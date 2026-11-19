import json
import sqlite3
from pathlib import Path

import pytest

from agents import report_sections as sections
from agents.derived import first_release, start_channel
from agents.report_sections import (
    APPENDIX_CATALOGUE,
    BASIS_LABELS,
    CELL_LABELS,
    NOT_INCLUDED,
    REASON_NO_STRATEGY,
    REASON_NOTHING_TO_COUNT,
    SECTION_CATALOGUE,
    build_document,
    glance_facts,
)
from models.report import BulletsBlock, CalloutBlock, FactsBlock, ParagraphBlock, ReportDocument, TableBlock
from models.schemas import PipelineResult, StageUsage, Usage, Versions
from tests.m4_report_fixtures_synthetic import (
    APP_VERSION,
    BUSY,
    GENERATED_AT,
    ROOT,
    SYNTHETIC_RESULTS,
    draft,
    synthetic_complete,
    synthetic_minimal,
    synthetic_no_strategy,
    synthetic_partial,
)
from utils import llm_client, search_client

STORED_RUNS = ROOT / "data" / "runs.db"
SAVED = sorted(path for path in (ROOT / "docs").glob("test_runs*/*.json") if path.name != "run_summary.json")
LIVE = [ROOT / "web" / "src" / "test" / "liveAgritech.json", ROOT / "web" / "src" / "test" / "liveFintech.json"]
REACT_BASIS_LABELS = {"sourced": "Sourced", "ai_interpretation": "AI interpretation", "user_provided": "From your idea",
                      "assumption": "Assumption"}


def load(path: Path) -> PipelineResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    return PipelineResult.model_validate(data.get("result", data) if "stages" in data else data)


def section(document: ReportDocument, section_id: str):
    return next(entry for entry in [*document.sections, *document.appendix_sections] if entry.id == section_id)


def of_type(document: ReportDocument, section_id: str, kind: type) -> list:
    return [block for block in section(document, section_id).blocks if isinstance(block, kind)]


def facts_of(document: ReportDocument, section_id: str) -> dict[str, str]:
    return {pair.label: pair.value for block in of_type(document, section_id, FactsBlock) for pair in block.pairs}


def table(document: ReportDocument, section_id: str, caption: str) -> TableBlock:
    return next(block for block in of_type(document, section_id, TableBlock) if block.caption == caption)


def texts(document: ReportDocument, section_id: str) -> list[str]:
    found = []
    for block in section(document, section_id).blocks:
        if isinstance(block, BulletsBlock):
            found += [entry.text for entry in block.items]
        elif hasattr(block, "text"):
            found.append(block.text)
    return found


def missing(document: ReportDocument) -> dict[str, str]:
    return {entry.id: entry.reason for entry in document.meta.sections_missing}


@pytest.fixture(autouse=True)
def no_outside_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args, **kwargs):
        raise AssertionError("the report builders must not call a model or a search")

    monkeypatch.setattr(llm_client, "_call_provider", refuse)
    monkeypatch.setattr(llm_client.groq_client, "generate_json", refuse)
    monkeypatch.setattr(search_client.requests, "post", refuse)


@pytest.mark.parametrize("name", list(SYNTHETIC_RESULTS))
def test_every_catalogue_section_appears_in_the_fixed_order(name: str) -> None:
    document = draft(SYNTHETIC_RESULTS[name]())
    assert [entry.id for entry in document.sections] == [section_id for section_id, _ in SECTION_CATALOGUE]
    assert [entry.title for entry in document.sections] == [title for _, title in SECTION_CATALOGUE]
    assert [entry.id for entry in document.appendix_sections] == [section_id for section_id, _ in APPENDIX_CATALOGUE]


def test_a_complete_result_includes_every_section() -> None:
    document = draft(synthetic_complete())
    assert document.meta.sections_missing == []
    assert document.meta.sections_included == [*(s for s, _ in SECTION_CATALOGUE), *(s for s, _ in APPENDIX_CATALOGUE)]
    assert document.title == "Startup validation report" and document.subtitle == synthetic_complete().idea.idea_title


def test_a_partial_result_explains_each_missing_part() -> None:
    document = draft(synthetic_partial())
    assert missing(document) == {"market": BUSY, "gtm": BUSY}
    for section_id, reason in missing(document).items():
        assert section(document, section_id).blocks == [CalloutBlock(kind="note", text=NOT_INCLUDED.format(reason=reason))]
    warning = of_type(document, "cover", CalloutBlock)[-1]
    assert warning.kind == "warning"
    assert warning.text == "Some parts of this validation did not finish: Analysing the market and Planning go-to-market."
    assert facts_of(document, "method")["Stages that did not finish"] == "Analysing the market and Planning go-to-market"
    assert facts_of(document, "cover")["Run status"] == "Partial"


def test_a_result_without_strategy_says_strategy_was_not_part_of_it() -> None:
    document = draft(synthetic_no_strategy())
    assert missing(document) == {key: REASON_NO_STRATEGY for key in ("swot", "risks", "mvp", "gtm")}


def test_a_minimal_result_still_has_a_title_block_method_and_limitations() -> None:
    result = synthetic_minimal()
    document = draft(result)
    reasons = missing(document)
    assert reasons["at_a_glance"] == REASON_NOTHING_TO_COUNT
    assert reasons["market"] == next(n.message for n in result.notices if n.stage == "market_opportunity")
    assert {"cover", "idea", "method", "limitations", "appendix_run", "appendix_glossary"} <= set(document.meta.sections_included)
    assert "Analysing the market" in of_type(document, "cover", CalloutBlock)[-1].text


def test_the_glance_figures_are_copied_from_the_result() -> None:
    result = synthetic_complete()
    shown = facts_of(draft(result), "at_a_glance")
    tam = result.market.market_size.tam
    assert shown["Market size (TAM)"] == f"Sourced: {tam.value}"
    assert shown["Market size (SAM)"] == "Unavailable"
    assert shown["Competitors found"].startswith(f"{len(result.competitors.competitors)} (")
    assert shown["Risks by severity"] == f"{len(result.swot.risks)} (2 high, 2 medium, 2 low)"
    assert shown["MVP features in the first release"] == str(len(first_release(result))) == "6"
    assert shown["First recommended channel"] == start_channel(result).name
    assert str(result.evidence_strength.score) in shown["Evidence strength"]
    assert [pair.label for pair in glance_facts(result)] == list(shown)


def test_the_market_size_table_keeps_values_and_statuses() -> None:
    result = synthetic_complete()
    rows = table(draft(result), "market", "Market size for this idea").rows
    size = result.market.market_size
    assert [row[1] for row in rows] == [figure.value or "Not available" for figure in (size.tam, size.sam, size.som)]
    assert [row[2] for row in rows] == ["Sourced" if f.status == "sourced" else "Unavailable" for f in (size.tam, size.sam, size.som)]


def test_risk_numbers_link_the_register_the_features_and_the_channels() -> None:
    result = synthetic_complete()
    document = draft(result)
    register = table(document, "risks", "Risk register")
    assert [row[0] for row in register.rows] == [str(index) for index in range(1, len(result.swot.risks) + 1)]
    assert [row[5] for row in register.rows] == [risk.severity.capitalize() for risk in result.swot.risks]
    features = table(document, "mvp", "First release")
    by_rank = {row[0]: row[7] for row in features.rows}
    assert by_rank["2"] == "2" and by_rank["6"] == "5" and by_rank["1"] == "None"
    channels = table(document, "gtm", "Channels, in the order to try them")
    assert channels.rows[0][1].endswith("(Start here)")
    assert channels.rows[0][8:10] == ["1", "1"]
    assert channels.rows[3][8:10] == ["1, 3", "3"]


def test_the_comparison_matrix_uses_symbols_and_words() -> None:
    result = synthetic_complete()
    matrix = table(draft(result), "competitors", "Feature comparison")
    assert matrix.columns == ["Competitor", *result.competitors.comparison.features]
    assert {cell for row in matrix.rows for cell in row[1:]} <= set(CELL_LABELS.values())


def test_the_basis_labels_are_the_interface_labels() -> None:
    assert BASIS_LABELS == REACT_BASIS_LABELS
    assert facts_of(draft(synthetic_complete()), "appendix_glossary")["From your idea"] == "Taken from what you wrote."


def test_labelled_items_keep_their_basis_and_source_keys() -> None:
    result = synthetic_complete()
    document = draft(result)
    demand = result.market.market_demand.demand_evidence[0]
    found = next(entry for block in of_type(document, "market", BulletsBlock) for entry in block.items if entry.text == demand.text)
    assert found.basis == demand.basis.value
    assert found.keys == [f"market:{source_id}" for source_id in demand.source_ids]
    summary = of_type(document, "executive_summary", BulletsBlock)[0]
    assert [entry.text for entry in summary.items] == [line.text for line in result.executive_summary]


def test_the_gtm_section_labels_a_hypothesis_differentiator() -> None:
    result = synthetic_complete()
    shown = facts_of(draft(result), "gtm")
    assert shown["Differentiator"] == f"{result.gtm.positioning.differentiator} (Hypothesis)"
    assert shown["Target segment"] == result.gtm.positioning.target_segment


def test_the_idea_section_marks_assumed_resources() -> None:
    complete = synthetic_complete()
    mvp = complete.mvp.model_copy(update={"quality": complete.mvp.quality.model_copy(update={"constraints_assumed": ["team_size"]})})
    result = complete.model_copy(update={"constraints": None, "mvp": mvp})
    shown = facts_of(draft(result), "idea")
    assert shown["Team size"] == "2 people (assumed)"
    assert shown["Budget"] == "Not given"
    assert facts_of(draft(complete), "idea")["Budget"] == "Bootstrapped"


def test_limitations_list_every_limitation_warning_and_standing_statement() -> None:
    result = synthetic_complete()
    shown = texts(draft(result), "limitations")
    for text in [*result.swot.limitations, *result.mvp.limitations, *result.gtm.limitations, *result.market.caveats]:
        assert text in shown
    for notice in result.notices:
        assert (notice.message in shown) == (notice.severity in ("warning", "error"))
    assert sections.STANDING_ABSENCE in shown and sections.STANDING_STRATEGY in shown
    assert len(shown) == len(set(text.lower() for text in shown))


def test_empty_lists_get_plain_wording() -> None:
    complete = synthetic_complete()
    swot = complete.swot.model_copy(update={"threats": []})
    competitors = complete.competitors.model_copy(update={"market_gaps": []})
    mvp = complete.mvp.model_copy(update={"success_metrics": []})
    document = draft(complete.model_copy(update={"swot": swot, "competitors": competitors, "mvp": mvp}))
    assert sections.NONE_IN_RUN in texts(document, "swot")
    assert sections.NONE_FOUND in texts(document, "competitors")
    assert sections.NO_METRICS in texts(document, "mvp")


def test_the_run_appendix_copies_timings_usage_queries_and_versions() -> None:
    complete = synthetic_complete()
    shown = table(draft(complete), "appendix_run", "Stage timings")
    stages = [key for key in complete.timings if key != "total"]
    assert [row[1] for row in shown.rows] == [sections.number(complete.timings[key]) for key in [*stages, "total"]]
    assert facts_of(draft(complete), "appendix_run")["AI requests"] == sections.NOT_RECORDED
    usage = Usage(llm_calls=7, search_calls=12, by_stage={"search": StageUsage(search_calls=4, seconds=0.5)})
    versions = Versions(query_profile="v1", prompt_profile="v1", prompt_versions={"market": "market-v1"}, app_version="0.1.0")
    document = draft(complete.model_copy(update={"usage": usage, "versions": versions}))
    shown = facts_of(document, "appendix_run")
    assert shown["AI requests"] == "7" and shown["Web searches"] == "12"
    assert shown["Prompt version (market)"] == "market-v1" and shown["Query profile"] == "v1"
    rows = {row[0]: row for row in table(document, "appendix_run", "Stage timings").rows}
    assert rows["Searching the web"][3] == "4" and rows["Total"][2:] == ["7", "12"]
    queries = table(document, "appendix_run", "Search queries").rows
    assert [row[1] for row in queries[: len(complete.search.sections)]] == [s.query for s in complete.search.sections]


def test_the_method_section_explains_the_labels_and_awaits_the_checks() -> None:
    document = draft(synthetic_complete())
    assert sections.CONSISTENCY_PENDING in texts(document, "method")
    assert set(BASIS_LABELS.values()) <= set(facts_of(document, "method"))


def test_numbers_are_never_rounded() -> None:
    assert sections.number(0.1234) == "0.1234" and sections.number(6.0) == "6" and sections.number(3) == "3"


def test_the_builders_are_pure() -> None:
    result = synthetic_complete()
    before = result.model_dump(mode="json")
    first = draft(result).model_dump(mode="json")
    assert draft(result).model_dump(mode="json") == first
    assert result.model_dump(mode="json") == before


def test_the_cover_shows_the_generation_date_and_the_report_version() -> None:
    shown = facts_of(draft(synthetic_complete()), "cover")
    assert shown["Date"] == GENERATED_AT[:10] and shown["Report version"] == "1"
    assert of_type(draft(synthetic_complete()), "cover", CalloutBlock)[0].text == sections.COVER_NOTE


def test_the_document_meta_describes_the_run() -> None:
    result = synthetic_partial()
    document = build_document(result, run_id="run-1", generated_at=GENERATED_AT, source_fingerprint="abc",
                              app_version=APP_VERSION)
    assert (document.meta.run_id, document.meta.source_fingerprint, document.meta.run_status) == ("run-1", "abc", "partial")
    assert document.meta.narrative_status == "skipped" and document.meta.app_version == APP_VERSION
    assert document.meta.idea_title == result.idea.idea_title and document.meta.industry == result.idea.industry


def test_the_app_version_defaults_to_the_meta_route_constant() -> None:
    from routes.meta_routes import APP_VERSION as META_VERSION

    assert build_document(synthetic_complete(), run_id="r", generated_at=GENERATED_AT).meta.app_version == META_VERSION


def test_narrative_free_paragraphs_are_not_marked_narrative() -> None:
    document = draft(synthetic_complete())
    blocks = [block for entry in [*document.sections, *document.appendix_sections] for block in entry.blocks]
    assert not any(getattr(block, "narrative", False) for block in blocks if isinstance(block, (ParagraphBlock, BulletsBlock)))


@pytest.mark.parametrize("path", [*SAVED, *LIVE], ids=lambda path: f"{path.parent.name}/{path.name}")
def test_every_stored_fixture_builds_a_document(path: Path) -> None:
    result = load(path)
    document = draft(result)
    assert ReportDocument.model_validate_json(document.model_dump_json()).meta.sections_included == document.meta.sections_included
    if result.market is not None:
        assert "market" in document.meta.sections_included


def stored_results(tmp_path: Path) -> list[PipelineResult]:
    copy_path = tmp_path / "runs_copy.db"
    source_db = sqlite3.connect(f"{STORED_RUNS.resolve().as_uri()}?mode=ro", uri=True)
    target_db = sqlite3.connect(copy_path)
    try:
        source_db.backup(target_db)
    finally:
        source_db.close()
    try:
        rows = target_db.execute("SELECT result_json FROM runs WHERE result_json IS NOT NULL").fetchall()
    finally:
        target_db.close()
    return [PipelineResult.model_validate_json(text) for (text,) in rows]


def test_every_result_in_a_copy_of_the_stored_runs_builds_a_document(tmp_path: Path) -> None:
    if not STORED_RUNS.exists():
        pytest.skip("no local run history")
    results = [result for result in stored_results(tmp_path) if result.idea is not None]
    assert results
    for result in results:
        assert draft(result).meta.run_status == result.status

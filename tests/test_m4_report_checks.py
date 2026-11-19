import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from agents.report_checks import CHECKS, check_document, consistency_text, with_consistency
from agents.report_sections import COLUMN_FEATURES, COLUMN_RISKS, CONSISTENCY_PENDING, HEADING_CONSISTENCY
from models.report import (
    BibEntry,
    BulletsBlock,
    CalloutBlock,
    FactsBlock,
    MissingSection,
    ParagraphBlock,
    ReportDocument,
    ReportItem,
    SubheadingBlock,
    TableBlock,
)
from models.schemas import PipelineResult
from tests.m4_report_fixtures_synthetic import ROOT, SYNTHETIC_RESULTS, full_document, synthetic_complete, synthetic_partial

STORED_RUNS = ROOT / "data" / "runs.db"
SAVED = sorted(path for path in (ROOT / "docs").glob("test_runs*/*.json") if path.name != "run_summary.json")
LIVE = [ROOT / "web" / "src" / "test" / "liveAgritech.json", ROOT / "web" / "src" / "test" / "liveFintech.json"]
FAKE_TAVILY_SHAPE = "tvly-" + "PLANTEDFAKE" + "0123456789"


def load(path: Path) -> PipelineResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    return PipelineResult.model_validate(data.get("result", data) if "stages" in data else data)


def failing(document: ReportDocument, result: PipelineResult) -> set[str]:
    return {check.id for check in check_document(document, result).checks if not check.passed}


def section(document: ReportDocument, section_id: str):
    return next(entry for entry in [*document.sections, *document.appendix_sections] if entry.id == section_id)


def first(document: ReportDocument, section_id: str, kind: type, where: Callable = lambda block: True):
    return next(block for block in section(document, section_id).blocks if isinstance(block, kind) and where(block))


def set_fact(document: ReportDocument, section_id: str, label: str, value: str) -> None:
    for block in section(document, section_id).blocks:
        if isinstance(block, FactsBlock):
            for pair in block.pairs:
                if pair.label == label:
                    pair.value = value


def planted(result: PipelineResult, change: Callable[[ReportDocument], None]) -> set[str]:
    document = full_document(result).model_copy(deep=True)
    change(document)
    return failing(document, result)


def assert_all_pass(result: PipelineResult) -> None:
    document = full_document(result)
    report = document.meta.consistency
    assert (report.passed_count, report.total_count) == (12, 12), [(c.id, c.detail) for c in report.checks if not c.passed]


def test_there_are_twelve_checks_in_order() -> None:
    assert [check_id for check_id, _ in CHECKS] == [f"C-{index:02d}" for index in range(1, 13)]


@pytest.mark.parametrize("name", list(SYNTHETIC_RESULTS))
def test_every_check_passes_on_every_synthetic_fixture(name: str) -> None:
    assert_all_pass(SYNTHETIC_RESULTS[name]())


@pytest.mark.parametrize("path", [*SAVED, *LIVE], ids=lambda path: f"{path.parent.name}/{path.name}")
def test_every_check_passes_on_every_stored_fixture(path: Path) -> None:
    assert_all_pass(load(path))


def test_every_check_passes_on_every_result_in_a_copy_of_the_stored_runs(tmp_path: Path) -> None:
    if not STORED_RUNS.exists():
        pytest.skip("no local run history")
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
    results = [PipelineResult.model_validate_json(text) for (text,) in rows]
    results = [result for result in results if result.idea is not None]
    assert results
    for result in results:
        assert_all_pass(result)


def test_the_method_section_states_the_result() -> None:
    document = full_document(synthetic_complete())
    method = section(document, "method").blocks
    index = next(i for i, block in enumerate(method) if isinstance(block, SubheadingBlock) and block.text == HEADING_CONSISTENCY)
    assert method[index + 1].text == "12 of 12 consistency checks passed."
    assert all(not (isinstance(block, ParagraphBlock) and block.text == CONSISTENCY_PENDING) for block in method)


def test_a_failed_check_is_named_in_the_method_section() -> None:
    result = synthetic_complete()
    document = full_document(result).model_copy(deep=True)
    set_fact(document, "cover", "Run status", "Failed")
    rechecked = with_consistency(document, result)
    assert rechecked.meta.consistency.passed_count == 11
    assert consistency_text(rechecked.meta.consistency) == "11 of 12 consistency checks passed. Failing checks: C-10."
    method = section(rechecked, "method").blocks
    assert any(isinstance(block, ParagraphBlock) and block.text.endswith("Failing checks: C-10.") for block in method)


def test_c01_flags_an_unknown_citation_and_an_uncited_entry() -> None:
    result = synthetic_complete()
    assert planted(result, lambda d: first(d, "idea", ParagraphBlock).cites.append(99)) == {"C-01"}
    assert planted(result, lambda d: d.bibliography.append(BibEntry(number=50, title="Uncited"))) == {"C-01"}


def test_c02_flags_a_section_that_is_neither_present_nor_explained() -> None:
    result = synthetic_complete()
    assert planted(result, lambda d: d.meta.sections_included.remove("swot")) == {"C-02"}
    assert planted(result, lambda d: d.sections.pop(6)) == {"C-02"}

    def unexplained(document: ReportDocument) -> None:
        document.meta.sections_included.remove("swot")
        document.meta.sections_missing.append(MissingSection(id="swot", reason="It did not finish."))

    assert planted(result, unexplained) == {"C-02"}


def test_c03_flags_a_glance_figure_that_differs_from_the_result() -> None:
    assert planted(synthetic_complete(), lambda d: set_fact(d, "at_a_glance", "Competitors found", "12 (12 direct)")) == {"C-03"}


def test_c04_flags_a_target_segment_that_is_not_the_priority_segment() -> None:
    assert planted(synthetic_complete(), lambda d: set_fact(d, "gtm", "Target segment", "Large estates")) == {"C-04"}


def test_c04_passes_on_case_and_spacing_differences() -> None:
    assert planted(synthetic_complete(), lambda d: set_fact(d, "gtm", "Target segment", " smallholder  FARMERS ")) == set()


def column_cell(document: ReportDocument, section_id: str, column: str, value: str) -> None:
    block = first(document, section_id, TableBlock, lambda b: column in b.columns)
    block.rows[0][block.columns.index(column)] = value


def test_c05_flags_a_risk_link_outside_the_register() -> None:
    result = synthetic_complete()
    assert planted(result, lambda d: column_cell(d, "mvp", COLUMN_RISKS, "9")) == {"C-05"}
    assert planted(result, lambda d: column_cell(d, "gtm", COLUMN_RISKS, "1, 7")) == {"C-05"}
    feature = result.mvp.features[0].model_copy(update={"mitigates_risk_ids": ["R99"]})
    broken = result.model_copy(update={"mvp": result.mvp.model_copy(update={"features": [feature, *result.mvp.features[1:]]})})
    assert "C-05" in failing(full_document(broken), broken)


def test_c06_flags_a_feature_link_outside_the_mvp_section() -> None:
    result = synthetic_complete()
    assert planted(result, lambda d: column_cell(d, "gtm", COLUMN_FEATURES, "42")) == {"C-06"}
    channel = result.gtm.channels[0].model_copy(update={"uses_feature_ids": ["F99"]})
    broken = result.model_copy(update={"gtm": result.gtm.model_copy(update={"channels": [channel, *result.gtm.channels[1:]]})})
    assert "C-06" in failing(full_document(broken), broken)


def test_c07_flags_a_gap_without_its_caveat_or_label_and_an_unlabelled_hypothesis() -> None:
    result = synthetic_complete()

    def no_caveat(document: ReportDocument) -> None:
        competitors = section(document, "competitors")
        competitors.blocks = [b for b in competitors.blocks if not (isinstance(b, CalloutBlock) and b.kind == "caveat")]

    def no_label(document: ReportDocument) -> None:
        for block in section(document, "competitors").blocks:
            if isinstance(block, BulletsBlock):
                for entry in block.items:
                    entry.text = entry.text.replace("a hypothesis", "a finding")

    assert planted(result, no_caveat) == {"C-07"}
    assert planted(result, no_label) == {"C-07"}
    assert planted(result, lambda d: set_fact(d, "gtm", "Differentiator", result.gtm.positioning.differentiator)) == {"C-07"}


def test_c08_flags_a_sourced_narrative_statement() -> None:
    result = synthetic_complete()

    def paragraph(document: ReportDocument) -> None:
        section(document, "executive_summary").blocks.insert(0, ParagraphBlock(text="Overview.", basis="sourced", narrative=True))

    def bullets(document: ReportDocument) -> None:
        section(document, "executive_summary").blocks.append(
            BulletsBlock(items=[ReportItem(text="Insight.", basis="sourced")], narrative=True)
        )

    assert planted(result, paragraph) == {"C-08"}
    assert planted(result, bullets) == {"C-08"}
    assert planted(result, lambda d: section(d, "executive_summary").blocks.append(
        ParagraphBlock(text="Overview.", basis="ai_interpretation", narrative=True))) == set()


def test_c09_flags_a_warning_notice_missing_from_limitations() -> None:
    result = synthetic_complete()
    warning = next(notice for notice in result.notices if notice.severity == "warning")

    def drop(document: ReportDocument) -> None:
        for block in section(document, "limitations").blocks:
            if isinstance(block, BulletsBlock):
                block.items = [entry for entry in block.items if entry.text != warning.message]

    assert planted(result, drop) == {"C-09"}


def test_c10_flags_a_wrong_status_and_an_unlisted_unfinished_stage() -> None:
    result = synthetic_complete()
    assert planted(result, lambda d: set_fact(d, "cover", "Run status", "Partial")) == {"C-10"}

    def status(document: ReportDocument) -> None:
        document.meta.run_status = "partial"

    assert planted(result, status) == {"C-10"}
    partial = synthetic_partial()

    def unlisted(document: ReportDocument) -> None:
        cover = section(document, "cover")
        cover.blocks = [b for b in cover.blocks if not (isinstance(b, CalloutBlock) and b.kind == "warning")]

    assert planted(partial, unlisted) == {"C-10"}


def test_c11_flags_a_configured_key_and_a_key_shaped_string() -> None:
    result = synthetic_complete()
    assert planted(result, lambda d: first(d, "idea", ParagraphBlock).__setattr__("text", "Key " + "test-" + "tavily-key")) == {"C-11"}
    assert planted(result, lambda d: first(d, "idea", ParagraphBlock).__setattr__("text", f"Key {FAKE_TAVILY_SHAPE}")) == {"C-11"}


def test_c11_details_never_hold_the_key() -> None:
    result = synthetic_complete()
    document = full_document(result).model_copy(deep=True)
    first(document, "idea", ParagraphBlock).text = f"Key {FAKE_TAVILY_SHAPE}"
    detail = next(check.detail for check in check_document(document, result).checks if check.id == "C-11")
    assert FAKE_TAVILY_SHAPE not in detail and "Tavily" in detail


def test_c12_flags_a_control_character() -> None:
    result = synthetic_complete()
    assert planted(result, lambda d: first(d, "idea", ParagraphBlock).__setattr__("text", "Bell \x07 here")) == {"C-12"}
    assert planted(result, lambda d: first(d, "idea", ParagraphBlock).__setattr__("text", "Two\nlines\tand a tab")) == set()


def test_checks_leave_the_document_unchanged() -> None:
    result = synthetic_complete()
    document = full_document(result)
    before = document.model_dump(mode="json")
    check_document(document, result)
    with_consistency(document, result)
    assert document.model_dump(mode="json") == before

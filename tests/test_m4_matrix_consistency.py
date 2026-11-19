import json
from pathlib import Path
from typing import Any

import pytest

from agents import competitor_analysis_agent as competitor_agent
from agents import market_opportunity_agent as market_agent
from agents.competitor_checks import (
    FEATURE_REMOVED,
    FEATURE_TABLE_CORRECTED,
    align_key_features,
    feature_key,
    feature_sources,
    founder_text,
)
from agents.evidence import sourced_items
from agents.integrity import check_competitor_integrity, check_market_integrity
from agents.market_size import market_evidence
from agents.notices import CODE_FEATURE_MISMATCH, build_notices, leaks, notice_for_warning
from models.schemas import (
    Comparison,
    ComparisonCell,
    ComparisonRow,
    Competitor,
    CompetitorAnalysisDraft,
    CompetitorAnalysisResult,
    EvidenceItem,
    FeatureCoverage,
    IdeaSubmission,
    PipelineResult,
)
from tests.test_m4_profiles_v1_snapshots import sha
from utils.errors import AppError

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = Path(__file__).resolve().parent / "snapshots" / "m4_v1_checks.json"
FIXTURES = {
    "docs/test_runs_m2/agritech.json": "agritech",
    "docs/test_runs_m2/fintech_cashflow.json": "fintech_cashflow",
    "docs/test_runs_m2/foodtech_surplus.json": "foodtech_surplus",
    "web/src/test/liveAgritech.json": "agritech",
    "web/src/test/liveFintech.json": "fintech_cashflow",
    "web/src/test/strategyFixture.synthetic.json": None,
}
CORRECTED_MESSAGE = "A competitor's listed feature did not match the comparison table, so the table was corrected."
REMOVED_MESSAGE = "A competitor's listed feature did not match the comparison table, so the feature was removed."
EVIDENCE = [
    EvidenceItem(id="S0", title="Search summary", snippet="LeafDoc offers offline diagnosis.", section_label="Summary"),
    EvidenceItem(id="S1", title="LeafDoc review", url="https://reviews.example/leafdoc",
                 snippet="LeafDoc offers offline diagnosis and a treatment calendar for farmers.", section_label="Competitors"),
    EvidenceItem(id="S2", title="Farm tools", url="https://tools.example/list",
                 snippet="Many apps offer voice support in local languages.", section_label="Competitors"),
    EvidenceItem(id="S3", title="CropPal pricing", url="https://croppal.example/pricing",
                 snippet="CropPal is free for farmers.", section_label="Competitors"),
]


@pytest.fixture(autouse=True)
def default_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PROMPT_PROFILE", "QUERY_PROFILE", "EVIDENCE_MAX_ITEMS", "COMPETITOR_MAX_EXTRA_QUERIES"):
        monkeypatch.delenv(name, raising=False)


def competitor(name: str, features: list[str], source_ids: list[str]) -> Competitor:
    return Competitor(name=name, type="direct", relevance_note="Serves the same farmers.", source_ids=source_ids,
                      key_features=features, offering="An app.", info_completeness="partial")


def row(name: str, *cells: tuple[str, str, list[str]]) -> ComparisonRow:
    return ComparisonRow(competitor=name, cells=[ComparisonCell(feature=f, status=s, source_ids=ids) for f, s, ids in cells])


def comparison(features: list[str], *rows: ComparisonRow) -> Comparison:
    coverage = [
        FeatureCoverage(feature=f, competitors_with_evidence=sum(
            c.feature == f and c.status == "evidence_found" for r in rows for c in r.cells)) for f in features
    ]
    return Comparison(features=features, rows=list(rows), feature_coverage=coverage)


def planted() -> tuple[list[Competitor], Comparison]:
    competitors = [
        competitor("LeafDoc", ["Offline diagnosis", "Treatment calendar", "Voice support"], ["S1", "S2"]),
        competitor("CropPal", ["Free plan"], ["S3"]),
    ]
    features = ["Offline diagnosis", "Treatment calendar", "Voice support", "Free plan"]
    matrix = comparison(
        features,
        row("LeafDoc", ("Offline diagnosis", "evidence_found", ["S1"]), ("Treatment calendar", "unclear", []),
            ("Voice support", "no_evidence_found", []), ("Free plan", "no_evidence_found", [])),
        row("CropPal", ("Offline diagnosis", "no_evidence_found", []), ("Treatment calendar", "unclear", []),
            ("Voice support", "unclear", []), ("Free plan", "evidence_found", ["S3"])),
    )
    return competitors, matrix


def conflicts(competitors: list[Competitor], matrix: Comparison) -> list[tuple[str, str]]:
    rows = {r.competitor: {feature_key(c.feature): c.status for c in r.cells} for r in matrix.rows}
    return [
        (c.name, feature)
        for c in competitors
        for feature in c.key_features
        if rows.get(c.name, {}).get(feature_key(feature), "evidence_found") != "evidence_found"
    ]


def load(path: str) -> PipelineResult:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return PipelineResult.model_validate(data["result"] if "stages" in data else data)


def founder(name: str | None) -> str:
    if name is None:
        return founder_text(None)
    data = json.loads((ROOT / "data" / "test_ideas" / f"{name}.json").read_text(encoding="utf-8"))
    return founder_text(IdeaSubmission(**data))


def guarded(call: Any) -> tuple[Any, dict]:
    try:
        result, warnings = call()
    except AppError as exc:
        return None, {"raised": type(exc).__name__, "message": exc.user_message}
    return result, {"result_sha256": sha(result.model_dump_json()), "warnings": warnings}


def competitor_inputs(saved: PipelineResult, name: str | None) -> tuple:
    evidence = competitor_agent.competitor_evidence(saved.search, saved.competitor_search, list(saved.competitor_candidates))
    draft = CompetitorAnalysisDraft.model_validate(saved.competitors.model_dump())
    return draft, evidence, saved.idea, founder(name), list(saved.competitors.queries_used)


def render(path: str, name: str | None, **profile: str) -> dict:
    saved = load(path)
    row_: dict[str, Any] = {}
    evidence = market_evidence(saved.search, saved.market_search, saved.idea)
    row_["market_stored_violations"] = check_market_integrity(saved.market, evidence)
    result, row_["market_guards"] = guarded(
        lambda: market_agent._apply_guards(saved.market, evidence, len(sourced_items(evidence)), saved.idea)
    )
    row_["market_violations"] = None if result is None else check_market_integrity(result, evidence)
    inputs = competitor_inputs(saved, name)
    row_["competitor_stored_violations"] = check_competitor_integrity(saved.competitors, inputs[1])
    result, row_["competitor_guards"] = guarded(lambda: competitor_agent._apply_guards(*inputs, **profile))
    row_["competitor_violations"] = None if result is None else check_competitor_integrity(result, inputs[1])
    return row_


@pytest.fixture(scope="module")
def stored() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_the_rule_corrects_a_cell_its_own_cited_source_supports() -> None:
    competitors, matrix = planted()
    fixed_competitors, fixed, warnings = align_key_features(competitors, matrix, EVIDENCE)

    leafdoc = fixed.rows[0].cells
    assert leafdoc[1] == ComparisonCell(feature="Treatment calendar", status="evidence_found", source_ids=["S1"])
    assert fixed_competitors[0].key_features == ["Offline diagnosis", "Treatment calendar"]
    assert fixed.rows[1] == matrix.rows[1] and fixed_competitors[1] == competitors[1]
    assert [item.competitors_with_evidence for item in fixed.feature_coverage] == [1, 1, 0, 1]
    assert warnings == [
        "comparison: " + FEATURE_TABLE_CORRECTED.format(feature="Treatment calendar", name="LeafDoc", status="unclear"),
        "competitors[0].key_features: "
        + FEATURE_REMOVED.format(feature="Voice support", name="LeafDoc", status="no_evidence_found"),
    ]
    assert conflicts(fixed_competitors, fixed) == [] and conflicts(competitors, matrix) != []


def test_a_source_that_does_not_name_the_competitor_or_the_summary_never_backs_a_feature() -> None:
    lone = competitor("LeafDoc", ["Voice support"], ["S0", "S2"])
    assert feature_sources("Voice support", lone, EVIDENCE) == []
    assert feature_sources("Offline diagnosis", competitor("LeafDoc", [], ["S0"]), EVIDENCE) == []
    assert feature_sources("Offline diagnosis", competitor("LeafDoc", [], ["S1"]), EVIDENCE) == ["S1"]
    assert feature_sources("Offline diagnosis and app", competitor("LeafDoc", [], ["S1"]), EVIDENCE) == []
    assert feature_sources("of the", competitor("LeafDoc", [], ["S1"]), EVIDENCE) == []


def test_a_removed_feature_updates_the_completeness_count() -> None:
    sparse = Competitor(name="LeafDoc", type="direct", relevance_note="Same farmers.", source_ids=["S2"],
                        key_features=["Voice support"], offering="An app.", target_segment="Farmers",
                        info_completeness="partial")
    matrix = comparison(["Voice support"], row("LeafDoc", ("Voice support", "unclear", [])))
    fixed_competitors, fixed, warnings = align_key_features([sparse], matrix, EVIDENCE)

    assert fixed_competitors[0].key_features == [] and fixed_competitors[0].info_completeness == "minimal"
    assert fixed == matrix and len(warnings) == 1


def test_consistent_rows_and_features_outside_the_table_are_left_alone() -> None:
    competitors = [competitor("LeafDoc", ["Offline diagnosis", "Weather alerts"], ["S1"])]
    matrix = comparison(["Offline diagnosis"], row("LeafDoc", ("Offline diagnosis", "evidence_found", ["S1"])))
    fixed_competitors, fixed, warnings = align_key_features(competitors, matrix, EVIDENCE)
    assert fixed_competitors is competitors and fixed is matrix and warnings == []


def test_both_repairs_give_the_new_plain_notice() -> None:
    corrected, removed = [
        notice_for_warning(f"Competitor analysis: {warning}")
        for warning in align_key_features(*planted(), EVIDENCE)[2]
    ]
    assert (corrected.code, corrected.message, corrected.severity) == (CODE_FEATURE_MISMATCH, CORRECTED_MESSAGE, "info")
    assert (removed.code, removed.message, removed.severity) == (CODE_FEATURE_MISMATCH, REMOVED_MESSAGE, "info")
    assert corrected.stage == removed.stage == "competitor_analysis"
    assert not leaks(corrected.message) and not leaks(removed.message)
    notices = build_notices([f"Competitor analysis: {w}" for w in align_key_features(*planted(), EVIDENCE)[2]], [])
    assert [notice.code for notice in notices] == [CODE_FEATURE_MISMATCH, CODE_FEATURE_MISMATCH]


def three_feature_idea() -> Any:
    idea = load("web/src/test/strategyFixture.synthetic.json").idea
    return idea.model_copy(update={"key_features": ["Photo scan", "Local language", "Expert chat"]})


def planted_draft() -> CompetitorAnalysisDraft:
    competitors, matrix = planted()
    return CompetitorAnalysisDraft.model_validate({
        "competitors": [c.model_dump(exclude={"info_completeness"}) for c in competitors],
        "comparison": {"features": matrix.features, "rows": [r.model_dump() for r in matrix.rows]},
        "data_quality": {"evidence_level": "limited", "notes": []},
    })


@pytest.mark.parametrize("profile", ["v1", "v2"])
def test_the_competitor_guards_apply_the_rule_only_under_v2(profile: str) -> None:
    idea = three_feature_idea()
    result, warnings = competitor_agent._apply_guards(planted_draft(), EVIDENCE, idea, "", [], profile=profile)

    assert check_competitor_integrity(result, EVIDENCE) == []
    mismatches = [w for w in warnings if notice_for_warning(f"Competitor analysis: {w}").code == CODE_FEATURE_MISMATCH]
    if profile == "v1":
        assert mismatches == [] and conflicts(result.competitors, result.comparison) != []
        default, default_warnings = competitor_agent._apply_guards(planted_draft(), EVIDENCE, idea, "", [])
        assert (default, default_warnings) == (result, warnings)
    else:
        assert len(mismatches) == 2 and conflicts(result.competitors, result.comparison) == []


def test_the_agent_runs_the_rule_when_the_active_profile_is_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = load("web/src/test/strategyFixture.synthetic.json")
    monkeypatch.setattr(competitor_agent, "find_candidates", lambda *args: ([], []))
    monkeypatch.setattr(competitor_agent, "search_competitors", lambda queries: (None, []))
    monkeypatch.setattr(competitor_agent, "competitor_evidence", lambda *args, **kwargs: EVIDENCE)
    monkeypatch.setattr(competitor_agent, "call_structured", lambda *args, **kwargs: planted_draft())
    found = {}
    for profile in ("v1", "v2"):
        monkeypatch.setenv("PROMPT_PROFILE", profile)
        run = competitor_agent.analyse_competitors(three_feature_idea(), saved.search)
        found[profile] = [w for w in run.warnings if CODE_FEATURE_MISMATCH == notice_for_warning(
            f"Competitor analysis: {w}").code]
    assert found["v1"] == [] and len(found["v2"]) == 2


def test_the_snapshot_was_taken_on_every_stored_result_fixture(stored: dict) -> None:
    assert sorted(stored) == sorted(FIXTURES)
    assert all(set(row_) == {"market_stored_violations", "market_guards", "market_violations",
                             "competitor_stored_violations", "competitor_guards", "competitor_violations"}
               for row_ in stored.values())


@pytest.mark.parametrize("path", list(FIXTURES))
def test_existing_checks_behave_as_before_on_every_stored_fixture(stored: dict, path: str) -> None:
    assert render(path, FIXTURES[path]) == stored[path]
    assert render(path, FIXTURES[path], profile="v1") == stored[path]


@pytest.mark.parametrize("path", list(FIXTURES))
def test_v2_only_adds_the_rule_on_every_stored_fixture(stored: dict, path: str) -> None:
    v2 = render(path, FIXTURES[path], profile="v2")
    before = stored[path]
    for key in ("market_stored_violations", "market_guards", "market_violations", "competitor_stored_violations"):
        assert v2[key] == before[key], key
    if "raised" in before["competitor_guards"]:
        assert v2["competitor_guards"] == before["competitor_guards"]
        return
    assert v2["competitor_violations"] == before["competitor_violations"] == []
    added = [w for w in v2["competitor_guards"]["warnings"] if w not in before["competitor_guards"]["warnings"]]
    assert [w for w in before["competitor_guards"]["warnings"] if w not in v2["competitor_guards"]["warnings"]] == []
    assert all(notice_for_warning(f"Competitor analysis: {w}").code == CODE_FEATURE_MISMATCH for w in added)
    result, _ = competitor_agent._apply_guards(*competitor_inputs(load(path), FIXTURES[path]), profile="v2")
    assert isinstance(result, CompetitorAnalysisResult) and conflicts(result.competitors, result.comparison) == []
    if not added:
        assert v2["competitor_guards"] == before["competitor_guards"]

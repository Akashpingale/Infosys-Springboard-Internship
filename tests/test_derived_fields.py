"""Evidence strength, executive summary and verify-next (KIRO_UI_UPGRADE_SPEC.md 8.5 and 10.4).

Everything here is derived in code from results the agents already checked, so these tests build
real results with fakes (tests/pipeline_fakes.py) or read the saved live runs as data. No claim,
figure or source is invented by a test.
"""

import json
from pathlib import Path

import pytest

from agents.derived import (
    BREADTH_CAP,
    CAPTION,
    LEVEL_VALUES,
    MSG_NO_MARKET_SIZE,
    WEIGHTS,
    evidence_strength,
    executive_summary,
    source_domain,
    strength_label,
    verify_next,
    with_derived_fields,
)
from models.schemas import (
    EVIDENCE_STRENGTH_LABELS,
    Basis,
    DataQuality,
    MarketFigure,
    PipelineResult,
    SourceRef,
)
from tests.pipeline_fakes import PIPELINE_SUBMISSION, use_full_pipeline

RUNS = Path(__file__).resolve().parent.parent / "docs" / "test_runs_m2"
DOMAINS = ("agritech", "fintech_cashflow", "foodtech_surplus")


@pytest.fixture
def full(monkeypatch: pytest.MonkeyPatch) -> PipelineResult:
    """A complete four-stage result produced with fakes."""
    import orchestrator

    use_full_pipeline(monkeypatch)
    return orchestrator.run_pipeline(PIPELINE_SUBMISSION, orchestrator.FULL_STAGES)


def saved(name: str) -> PipelineResult:
    return PipelineResult.model_validate(json.loads((RUNS / f"{name}.json").read_text(encoding="utf-8")))


# --- the formula (Section 8.5) ----------------------------------------------------------------


def test_the_weights_and_the_cap_are_the_specified_ones() -> None:
    assert WEIGHTS == {"sourced_share": 0.40, "source_breadth": 0.30, "evidence_level": 0.30}
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)
    assert BREADTH_CAP == 8
    assert LEVEL_VALUES == {"strong": 1.0, "limited": 0.5, "insufficient": 0.0}


@pytest.mark.parametrize(
    ("score", "label"),
    [(1.0, "strong"), (0.70, "strong"), (0.699, "moderate"), (0.40, "moderate"), (0.399, "limited"), (0.0, "limited")],
)
def test_the_label_bands_are_exact_at_their_edges(score: float, label: str) -> None:
    assert strength_label(score) == label
    assert label in EVIDENCE_STRENGTH_LABELS


def test_a_perfect_result_scores_one_and_reads_strong(full: PipelineResult) -> None:
    perfect = full.model_copy(update={
        "market": full.market.model_copy(update={
            "data_quality": DataQuality(evidence_level="strong", notes=[]),
            "sources": [SourceRef(id=f"S{n}", title=f"t{n}", url=f"https://s{n}.example/a") for n in range(1, 9)],
        }),
        "competitors": full.competitors.model_copy(update={"data_quality": DataQuality(evidence_level="strong", notes=[])}),
    })
    # every labelled item sourced: take the share component on its own
    strength = evidence_strength(perfect)

    breadth = next(c for c in strength.components if c.key == "source_breadth")
    level = next(c for c in strength.components if c.key == "evidence_level")
    assert breadth.value == 1.0 and level.value == 1.0
    assert strength.score == pytest.approx(0.4 * next(c for c in strength.components if c.key == "sourced_share").value + 0.6)


def test_the_breadth_component_counts_distinct_domains_up_to_the_cap(full: PipelineResult) -> None:
    many = [SourceRef(id=f"S{n}", title=f"t{n}", url=f"https://site{n}.example/x") for n in range(1, 13)]
    same = [SourceRef(id=f"S{n}", title=f"t{n}", url=f"https://www.one.example/page{n}") for n in range(1, 6)]

    wide = evidence_strength(full.model_copy(update={"market": full.market.model_copy(update={"sources": many}),
                                                     "competitors": full.competitors.model_copy(update={"sources": []})}))
    narrow = evidence_strength(full.model_copy(update={"market": full.market.model_copy(update={"sources": same}),
                                                       "competitors": full.competitors.model_copy(update={"sources": []})}))

    assert next(c for c in wide.components if c.key == "source_breadth").value == 1.0, "12 domains, capped at 8"
    assert next(c for c in narrow.components if c.key == "source_breadth").value == pytest.approx(1 / 8), (
        "five pages on one site are one domain"
    )


def test_www_and_case_do_not_make_a_second_domain() -> None:
    assert source_domain("https://WWW.Example.com/a") == source_domain("https://example.com/b") == "example.com"


def test_each_component_explains_itself_without_a_percentage_headline(full: PipelineResult) -> None:
    strength = evidence_strength(full)

    assert strength.caption == CAPTION and "not a prediction" in strength.caption
    assert [component.key for component in strength.components] == list(WEIGHTS)
    for component in strength.components:
        assert component.weight == WEIGHTS[component.key]
        assert 0.0 <= component.value <= 1.0
        assert component.detail.endswith(".") and component.label


def test_one_analysis_alone_still_gets_a_rating(full: PipelineResult) -> None:
    market_only = evidence_strength(full.model_copy(update={"competitors": None}))
    competitor_only = evidence_strength(full.model_copy(update={"market": None}))

    for strength in (market_only, competitor_only):
        assert strength is not None and strength.label in EVIDENCE_STRENGTH_LABELS
    assert "Market evidence" in next(c for c in market_only.components if c.key == "evidence_level").detail
    assert "Competitor evidence" in next(c for c in competitor_only.components if c.key == "evidence_level").detail


def test_without_an_analysis_there_is_no_rating(full: PipelineResult) -> None:
    assert evidence_strength(full.model_copy(update={"market": None, "competitors": None})) is None
    assert evidence_strength(PipelineResult(status="failed")) is None


@pytest.mark.parametrize("name", DOMAINS)
def test_the_saved_live_runs_get_a_rating_that_matches_the_formula(name: str) -> None:
    strength = evidence_strength(saved(name))

    by_hand = sum(component.weight * component.value for component in strength.components)
    assert strength.score == pytest.approx(by_hand, abs=5e-4)
    assert strength.label == strength_label(strength.score)


# --- the executive summary (Section 10.4) -----------------------------------------------------


def test_the_summary_quotes_the_checked_results_with_their_basis_and_sources(full: PipelineResult) -> None:
    lines = executive_summary(full)

    topics = [line.topic for line in lines]
    assert topics == ["market_size", "demand", "priority_segment", "competitors", "gap", "limitation"]
    assert len(lines) <= 6
    size = lines[0]
    assert size.text == "Market size (TAM): USD 1.8 billion (AI crop disease detection market, 2025)."
    assert size.basis is Basis.sourced and size.source_ids == ["S1"] and size.analysis == "market"
    demand = lines[1]
    assert demand.text.startswith("Demand: ") and demand.source_ids
    assert all(line.text.endswith(".") for line in lines)


def test_a_sourced_claim_keeps_the_wording_the_agent_checked(full: PipelineResult) -> None:
    demand = next(line for line in executive_summary(full) if line.topic == "demand")
    original = full.market.market_demand.demand_evidence[0]

    assert original.text in demand.text, "the claim is quoted, not rewritten"
    assert demand.basis is original.basis and demand.source_ids == original.source_ids


def test_a_missing_market_size_is_stated_rather_than_guessed(full: PipelineResult) -> None:
    unavailable = MarketFigure(status="unavailable")
    size = full.market.market_size.model_copy(update={"tam": unavailable, "sam": unavailable, "som": unavailable})

    line = next(l for l in executive_summary(full.model_copy(update={"market": full.market.model_copy(update={"market_size": size})})) if l.topic == "market_size")

    assert line.text == MSG_NO_MARKET_SIZE and line.source_ids == []
    assert line.basis is None, "nothing is claimed as sourced"


def test_an_estimated_market_size_is_labelled_as_needing_verification(full: PipelineResult) -> None:
    estimate = MarketFigure(value="USD 4 billion", status="estimate_needs_verification", source_ids=["S1"])
    unavailable = MarketFigure(status="unavailable")
    size = full.market.market_size.model_copy(update={"tam": estimate, "sam": unavailable, "som": unavailable})

    line = next(l for l in executive_summary(full.model_copy(update={"market": full.market.model_copy(update={"market_size": size})})) if l.topic == "market_size")

    assert "needs verification" in line.text and "USD 4 billion" in line.text
    assert line.basis is None, "an estimate is never shown as sourced"


def test_the_competitor_count_is_counted_not_claimed(full: PipelineResult) -> None:
    line = next(l for l in executive_summary(full) if l.topic == "competitors")
    counts = {kind: sum(1 for c in full.competitors.competitors if c.type == kind) for kind in ("direct", "indirect", "emerging")}

    assert line.text.startswith(f"{sum(counts.values())} competitor")
    assert line.basis is None and line.source_ids == [], "a count has no source of its own"
    for kind, number in counts.items():
        if number:
            assert f"{number} {kind}" in line.text


def test_the_most_confident_gap_comes_first_and_is_called_a_hypothesis(full: PipelineResult) -> None:
    line = next(l for l in executive_summary(full) if l.topic == "gap")

    assert "hypothesis" in line.text
    assert any(line.text.endswith(f"{gap.description}.") or gap.description in line.text
               for gap in full.competitors.market_gaps)


def test_a_result_without_an_analysis_has_no_summary(full: PipelineResult) -> None:
    assert executive_summary(full.model_copy(update={"market": None, "competitors": None})) == []


@pytest.mark.parametrize("name", DOMAINS)
def test_every_summary_line_of_the_saved_runs_traces_to_its_own_analysis(name: str) -> None:
    result = saved(name)
    ids = {"market": {s.id for s in result.market.sources}, "competitors": {s.id for s in result.competitors.sources}}

    for line in executive_summary(result):
        assert line.text and line.text.endswith(".")
        if line.source_ids:
            assert line.analysis in ids, line.topic
            assert set(line.source_ids) <= ids[line.analysis] | {"S0"}, f"{line.topic}: {line.source_ids}"


# --- what to verify next (Section 10.4) --------------------------------------------------------


def test_unavailable_figures_become_one_checklist_item(full: PipelineResult) -> None:
    items = verify_next(full)

    sizes = [item for item in items if item.topic == "market_size"]
    assert len(sizes) == 1 and "SAM or SOM" in sizes[0].text, "the fake has a sourced TAM and two unavailable"


def test_estimates_low_confidence_gaps_and_thin_competitors_are_listed(full: PipelineResult) -> None:
    estimate = MarketFigure(value="USD 9 billion", status="estimate_needs_verification", source_ids=["S1"],
                            scope="broader_market")
    result = full.model_copy(update={"market": full.market.model_copy(update={"broader_markets": [estimate]})})

    topics = [item.topic for item in verify_next(result)]

    assert "broader_market" in topics
    assert "evidence" in topics, "an evidence level below strong is worth checking"
    broader = next(item for item in verify_next(result) if item.topic == "broader_market")
    assert "USD 9 billion" in broader.text and broader.source_ids == ["S1"]


def test_a_missing_priority_segment_becomes_an_item(full: PipelineResult) -> None:
    result = full.model_copy(update={"market": full.market.model_copy(update={"priority_segment": None})})
    assert any(item.topic == "priority_segment" for item in verify_next(result))


def test_a_strong_clean_analysis_needs_no_evidence_item(full: PipelineResult) -> None:
    strong = full.model_copy(update={
        "market": full.market.model_copy(update={"data_quality": DataQuality(evidence_level="strong", notes=[])}),
        "competitors": full.competitors.model_copy(update={"data_quality": DataQuality(evidence_level="strong", notes=[])}),
    })
    assert not [item for item in verify_next(strong) if item.topic == "evidence"]


def test_without_an_analysis_there_is_nothing_to_verify(full: PipelineResult) -> None:
    assert verify_next(full.model_copy(update={"market": None, "competitors": None})) == []


@pytest.mark.parametrize("name", DOMAINS)
def test_the_saved_runs_produce_readable_checklist_items(name: str) -> None:
    items = verify_next(saved(name))

    assert items, "each saved run has something left to verify"
    for item in items:
        assert item.text and item.text[0].isupper() and item.text.endswith(".")
        assert "[" not in item.text and "_" not in item.text.replace("\n", ""), item.text


# --- all together ------------------------------------------------------------------------------


def test_a_pipeline_result_carries_the_derived_fields(full: PipelineResult) -> None:
    assert full.evidence_strength is not None and full.evidence_strength.label in EVIDENCE_STRENGTH_LABELS
    assert full.executive_summary and full.verify_next
    assert PipelineResult.model_validate(full.model_dump(mode="json")) == full, "the result round-trips as JSON"


def test_a_milestone_1_result_gets_no_analysis_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    import orchestrator

    use_full_pipeline(monkeypatch)
    result = orchestrator.run_pipeline(PIPELINE_SUBMISSION)  # the two Milestone 1 stages

    assert result.status == "complete" and result.market is None
    assert result.evidence_strength is None and result.executive_summary == [] and result.verify_next == []
    assert result.notices == [], "a clean Milestone 1 run has nothing to report"


def test_a_failure_while_deriving_leaves_the_result_untouched(monkeypatch: pytest.MonkeyPatch, full: PipelineResult) -> None:
    """The derived fields are extras: a problem there must never fail a run."""
    import agents.derived as derived

    monkeypatch.setattr(derived, "evidence_strength", lambda result: 1 / 0)
    plain = full.model_copy(update={"evidence_strength": None, "executive_summary": [], "verify_next": [], "notices": []})

    assert with_derived_fields(plain) == plain

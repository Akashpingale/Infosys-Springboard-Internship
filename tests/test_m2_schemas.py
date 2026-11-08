"""Milestone 2 shared labeled types (KIRO_PROMPT_M2.md Section 5.2)."""

import json

import pytest
from pydantic import ValidationError

from models.schemas import (
    MARKET_SCOPES,
    QUANT_STATUSES,
    SNIPPET_MAX,
    Basis,
    EvidenceItem,
    LabeledItem,
    MarketFigure,
    MarketOpportunityDraft,
    MarketSize,
    QuantEstimate,
    SourceRef,
)
from tests.m2_fakes import market_reply


def test_basis_has_exactly_the_four_labels_and_serialises_as_text() -> None:
    assert {b.value for b in Basis} == {"sourced", "assumption", "ai_interpretation", "user_provided"}
    item = LabeledItem(text="Demand is rising", basis=Basis.sourced, source_ids=["S1"])
    assert json.loads(item.model_dump_json())["basis"] == "sourced"


@pytest.mark.parametrize("source_ids", [[], ["   "], [""]])
def test_sourced_item_without_a_source_is_rejected(source_ids: list[str]) -> None:
    with pytest.raises(ValidationError, match="needs at least one source id"):
        LabeledItem(text="Demand is rising", basis="sourced", source_ids=source_ids)


@pytest.mark.parametrize("basis", ["assumption", "ai_interpretation", "user_provided"])
def test_non_sourced_items_may_have_no_source(basis: str) -> None:
    assert LabeledItem(text="Founders say farmers want this", basis=basis).source_ids == []


def test_labeled_item_rejects_empty_text_and_unknown_basis() -> None:
    with pytest.raises(ValidationError):
        LabeledItem(text="   ", basis="assumption")
    with pytest.raises(ValidationError):
        LabeledItem(text="Demand is rising", basis="guess")


def test_quant_estimate_accepts_each_status_and_null_value() -> None:
    assert set(QUANT_STATUSES) == {"sourced", "estimate_needs_verification", "unavailable"}
    for status in QUANT_STATUSES:
        assert QuantEstimate(value=None, status=status).value is None
    sized = QuantEstimate(value="USD 1.8 billion", status="sourced", source_ids=["S1"], note="2025")
    assert sized.note == "2025"


def test_quant_estimate_rejects_an_unknown_status() -> None:
    with pytest.raises(ValidationError):
        QuantEstimate(value="USD 1 billion", status="guessed")


def test_source_ref_needs_an_id() -> None:
    assert SourceRef(id="S2", title="Report", url="https://x.example").id == "S2"
    with pytest.raises(ValidationError):
        SourceRef(id=" ", title="Report", url="https://x.example")


def test_evidence_item_limits_snippet_length() -> None:
    EvidenceItem(id="S1", title="t", url="https://x.example", snippet="s" * SNIPPET_MAX, section_label="L")
    with pytest.raises(ValidationError):
        EvidenceItem(id="S1", title="t", url="https://x.example", snippet="s" * (SNIPPET_MAX + 1), section_label="L")
    assert EvidenceItem(id="S0", title="t", snippet="s", section_label="L").url == ""


def test_basis_prints_as_its_value_in_str_and_f_strings() -> None:
    for member in Basis:
        assert str(member) == member.value
        assert f"{member}" == member.value
        assert "{}".format(member) == member.value
    assert f"Basis: {Basis.ai_interpretation}" == "Basis: ai_interpretation"
    assert format(Basis.sourced, ">10") == "   sourced"
    assert Basis.sourced == "sourced" and Basis("sourced") is Basis.sourced


# --- Task 1 scope fixes ----------------------------------------------------------------------


def test_market_figure_adds_a_scope_and_quant_estimate_is_unchanged_for_task_2() -> None:
    assert issubclass(MarketFigure, QuantEstimate)
    assert set(QuantEstimate.model_fields) == {"value", "status", "source_ids", "note"}
    assert set(MarketFigure.model_fields) == {"value", "status", "source_ids", "note", "scope"}
    assert set(MARKET_SCOPES) == {"idea_market", "broader_market"}
    assert MarketFigure(status="unavailable").scope is None
    for scope in MARKET_SCOPES:
        assert MarketFigure(value="USD 1 billion", status="sourced", source_ids=["S1"], scope=scope).scope == scope
    with pytest.raises(ValidationError):
        MarketFigure(status="unavailable", scope="global")


def test_tam_sam_som_and_broader_markets_use_market_figures() -> None:
    assert all(MarketSize.model_fields[name].annotation is MarketFigure for name in ("tam", "sam", "som"))
    draft = MarketOpportunityDraft(**json.loads(market_reply()))
    assert draft.broader_markets == []
    assert isinstance(draft.market_size.tam, MarketFigure) and draft.market_size.tam.scope == "idea_market"
    assert draft.market_size.sam.scope is None


# --- Task 2: Competitor Analysis schemas ------------------------------------------------------


def test_competitor_enums_follow_section_8_1() -> None:
    from models.schemas import CELL_STATUSES, COMPETITOR_BASES, COMPETITOR_TYPES, GAP_CONFIDENCES, INFO_COMPLETENESS

    assert COMPETITOR_TYPES == ("direct", "indirect", "emerging")
    assert COMPETITOR_BASES == ("sourced", "user_provided")
    assert INFO_COMPLETENESS == ("complete", "partial", "minimal")
    assert CELL_STATUSES == ("evidence_found", "no_evidence_found", "unclear")
    assert GAP_CONFIDENCES == ("low", "medium")


def test_a_draft_competitor_may_lack_a_type_but_a_result_competitor_may_not() -> None:
    from models.schemas import Competitor, CompetitorDraft

    draft = CompetitorDraft(name="LeafDoc")
    assert (draft.type, draft.relevance_note, draft.basis) == (None, "", "sourced")
    assert isinstance(draft.pricing_model, QuantEstimate) and draft.pricing_model.status == "unavailable"
    with pytest.raises(ValidationError):
        Competitor(name="LeafDoc", relevance_note="Same job.", info_completeness="minimal")
    with pytest.raises(ValidationError):
        Competitor(name="LeafDoc", type="direct", relevance_note=" ", info_completeness="minimal")
    with pytest.raises(ValidationError):
        Competitor(name="LeafDoc", type="rival", relevance_note="Same job.", info_completeness="minimal")


def test_a_gap_hypothesis_is_never_above_medium_in_the_result() -> None:
    from models.schemas import MarketGap, MarketGapDraft

    assert MarketGapDraft(description="Gap", basis="ai_interpretation", confidence="high").confidence == "high"
    with pytest.raises(ValidationError):
        MarketGap(description="Gap", basis="ai_interpretation", confidence="high", caveat="c")
    with pytest.raises(ValidationError):
        MarketGap(description="Gap", basis="ai_interpretation", confidence="low", caveat=" ")


def test_a_competitor_result_needs_at_least_one_competitor() -> None:
    from models.schemas import Comparison, CompetitorAnalysisResult, DataQuality

    with pytest.raises(ValidationError):
        CompetitorAnalysisResult(competitors=[], comparison=Comparison(), data_quality=DataQuality(evidence_level="limited"))


def test_candidates_and_cells_accept_only_the_listed_values() -> None:
    from models.schemas import CandidateList, ComparisonCell

    listed = CandidateList(candidates=[{"name": "Plantix", "type": "direct", "source_ids": ["S1"]}])
    assert listed.candidates[0].basis == "sourced"
    with pytest.raises(ValidationError):
        CandidateList(candidates=[{"name": "Plantix", "type": "direct", "basis": "guessed"}])
    with pytest.raises(ValidationError):
        ComparisonCell(feature="Photo diagnosis", status="maybe")

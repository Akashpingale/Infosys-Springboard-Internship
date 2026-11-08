"""Task 3 UI (KIRO_PROMPT_M2.md Section 9.3): the display helpers, the backend call with the
analysis stages, and the Streamlit page itself rendered headless with Streamlit's AppTest.

The page is rendered from a result stored in the session, so no backend, LLM or search runs.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import orchestrator
from agents.integrity import COMPETITOR_CAVEAT, MARKET_CAVEAT
from frontend import analysis_views as views
from frontend import api_client
from frontend.api_client import validate_idea
from models.schemas import (
    Basis,
    ComparisonCell,
    LabeledItem,
    MarketFigure,
    MarketGap,
    PipelineResult,
    SourceRef,
    StageError,
)
from tests.fakes import VALID_EXTRACTION, FakeHTTPResponse, make_sequence
from tests.pipeline_fakes import PIPELINE_SUBMISSION, use_full_pipeline

APP = Path(__file__).resolve().parent.parent / "frontend" / "app.py"
RESULT_KEY = "pipeline_result"
MILESTONE_1_RESULT = {
    "status": "complete",
    "idea": VALID_EXTRACTION,
    "search": {"sections": [], "total_results": 0, "queries_failed": 0},
    "warnings": [],
    "errors": [],
    "timings": {"extraction": 1.0, "search": 2.0, "total": 3.0},
}


@pytest.fixture
def full_result(monkeypatch: pytest.MonkeyPatch) -> PipelineResult:
    """A real four-stage result, produced by the pipeline with the LLM and searches faked."""
    use_full_pipeline(monkeypatch)
    result = orchestrator.run_pipeline(PIPELINE_SUBMISSION, orchestrator.FULL_STAGES)
    assert result.status == "complete" and result.market is not None and result.competitors is not None
    return result


def render(result: PipelineResult) -> AppTest:
    page = AppTest.from_file(str(APP), default_timeout=60)
    page.session_state[RESULT_KEY] = result
    page.run()
    assert not page.exception, [str(exception.value) for exception in page.exception]
    return page


def values(elements) -> list[str]:
    return [element.value for element in elements]


def joined(elements) -> str:
    return "\n".join(values(elements))


# --- display helpers --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("basis", "text"),
    [
        (Basis.sourced, "Sourced"),
        ("assumption", "Assumption"),
        (Basis.ai_interpretation, "AI interpretation"),
        ("user_provided", "User provided"),
    ],
)
def test_every_basis_is_written_out_in_words(basis: object, text: str) -> None:
    assert views.basis_text(basis) == text


def test_an_item_line_shows_its_basis_and_the_ids_it_cites() -> None:
    sourced = LabeledItem(text="Farmers lose crops", basis="sourced", source_ids=["S1", " S3 "])
    assumed = LabeledItem(text="Cooperatives would pay", basis="assumption")
    assert views.item_line(sourced) == "Farmers lose crops (Sourced: S1, S3)"
    assert views.item_line(assumed) == "Cooperatives would pay (Assumption)"


def test_an_unknown_market_figure_is_shown_as_not_available(full_result: PipelineResult) -> None:
    rows = views.market_size_rows(full_result.market)
    assert [row["Figure"] for row in rows] == ["TAM", "SAM", "SOM"]
    assert rows[0] == {
        "Figure": "TAM",
        "Value": "USD 1.8 billion",
        "Status": "Sourced",
        "Sources": "S1",
        "Note": "AI crop disease detection market, 2025",
    }
    assert rows[1]["Value"] == views.NOT_AVAILABLE and rows[1]["Status"] == "Unavailable"
    assert rows[2]["Sources"] == views.NO_IDS


def test_broader_market_figures_are_labelled_as_such(full_result: PipelineResult) -> None:
    figure = MarketFigure(
        value="USD 31.9 billion",
        status="sourced",
        source_ids=["S1"],
        note="Global agritech, 2025",
        scope="broader_market",
    )
    market = full_result.market.model_copy(update={"broader_markets": [figure]})
    assert views.broader_market_rows(market) == [
        {"Figure": "Broader market", "Value": "USD 31.9 billion", "Status": "Sourced", "Sources": "S1", "Note": "Global agritech, 2025"}
    ]
    assert views.broader_market_rows(full_result.market) == []


def test_an_estimate_is_flagged_as_needing_verification() -> None:
    figure = MarketFigure(value="USD 5 million", status="estimate_needs_verification", source_ids=["S0"])
    assert views.figure_row("SAM", figure)["Status"] == "Estimate, needs verification"


def test_sources_are_markdown_links_in_evidence_order() -> None:
    sources = [
        SourceRef(id="S1", title="Crop AI market report", url="https://reports.example/crop-ai-market"),
        SourceRef(id="S4", title="[Breaking] CropSense", url="https://news.example/cropsense-launch"),
        SourceRef(id="S5", title="", url="https://farmers.example/survey"),
    ]
    assert views.source_lines(sources) == [
        "S1. [Crop AI market report](https://reports.example/crop-ai-market)",
        "S4. [(Breaking) CropSense](https://news.example/cropsense-launch)",
        "S5. [https://farmers.example/survey](https://farmers.example/survey)",
    ]


def test_competitors_are_grouped_by_type_with_direct_first(full_result: PipelineResult) -> None:
    groups = views.competitor_groups(full_result.competitors)
    assert [(heading, [c.name for c in members]) for heading, members in groups] == [
        ("Direct competitors", ["Plantix", "LeafDoc"]),
        ("Indirect competitors and substitutes", ["Fasal", "Kisan call centres"]),
        ("Emerging competitors", ["CropSense"]),
    ]


def test_an_empty_competitor_group_is_left_out(full_result: PipelineResult) -> None:
    direct_only = full_result.competitors.model_copy(
        update={"competitors": [c for c in full_result.competitors.competitors if c.type == "direct"]}
    )
    assert [heading for heading, _ in views.competitor_groups(direct_only)] == ["Direct competitors"]


def test_competitor_facts_never_fill_in_what_the_evidence_did_not_give(full_result: PipelineResult) -> None:
    by_name = {c.name: dict(views.competitor_facts(c)) for c in full_result.competitors.competitors}
    leafdoc, fasal = by_name["LeafDoc"], by_name["Fasal"]

    assert leafdoc["Basis"] == "User provided"
    assert leafdoc["Value proposition"] == views.NOT_AVAILABLE
    assert fasal["Pricing"] == "Not available (Unavailable)"
    assert by_name["Plantix"]["Basis"] == "Sourced"
    assert by_name["Plantix"]["Pricing"].endswith("(Sourced: S5)")


def test_the_comparison_table_has_one_column_per_feature_and_words_for_each_cell(
    full_result: PipelineResult,
) -> None:
    analysis = full_result.competitors
    rows = views.comparison_rows(analysis)

    assert [row["Competitor"] for row in rows] == [row.competitor for row in analysis.comparison.rows]
    assert all(list(row) == ["Competitor", *analysis.comparison.features] for row in rows)
    allowed = set(views.CELL_TEXT.values())
    assert all(cell.split(" (")[0] in allowed for row in rows for key, cell in row.items() if key != "Competitor")


def test_a_missing_or_cited_cell_is_described_in_words() -> None:
    assert views.cell_text(None) == "Unclear"
    assert views.cell_text(ComparisonCell(feature="Expert chat", status="evidence_found", source_ids=["S4"])) == "Evidence found (S4)"
    assert views.cell_text(ComparisonCell(feature="Expert chat", status="no_evidence_found")) == "No evidence found"


def test_feature_coverage_is_shown_out_of_the_competitor_count(full_result: PipelineResult) -> None:
    analysis = full_result.competitors
    rows = views.coverage_rows(analysis)
    total = len(analysis.competitors)
    assert [row["Feature"] for row in rows] == [c.feature for c in analysis.comparison.feature_coverage]
    assert all(row["Competitors with evidence"].endswith(f" of {total}") for row in rows)


def test_a_gap_is_shown_as_a_hypothesis_with_its_confidence_and_basis() -> None:
    gap = MarketGap(
        description="Few competitors show treatment advice",
        related_features=["Treatment advice"],
        basis="ai_interpretation",
        source_ids=["S6"],
        confidence="medium",
        caveat=COMPETITOR_CAVEAT,
    )
    assert views.gap_line(gap) == (
        "Few competitors show treatment advice "
        "(Medium confidence; AI interpretation; related features: Treatment advice; sources: S6)"
    )


@pytest.mark.parametrize(
    ("stage", "label"),
    [
        ("extraction", "extraction"),
        ("search", "search"),
        ("total", "total"),
        ("market_opportunity", "market opportunity"),
        ("competitor_analysis", "competitor analysis"),
    ],
)
def test_stage_labels_keep_the_milestone_1_names(stage: str, label: str) -> None:
    assert views.stage_label(stage) == label


# --- the backend call -------------------------------------------------------------------------


def use_fake_post(monkeypatch: pytest.MonkeyPatch, body: dict):
    fake = make_sequence(FakeHTTPResponse(200, body))
    monkeypatch.setattr(api_client.requests, "post", fake)
    return fake


def test_the_full_call_asks_for_the_analysis_and_waits_pipeline_timeout_s(
    monkeypatch: pytest.MonkeyPatch, full_result: PipelineResult
) -> None:
    fake = use_fake_post(monkeypatch, full_result.model_dump(mode="json"))
    result = validate_idea(PIPELINE_SUBMISSION, url="http://localhost:8000", include_analysis=True)

    args, kwargs = fake.calls[0]
    assert args[0] == "http://localhost:8000/api/validate"
    assert kwargs["params"] == {"include_analysis": "true"}
    assert kwargs["timeout"] == api_client.pipeline_timeout_s() == 180
    assert result == full_result


@pytest.mark.parametrize(("raw", "expected"), [("240", 240.0), ("abc", 180.0), ("-5", 180.0)])
def test_pipeline_timeout_s_comes_from_the_settings(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: float
) -> None:
    monkeypatch.setenv("PIPELINE_TIMEOUT_S", raw)
    fake = use_fake_post(monkeypatch, MILESTONE_1_RESULT)
    validate_idea(PIPELINE_SUBMISSION, include_analysis=True)
    assert fake.calls[0][1]["timeout"] == expected


def test_an_explicit_timeout_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, MILESTONE_1_RESULT)
    validate_idea(PIPELINE_SUBMISSION, timeout=12.5, include_analysis=True)
    assert fake.calls[0][1]["timeout"] == 12.5


def test_the_milestone_1_call_sends_no_parameter_and_keeps_its_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, MILESTONE_1_RESULT)
    result = validate_idea(PIPELINE_SUBMISSION)
    assert fake.calls[0][1]["params"] is None
    assert fake.calls[0][1]["timeout"] == api_client.REQUEST_TIMEOUT_S
    assert result.market is None and result.competitors is None


# --- the Streamlit page -----------------------------------------------------------------------


def test_the_page_shows_both_new_sections_after_the_milestone_1_sections(full_result: PipelineResult) -> None:
    page = render(full_result)
    assert values(page.subheader) == [
        "What the system understood",
        "Market and competitor research",
        "Market opportunity",
        "Competitors",
    ]
    assert values(page.success) == ["**Status: Complete.** Your idea was structured and researched."]


def test_the_page_writes_every_basis_as_text(full_result: PipelineResult) -> None:
    text = joined(render(full_result).markdown)
    for expected in ("(Sourced: S5)", "(AI interpretation: S2)", "(Assumption)", "Basis: User provided"):
        assert expected in text, expected


def test_the_page_shows_the_market_size_table_with_status_text(full_result: PipelineResult) -> None:
    tables = [element.value for element in render(full_result).dataframe]
    market_size = tables[0]
    assert list(market_size.columns) == ["Figure", "Value", "Status", "Sources", "Note"]
    assert market_size["Value"].tolist() == ["USD 1.8 billion", "Not available", "Not available"]
    assert market_size["Status"].tolist() == ["Sourced", "Unavailable", "Unavailable"]


def test_the_page_groups_competitors_and_shows_the_comparison(full_result: PipelineResult) -> None:
    page = render(full_result)
    labels = [expander.label for expander in page.expander]
    for expected in (
        "Direct competitors (2)",
        "Indirect competitors and substitutes (2)",
        "Emerging competitors (1)",
        "Feature comparison",
        "Market gaps and differentiation",
    ):
        assert expected in labels, expected

    tables = [element.value for element in page.dataframe]
    comparison = next(table for table in tables if "Competitor" in table.columns)
    assert comparison["Competitor"].tolist() == [row.competitor for row in full_result.competitors.comparison.rows]
    assert any("Competitors with evidence" in table.columns for table in tables)


def test_the_page_shows_gaps_with_their_caveat_and_the_fixed_caveats(full_result: PipelineResult) -> None:
    page = render(full_result)
    captions = values(page.caption)
    assert full_result.competitors.market_gaps
    assert captions.count(COMPETITOR_CAVEAT) == len(full_result.competitors.market_gaps) + 1
    assert MARKET_CAVEAT in captions
    assert any("confidence" in line for line in values(page.markdown))


def test_the_page_shows_sources_as_links(full_result: PipelineResult) -> None:
    text = joined(render(full_result).markdown)
    assert "S1. [Crop AI market report](https://reports.example/crop-ai-market)" in text
    assert "[website](https://plantix.example)" in text


def test_missing_sections_get_a_friendly_message(full_result: PipelineResult) -> None:
    partial = full_result.model_copy(
        update={
            "status": "partial",
            "market": None,
            "competitors": None,
            "warnings": ["Market opportunity: skipped because the web search found no usable results."],
        }
    )
    page = render(partial)
    infos = joined(page.info)
    assert "No market opportunity analysis is available for this run." in infos
    assert "No competitor analysis is available for this run." in infos
    assert "Market opportunity: skipped because the web search found no usable results." in values(page.warning)
    assert "What the system understood" in values(page.subheader)
    assert not list(page.dataframe), "no table is drawn for a missing analysis"


def test_a_milestone_1_result_still_renders() -> None:
    page = render(PipelineResult.model_validate(MILESTONE_1_RESULT))
    assert values(page.subheader) == [
        "What the system understood",
        "Market and competitor research",
        "Market opportunity",
        "Competitors",
    ]
    assert "No market opportunity analysis is available for this run." in joined(page.info)


def test_a_failed_run_shows_no_analysis_sections() -> None:
    failed = PipelineResult(
        status="failed",
        errors=[StageError(stage="extraction", code="llm_not_configured", message="The AI service is not configured.")],
        timings={"extraction": 0.1, "total": 0.1},
    )
    page = render(failed)
    assert values(page.subheader) == []
    assert values(page.error) == [
        "**Status: Failed.** We could not process your idea. Details are below.",
        "The extraction step failed: The AI service is not configured.",
    ]


def test_analysis_stage_errors_and_timings_use_readable_names(full_result: PipelineResult) -> None:
    errored = full_result.model_copy(
        update={
            "status": "partial",
            "market": None,
            "errors": [StageError(stage="market_opportunity", code="llm_api_error", message="The AI service is busy right now.")],
            "timings": {"extraction": 1.0, "search": 2.0, "market_opportunity": 3.0, "competitor_analysis": 4.0, "total": 10.0},
        }
    )
    page = render(errored)
    assert "The market opportunity step failed: The AI service is busy right now." in values(page.error)
    assert (
        "Time taken: extraction 1.0s, search 2.0s, market opportunity 3.0s, competitor analysis 4.0s, total 10.0s"
        in values(page.caption)
    )

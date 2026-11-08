"""Plain-language quality notes (KIRO_UI_UPGRADE_SPEC.md Sections 6.7 and 10.3).

The rule that matters: `message` is for the founder, so it never carries a field path, an index or
an evidence id, and the technical text stays in `detail`. The three rewrites in Section 6.7 are
pinned word for word; every other warning the agents can raise must still produce a clean message.
"""

import json
from pathlib import Path

import pytest

from agents.notices import STAGE_TITLES, build_notices, leaks, notice_for_error, notice_for_warning
from models.schemas import NOTICE_SEVERITIES, PipelineResult, StageError
from orchestrator import STAGE_COMPETITOR, STAGE_EXTRACTION, STAGE_MARKET, STAGE_SEARCH

RUNS = Path(__file__).resolve().parent.parent / "docs" / "test_runs_m2"

# Section 6.7, the three rewrites, with the exact wording the specification gives.
REWRITES = (
    (
        "Market opportunity: market_demand.demand_evidence[1]: this sourced claim adds a conclusion "
        "('indicate') that its cited sources do not state, so it is now an AI interpretation",
        "One demand claim went further than its sources say, so it is marked as an AI interpretation.",
    ),
    (
        "Market opportunity: broader_markets[0]: the figure does not appear with the same magnitude and unit "
        "in its cited sources, so it needs verification",
        "A market figure could not be matched to its source text. Treat it as an estimate and verify it.",
    ),
    (
        "Market opportunity: segments[1].pain_points[0]: it is not about the problem this idea solves, "
        "so it was removed",
        "One pain point was removed because it was not about the problem your idea solves.",
    ),
)


@pytest.mark.parametrize(("warning", "expected"), REWRITES, ids=["conclusion", "figure", "pain_point"])
def test_the_three_specified_rewrites_are_exact(warning: str, expected: str) -> None:
    notice = notice_for_warning(warning)

    assert notice.message == expected
    assert notice.detail == warning, "the technical text stays available for developers"
    assert notice.stage == STAGE_MARKET and notice.severity == "info"


@pytest.mark.parametrize(
    ("warning", "expected_stage", "contains"),
    [
        ("Competitor analysis: competitors[0]: removed 'Plantix'; the founder did not name it in the submission",
         STAGE_COMPETITOR, "Plantix was removed"),
        ("Competitor analysis: competitors[2]: removed 'AgroGhost'; it is not named in its cited sources",
         STAGE_COMPETITOR, "its sources do not name it"),
        ("Competitor analysis: competitors[0].strengths[0]: removed strength 'Massive scale.'; it had no valid source",
         STAGE_COMPETITOR, "competitor strength was removed"),
        ("Competitor analysis: competitors: merged a duplicate 'Khatabook Pvt' into 'Khatabook'",
         STAGE_COMPETITOR, "merged into one"),
        ("Competitor analysis: competitors: dropped 2 with no type or relevance note",
         STAGE_COMPETITOR, "2 search results were not counted"),
        ("Competitor analysis: market_gaps[1]: confidence lowered from high to medium; a gap is a hypothesis",
         STAGE_COMPETITOR, "medium confidence"),
        ("Market opportunity: priority_segment: it does not match any segment, so no priority segment is shown",
         STAGE_MARKET, "No priority segment is shown"),
        ("Market opportunity: market_size.tam: USD 9 billion is marked as a broader market, so it was moved to "
         "broader_markets and the TAM is unavailable", STAGE_MARKET, "TAM"),
        ("Market and competitor research is not available, so only the structured idea is shown.",
         STAGE_SEARCH, "only the structured idea"),
        ("3 of 4 web searches failed, so some sections are empty.", STAGE_SEARCH, "3 of 4 web searches failed"),
        ("Market opportunity: skipped because the web search found no usable results.",
         STAGE_MARKET, "Analysing the market was skipped"),
        ("Competitor analysis: skipped because the request reached its time limit.",
         STAGE_COMPETITOR, "reached its time limit"),
    ],
)
def test_other_warnings_are_rewritten_for_the_founder(warning: str, expected_stage: str, contains: str) -> None:
    notice = notice_for_warning(warning)

    assert contains in notice.message
    assert notice.stage == expected_stage
    assert not leaks(notice.message), notice.message


def test_an_unknown_wording_gets_a_general_message_rather_than_the_field_path() -> None:
    notice = notice_for_warning("Market opportunity: segments[3].pain_points[2]: some future check changed this")

    assert notice.code == "quality_adjusted"
    assert notice.message == (
        "A quality check adjusted part of the market analysis. Open the details to see what changed."
    )
    assert not leaks(notice.message)
    assert notice.detail is not None and "segments[3]" in notice.detail


def test_a_stage_error_becomes_a_notice_that_names_the_step() -> None:
    error = StageError(stage=STAGE_MARKET, code="llm_api_error", message="The AI service is busy right now.")

    notice = notice_for_error(error)

    assert notice.message == "Analysing the market did not finish. The AI service is busy right now."
    assert (notice.severity, notice.code, notice.stage) == ("error", "llm_api_error", STAGE_MARKET)
    assert notice.detail == "llm_api_error: The AI service is busy right now."


def test_a_cancelled_stage_is_a_warning_not_an_error() -> None:
    error = StageError(stage=STAGE_COMPETITOR, code="run_cancelled", message="The run was cancelled.")
    assert notice_for_error(error).severity == "warning"


def test_errors_come_before_warnings_and_nothing_is_dropped() -> None:
    warnings = ["Market opportunity: segments[0]: it is not about the problem this idea solves, so it was removed",
                "3 of 4 web searches failed, so some sections are empty."]
    errors = [StageError(stage=STAGE_COMPETITOR, code="llm_api_error", message="The AI service is busy.")]

    notices = build_notices(warnings, errors)

    assert len(notices) == 3, "one notice per warning and per error, so a count stays meaningful"
    assert [notice.severity for notice in notices] == ["error", "info", "warning"]
    assert all(notice.severity in NOTICE_SEVERITIES for notice in notices)


def test_no_notice_is_produced_for_a_clean_run() -> None:
    assert build_notices([], []) == []


def test_the_stage_titles_are_the_specified_ones() -> None:
    assert STAGE_TITLES == {
        STAGE_EXTRACTION: "Understanding your idea",
        STAGE_SEARCH: "Searching the web",
        STAGE_MARKET: "Analysing the market",
        STAGE_COMPETITOR: "Comparing competitors",
    }


@pytest.mark.parametrize("name", ["agritech", "fintech_cashflow", "foodtech_surplus"])
def test_every_warning_from_the_saved_live_runs_reads_plainly(name: str) -> None:
    """The saved results are read as test data only; nothing is called."""
    result = PipelineResult.model_validate(json.loads((RUNS / f"{name}.json").read_text(encoding="utf-8")))
    assert result.warnings, "the saved run carries warnings to rewrite"

    notices = build_notices(result.warnings, result.errors)

    assert len(notices) == len(result.warnings) + len(result.errors)
    for notice in notices:
        assert notice.message and notice.message[0].isupper() and notice.message.endswith(".")
        assert not leaks(notice.message), notice.message
        assert "S0" not in notice.message and "data_quality" not in notice.message


def test_a_message_that_would_leak_a_path_is_caught_by_the_guard() -> None:
    """The guard that protects every rule: anything technical falls back to the general message."""
    assert leaks("market_demand.demand_evidence[1] changed")
    assert leaks("the claim cites S10")
    assert leaks("segments[0] was removed")
    assert not leaks("One demand claim went further than its sources say.")

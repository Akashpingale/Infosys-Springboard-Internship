"""Task 3 (KIRO_PROMPT_M2.md Section 9): the four-stage pipeline, context passing, skip rules,
status rules and timings. Nothing touches the network.

The first tests replace the agents' entry points with call spies, to check the orchestration on its
own. The last ones run the real agents, with only the LLM and the searches faked.
"""

from dataclasses import dataclass
from typing import Any, Callable

import pytest

import orchestrator
from agents import competitor_analysis_agent as competitor_agent
from agents import market_opportunity_agent as market_agent
from agents.base import Agent, AgentContext
from agents.competitor_analysis_agent import CompetitorRun, competitor_evidence, market_context_for_competitors
from agents.integrity import COMPETITOR_CAVEAT, check_competitor_integrity, check_market_integrity
from agents.market_size import market_evidence
from models.schemas import CompetitorCandidate
from models.schemas import (
    Comparison,
    ComparisonCell,
    ComparisonRow,
    Competitor,
    CompetitorAnalysisResult,
    DataQuality,
    FeatureCoverage,
    MarketContext,
    MarketOpportunityResult,
    PipelineResult,
    SearchBundle,
    SearchResult,
    SearchSection,
    StageError,
)
from tests.fakes import make_sequence
from tests.m2_fakes import NO_MARKET_SIZE_RESULTS, analysis_draft, as_reply, candidate_draft
from tests.pipeline_fakes import (
    IDEA,
    MARKET_CONTEXT_LINE,
    MARKET_ONLY_TEXT,
    NO_MARKET_CONTEXT_LINE,
    PIPELINE_MARKET_REPLY,
    PIPELINE_SEARCH,
    PIPELINE_SUBMISSION,
    evidence_urls,
    use_full_pipeline,
)
from utils.errors import (
    AppError,
    InsufficientEvidenceError,
    LLMAPIError,
    LLMConfigError,
    LLMInvalidResponseError,
    SearchAPIError,
)

FULL = orchestrator.FULL_STAGES
MARKET = "market_opportunity"
COMPETITOR = "competitor_analysis"
FOUR_STAGES = ["extraction", "search", MARKET, COMPETITOR]
ALL_TIMINGS = {"extraction", "search", MARKET, COMPETITOR, "total"}
MILESTONE_1_TIMINGS = {"extraction", "search", "total"}
SKIP_MARKET_NO_SEARCH = "Market opportunity: skipped because the web search did not complete."
SKIP_COMPETITOR_NO_SEARCH = "Competitor analysis: skipped because the web search did not complete."
SKIP_MARKET_NO_EVIDENCE = "Market opportunity: skipped because the web search found no usable results."
SKIP_COMPETITOR_NO_EVIDENCE = "Competitor analysis: skipped because the web search found no usable results."

MARKET_RESULT = MarketOpportunityResult.model_validate(PIPELINE_MARKET_REPLY)
COMPETITOR_RESULT = CompetitorAnalysisResult(
    competitors=[
        Competitor(
            name="Plantix",
            type="direct",
            relevance_note="A photo-based crop disease diagnosis app.",
            source_ids=["S2"],
            info_completeness="partial",
        )
    ],
    comparison=Comparison(
        features=["Photo-based diagnosis"],
        rows=[
            ComparisonRow(
                competitor="Plantix",
                cells=[ComparisonCell(feature="Photo-based diagnosis", status="evidence_found", source_ids=["S2"])],
            )
        ],
        feature_coverage=[FeatureCoverage(feature="Photo-based diagnosis", competitors_with_evidence=1)],
    ),
    data_quality=DataQuality(evidence_level="limited"),
    caveats=[COMPETITOR_CAVEAT],
)

NOTHING_USABLE = SearchBundle(
    sections=[
        SearchSection(
            label="Market size and trends",
            query="q1",
            answer="A search summary with no source behind it.",
            error="No live results found for this query.",
        ),
        SearchSection(label="Competitors", query="q2", error="No live results found for this query."),
    ],
    total_results=0,
    queries_failed=0,
)
PARTLY_FAILED = PIPELINE_SEARCH.model_copy(
    update={
        "sections": [
            *PIPELINE_SEARCH.sections,
            SearchSection(label="Recent news and funding", query="q4", error="Web search is busy."),
        ],
        "queries_failed": 1,
    }
)


def competitor_run(warnings: list[str] | None = None) -> CompetitorRun:
    return CompetitorRun(COMPETITOR_RESULT, warnings or [], [], None, [])


@dataclass
class Spies:
    order: list[str]
    extract: Callable[..., Any]
    search: Callable[..., Any]
    market_search: Callable[..., Any]
    market: Callable[..., Any]
    competitor: Callable[..., Any]

    def analysis_calls(self) -> int:
        return len(self.market_search.calls) + len(self.market.calls) + len(self.competitor.calls)


def use_spies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    extraction: object = IDEA,
    search: object = PIPELINE_SEARCH,
    market_search: object = (None, []),
    market: object = (MARKET_RESULT, []),
    competitor: object = None,
) -> Spies:
    """Replace the stage functions and the agents' entry points with spies that record the call
    order. Exceptions are raised, values returned."""
    order: list[str] = []

    def spy(name: str, outcome: object) -> Callable[..., Any]:
        fake = make_sequence(outcome)

        def call(*args: Any, **kwargs: Any) -> Any:
            order.append(name)
            return fake(*args, **kwargs)

        call.calls = fake.calls  # type: ignore[attr-defined]
        return call

    spies = Spies(
        order=order,
        extract=spy("extraction", extraction),
        search=spy("search", search),
        market_search=spy("market targeted search", market_search),
        market=spy("market analysis", market),
        competitor=spy("competitor analysis", competitor_run() if competitor is None else competitor),
    )
    monkeypatch.setattr(orchestrator, "extract_idea", spies.extract)
    monkeypatch.setattr(orchestrator, "run_web_search", spies.search)
    monkeypatch.setattr(market_agent, "search_market_size", spies.market_search)
    monkeypatch.setattr(market_agent, "analyse_market", spies.market)
    monkeypatch.setattr(competitor_agent, "analyse_competitors", spies.competitor)
    return spies


def run_full() -> PipelineResult:
    return orchestrator.run_pipeline(PIPELINE_SUBMISSION, FULL)


def received_market_context(spies: Spies) -> object:
    (idea, search, submission, market_context), _ = spies.competitor.calls[0]
    assert idea is IDEA and search is PIPELINE_SEARCH and submission is PIPELINE_SUBMISSION
    return market_context


# --- the stage list -------------------------------------------------------------------------


def test_the_two_analysis_stages_are_appended_to_the_milestone_1_stages() -> None:
    assert [stage.name for stage in FULL] == FOUR_STAGES
    assert FULL[0] is orchestrator.STAGES[0] and FULL[1] is orchestrator.STAGES[1]
    assert [stage.name for stage in orchestrator.STAGES] == ["extraction", "search"]


def test_every_stage_satisfies_the_agent_protocol() -> None:
    for stage in FULL:
        assert isinstance(stage, Agent) and stage.name


def test_execution_order_is_extraction_search_market_then_competitor(monkeypatch: pytest.MonkeyPatch) -> None:
    spies = use_spies(monkeypatch)
    run_full()
    assert spies.order == [
        "extraction",
        "search",
        "market targeted search",
        "market analysis",
        "competitor analysis",
    ]


def test_the_default_pipeline_is_still_the_milestone_1_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    spies = use_spies(monkeypatch)
    run = orchestrator.run_pipeline(PIPELINE_SUBMISSION)

    assert spies.order == ["extraction", "search"] and spies.analysis_calls() == 0
    assert run.status == "complete" and run.market is None and run.competitors is None
    assert set(run.timings) == MILESTONE_1_TIMINGS and run.warnings == []


# --- complete -------------------------------------------------------------------------------


def test_all_four_stages_succeeding_gives_complete_with_every_output(monkeypatch: pytest.MonkeyPatch) -> None:
    use_spies(monkeypatch)
    run = run_full()

    assert run.status == "complete"
    assert run.idea is IDEA and run.search is PIPELINE_SEARCH
    assert run.market is MARKET_RESULT and run.competitors is COMPETITOR_RESULT
    assert run.errors == [] and run.warnings == []


def test_repair_warnings_keep_the_run_complete_and_name_their_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    use_spies(
        monkeypatch,
        market_search=(None, ["a targeted search failed"]),
        market=(MARKET_RESULT, ["an unknown source id was dropped"]),
        competitor=competitor_run(["a website was removed"]),
    )
    run = run_full()

    assert run.status == "complete"
    assert run.warnings == [
        "Market opportunity: a targeted search failed",
        "Market opportunity: an unknown source id was dropped",
        "Competitor analysis: a website was removed",
    ]


def test_timings_exist_for_the_new_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    use_spies(monkeypatch)
    timings = run_full().timings

    assert set(timings) == ALL_TIMINGS
    assert all(value >= 0 for value in timings.values())
    assert timings["total"] >= max(timings[MARKET], timings[COMPETITOR])


def test_the_full_result_round_trips_through_json(monkeypatch: pytest.MonkeyPatch) -> None:
    use_spies(monkeypatch)
    run = run_full()
    assert PipelineResult.model_validate_json(run.model_dump_json()) == run


# --- context passing (Section 9.1.4) --------------------------------------------------------


def test_the_competitor_stage_gets_the_compact_market_context_when_the_market_stage_succeeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spies = use_spies(monkeypatch)
    run_full()

    context = received_market_context(spies)
    assert isinstance(context, MarketContext) and not isinstance(context, MarketOpportunityResult)
    assert context == market_context_for_competitors(MARKET_RESULT)
    assert context.model_dump() == {
        "market_category": "AI crop disease detection",
        "segment_names": ["Smallholder farmers", "Farming cooperatives"],
        "priority_segment": "Smallholder farmers",
        "priority_rationale": "They feel the crop losses most directly.",
        "trend_titles": ["Drone-based disease scouting"],
    }


def test_the_competitor_stage_gets_no_market_context_when_the_market_stage_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spies = use_spies(monkeypatch, market=LLMAPIError("The AI service is busy right now."))
    run = run_full()

    assert received_market_context(spies) is None
    assert run.status == "partial"
    assert run.market is None and run.competitors is COMPETITOR_RESULT
    assert run.errors == [StageError(stage=MARKET, code="llm_api_error", message="The AI service is busy right now.")]


# --- partial: the analysis stages (Section 9.2) ---------------------------------------------


def test_a_competitor_failure_keeps_the_market_result(monkeypatch: pytest.MonkeyPatch) -> None:
    use_spies(monkeypatch, competitor=InsufficientEvidenceError("No competitor could be confirmed."))
    run = run_full()

    assert run.status == "partial"
    assert run.idea is IDEA and run.search is PIPELINE_SEARCH and run.market is MARKET_RESULT
    assert run.competitors is None
    assert [(error.stage, error.code) for error in run.errors] == [(COMPETITOR, "insufficient_evidence")]
    assert set(run.timings) == ALL_TIMINGS


def test_both_analysis_failures_keep_the_idea_and_the_search(monkeypatch: pytest.MonkeyPatch) -> None:
    use_spies(monkeypatch, market=LLMInvalidResponseError(), competitor=LLMAPIError())
    run = run_full()

    assert run.status == "partial"
    assert run.idea is IDEA and run.search is PIPELINE_SEARCH
    assert run.market is None and run.competitors is None
    assert [(error.stage, error.code) for error in run.errors] == [
        (MARKET, "llm_invalid_response"),
        (COMPETITOR, "llm_api_error"),
    ]
    assert run.warnings == []


def test_a_failed_analysis_stage_is_still_timed(monkeypatch: pytest.MonkeyPatch) -> None:
    use_spies(monkeypatch, market=LLMAPIError())
    assert set(run_full().timings) == ALL_TIMINGS


def test_an_unexpected_exception_in_the_market_stage_becomes_a_safe_stage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spies = use_spies(monkeypatch, market=RuntimeError("provider internals test-llm-key"))
    run = run_full()

    assert run.status == "partial"
    assert run.errors == [StageError(stage=MARKET, code=AppError.code, message=AppError.default_message)]
    assert received_market_context(spies) is None and run.competitors is COMPETITOR_RESULT
    assert "provider internals" not in run.model_dump_json() and "test-llm-key" not in run.model_dump_json()


def test_an_unexpected_exception_in_the_competitor_stage_keeps_the_market_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_spies(monkeypatch, competitor=KeyError("internal detail"))
    run = run_full()

    assert run.status == "partial" and run.market is MARKET_RESULT and run.competitors is None
    assert run.errors == [StageError(stage=COMPETITOR, code=AppError.code, message=AppError.default_message)]
    assert "internal detail" not in run.model_dump_json()


def test_an_unexpected_exception_in_a_milestone_1_stage_is_still_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_spies(monkeypatch, extraction=RuntimeError("provider internals"))
    with pytest.raises(RuntimeError):
        run_full()


# --- failed and skipped ---------------------------------------------------------------------


def test_an_extraction_failure_is_failed_with_errors_only(monkeypatch: pytest.MonkeyPatch) -> None:
    spies = use_spies(monkeypatch, extraction=LLMConfigError())
    run = run_full()

    assert run.status == "failed"
    assert run.idea is None and run.search is None and run.market is None and run.competitors is None
    assert [(error.stage, error.code) for error in run.errors] == [("extraction", "llm_not_configured")]
    assert run.warnings == []
    assert set(run.timings) == {"extraction", "total"}
    assert spies.order == ["extraction"]


def test_a_search_failure_skips_both_analysis_stages_with_a_warning_each(monkeypatch: pytest.MonkeyPatch) -> None:
    spies = use_spies(monkeypatch, search=SearchAPIError("Web search could not be completed. Please try again."))
    run = run_full()

    assert run.status == "partial"
    assert run.idea is IDEA and run.search is None and run.market is None and run.competitors is None
    assert run.warnings == [
        orchestrator.WARNING_SEARCH_UNAVAILABLE,
        SKIP_MARKET_NO_SEARCH,
        SKIP_COMPETITOR_NO_SEARCH,
    ]
    assert [(error.stage, error.code) for error in run.errors] == [("search", "search_api_error")]
    assert spies.analysis_calls() == 0
    assert set(run.timings) == MILESTONE_1_TIMINGS


def test_zero_usable_evidence_skips_both_analysis_stages_without_any_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """The search summary S0 has no source URL, so a bundle with only a summary has no usable
    evidence (the same rule as the agents' own check)."""
    spies = use_spies(monkeypatch, search=NOTHING_USABLE)
    run = run_full()

    assert run.status == "partial"
    assert run.errors == []
    assert run.warnings == [SKIP_MARKET_NO_EVIDENCE, SKIP_COMPETITOR_NO_EVIDENCE]
    assert spies.analysis_calls() == 0
    assert run.search is NOTHING_USABLE and run.market is None and run.competitors is None
    assert set(run.timings) == MILESTONE_1_TIMINGS


def test_a_result_without_a_url_is_not_usable_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    no_url = SearchBundle(
        sections=[
            SearchSection(
                label="Competitors",
                query="q",
                results=[SearchResult(title="No link", url="", snippet="Plantix is a crop doctor app.")],
            )
        ],
        total_results=1,
        queries_failed=0,
    )
    spies = use_spies(monkeypatch, search=no_url)
    run = run_full()
    assert run.warnings == [SKIP_MARKET_NO_EVIDENCE, SKIP_COMPETITOR_NO_EVIDENCE] and spies.analysis_calls() == 0
    assert run.status == "partial" and run.errors == []


def test_a_partly_failed_search_still_runs_the_analysis_and_stays_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    use_spies(monkeypatch, search=PARTLY_FAILED)
    run = run_full()

    assert run.status == "partial", "the Milestone 1 rule for failed queries is kept"
    assert run.errors == []
    assert run.market is MARKET_RESULT and run.competitors is COMPETITOR_RESULT
    assert run.warnings == ["1 of 4 web searches failed, so some sections are empty."]


@pytest.mark.parametrize(
    "outcome",
    [
        {"search": SearchAPIError()},
        {"search": NOTHING_USABLE},
        {"market": LLMAPIError(), "competitor": InsufficientEvidenceError()},
    ],
    ids=["search failed", "no usable evidence", "both analyses failed"],
)
def test_no_placeholder_output_for_a_skipped_or_failed_stage(
    monkeypatch: pytest.MonkeyPatch, outcome: dict
) -> None:
    use_spies(monkeypatch, **outcome)
    body = run_full().model_dump(mode="json")
    assert body["market"] is None and body["competitors"] is None


# --- the real agents, with only the LLM and the searches faked ------------------------------


def record_integrity(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[list[str]]]:
    """Wrap both integrity checkers so the test can see what they returned inside the agents."""
    seen: dict[str, list[list[str]]] = {MARKET: [], COMPETITOR: []}
    for module, name, key in (
        (market_agent, "check_market_integrity", MARKET),
        (competitor_agent, "check_competitor_integrity", COMPETITOR),
    ):
        real = getattr(module, name)

        def wrapped(result: object, evidence: list, _real: Callable = real, _key: str = key) -> list[str]:
            violations = _real(result, evidence)
            seen[_key].append(violations)
            return violations

        monkeypatch.setattr(module, name, wrapped)
    return seen


def test_the_real_agents_complete_with_clean_integrity_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = use_full_pipeline(monkeypatch)
    seen = record_integrity(monkeypatch)
    run = run_full()

    assert run.status == "complete" and run.errors == []
    assert run.market is not None and run.competitors is not None
    assert seen == {MARKET: [[]], COMPETITOR: [[]]}
    assert run.market.market_size.tam.status == "sourced"
    assert {competitor.name for competitor in run.competitors.competitors} >= {"Plantix", "LeafDoc"}
    assert all(warning.startswith(("Market opportunity: ", "Competitor analysis: ")) for warning in run.warnings)
    assert len(fakes.market_llm.calls) == 1 and len(fakes.competitor_llm.calls) == 2


def test_every_url_from_the_real_agents_comes_from_the_search_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    run = run_full()
    assert run.market is not None and run.competitors is not None

    urls = evidence_urls(NO_MARKET_SIZE_RESULTS)
    cited = [source.url for source in [*run.market.sources, *run.competitors.sources]]
    assert cited and set(cited) <= urls
    websites = [competitor.website for competitor in run.competitors.competitors if competitor.website]
    assert websites and all(any(url.startswith(site) for url in urls) for site in websites)


def test_the_phase_c_prompt_carries_only_the_compact_market_context(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = use_full_pipeline(monkeypatch)
    run_full()

    prompt = fakes.phase_c_prompt()
    assert MARKET_CONTEXT_LINE in prompt
    assert not any(text in prompt for text in MARKET_ONLY_TEXT)


def test_a_market_llm_failure_leaves_the_phase_c_prompt_without_market_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = use_full_pipeline(monkeypatch, market_llm=(LLMAPIError("The AI service is busy right now."),))
    run = run_full()

    assert run.status == "partial" and run.market is None and run.competitors is not None
    assert [(error.stage, error.code) for error in run.errors] == [(MARKET, "llm_api_error")]
    assert NO_MARKET_CONTEXT_LINE in fakes.phase_c_prompt()


def test_a_thin_idea_is_a_stage_error_in_both_analysis_stages_without_any_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thin = (
        '{"idea_title": "...", "problem": "...", "solution": "???", "target_customers": ["..."], '
        '"industry": "!!!", "key_features": ["...", "???", "!!!"]}'
    )
    fakes = use_full_pipeline(monkeypatch, extraction=(thin,))
    run = run_full()

    assert run.status == "partial" and run.idea is not None
    assert [(error.stage, error.code) for error in run.errors] == [(MARKET, "invalid_input"), (COMPETITOR, "invalid_input")]
    assert fakes.analysis_calls() == 0


def test_llm_api_errors_in_both_analysis_stages_give_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = use_full_pipeline(monkeypatch, market_llm=(LLMAPIError(),), competitor_llm=(LLMAPIError(),))
    run = run_full()

    assert run.status == "partial" and run.idea is not None and run.search is PIPELINE_SEARCH
    assert [(error.stage, error.code) for error in run.errors] == [(MARKET, "llm_api_error"), (COMPETITOR, "llm_api_error")]
    assert run.market is None and run.competitors is None
    assert len(fakes.competitor_llm.calls) == 2, "Phase A falls back to the generic searches, then Phase C fails"


def test_an_unusable_market_reply_twice_is_a_stage_error_and_the_competitor_stage_still_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = use_full_pipeline(monkeypatch, market_llm=("not json", "still not json"))
    run = run_full()

    assert [(error.stage, error.code) for error in run.errors] == [(MARKET, "llm_invalid_response")]
    assert len(fakes.market_llm.calls) == 2, "one retry, then a stage error"
    assert run.status == "partial" and run.competitors is not None


def test_no_surviving_competitor_is_a_stage_error_that_keeps_the_market(monkeypatch: pytest.MonkeyPatch) -> None:
    empty = {**analysis_draft(), "competitors": [], "comparison": {"features": [], "rows": []}}
    use_full_pipeline(monkeypatch, competitor_llm=(as_reply(candidate_draft()), as_reply(empty)))
    run = run_full()

    assert run.status == "partial" and run.market is not None and run.competitors is None
    assert [(error.stage, error.code) for error in run.errors] == [(COMPETITOR, "insufficient_evidence")]


def test_a_failed_targeted_competitor_search_is_only_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch, competitor_search=(SearchAPIError("Web search is busy."),))
    run = run_full()

    assert run.status == "complete" and run.competitors is not None
    assert any(warning.startswith("Competitor analysis: ") and "failed" in warning for warning in run.warnings)


def test_each_stage_calls_its_services_once_in_the_full_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = use_full_pipeline(monkeypatch)
    run = run_full()

    (received_idea,), _ = fakes.search.calls[0]
    assert received_idea == IDEA and run.idea == IDEA
    assert len(fakes.extraction_llm.calls) == 1 and len(fakes.search.calls) == 1
    assert len(fakes.market_search.calls) == 1 and len(fakes.market_llm.calls) == 1
    assert len(fakes.competitor_search.calls) == 1 and len(fakes.competitor_llm.calls) == 2


# --- the audit fields the shared context carries (Section 9.1.2) ----------------------------
# scripts/run_agent.py rebuilds each agent's evidence from these fields, so a pipeline run must
# leave them populated, not just `market` and `competitors`.


class CaptureStage:
    """A stage that keeps the context it was handed, so a test can inspect it."""

    name = "capture"

    def __init__(self) -> None:
        self.context: AgentContext | None = None

    def run(self, context: AgentContext) -> AgentContext:
        self.context = context
        return context


def run_capturing(monkeypatch: pytest.MonkeyPatch, **outcomes) -> tuple[PipelineResult, AgentContext]:
    use_full_pipeline(monkeypatch, **outcomes)
    capture = CaptureStage()
    run = orchestrator.run_pipeline(PIPELINE_SUBMISSION, [*FULL, capture])
    assert capture.context is not None, "the capture stage ran"
    return run, capture.context


def test_the_context_carries_every_audit_field_after_a_full_run(monkeypatch: pytest.MonkeyPatch) -> None:
    run, context = run_capturing(monkeypatch)

    assert context.submission is PIPELINE_SUBMISSION and context.idea == IDEA
    assert context.search is PIPELINE_SEARCH
    assert context.market is run.market and context.competitors is run.competitors
    assert context.market_search is NO_MARKET_SIZE_RESULTS, "the market agent's own searches"
    assert isinstance(context.competitor_search, SearchBundle) and context.competitor_search.sections
    assert context.competitor_candidates and all(
        isinstance(candidate, CompetitorCandidate) for candidate in context.competitor_candidates
    )
    assert {candidate.name for candidate in context.competitor_candidates} >= {"Plantix", "LeafDoc"}


def test_each_agents_evidence_can_be_rebuilt_from_the_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """The audit path scripts/run_agent.py uses: every source the agents cited must reappear,
    with the same URL, in the evidence rebuilt from the context alone."""
    run, context = run_capturing(monkeypatch)
    assert run.market is not None and run.competitors is not None

    market_items = market_evidence(context.search, context.market_search, context.idea)
    competitor_items = competitor_evidence(
        context.search, context.competitor_search, context.competitor_candidates
    )
    for result, rebuilt in ((run.market, market_items), (run.competitors, competitor_items)):
        by_id = {item.id.upper(): item.url for item in rebuilt}
        assert result.sources, "the result cited something"
        for source in result.sources:
            assert by_id.get(source.id.upper()) == source.url, f"{source.id} rebuilt from the context"

    assert check_market_integrity(run.market, market_items) == []
    assert check_competitor_integrity(run.competitors, competitor_items) == []


def test_a_skipped_analysis_leaves_the_audit_fields_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _, context = run_capturing(monkeypatch, search=(SearchAPIError("Web search could not be completed."),))

    assert context.market is None and context.competitors is None
    assert context.market_search is None and context.competitor_search is None
    assert context.competitor_candidates == []


def test_a_failed_competitor_stage_still_leaves_the_market_audit_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    run, context = run_capturing(monkeypatch, competitor_llm=(LLMAPIError(),))

    assert run.status == "partial" and context.market is not None
    assert context.market_search is NO_MARKET_SIZE_RESULTS
    assert context.competitors is None







"""Orchestration: a plain function that runs the agents in order.

Milestone 1 runs two stages (STAGES): extraction, then web search. Milestone 2, Task 3 appends the
Market Opportunity and Competitor Analysis stages (FULL_STAGES). POST /api/validate runs the full
list when the client asks for the analysis, which the UI always does; without it the Milestone 1
pipeline runs unchanged. Milestone 3 adds the three strategy stages after them (STRATEGY_STAGES), or
on their own after a saved result (STRATEGY_ONLY_STAGES); only background runs that ask for strategy
use them (utils/run_manager.py).
"""

import logging
import time
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Sequence

from agents.base import Agent, AgentContext
from agents.competitor_analysis_agent import STAGE_COMPETITOR
from agents.competitor_analysis_agent import WARNING_PREFIX as COMPETITOR_LABEL
from agents.competitor_analysis_agent import CompetitorAnalysisAgent
from agents.derived import with_derived_fields
from agents.competitor_analysis_agent import PROMPT_VERSION as COMPETITOR_PROMPT_VERSION
from agents.evidence import build_evidence, sourced_items
from agents.extraction_agent import PROMPT_VERSION as EXTRACTION_PROMPT_VERSION
from agents.extraction_agent import extract_idea
from agents.extraction_agent import prompt_version as extraction_prompt_version
from agents.gtm_agent import PROMPT_VERSION as GTM_PROMPT_VERSION
from agents.gtm_agent import GtmAgent
from agents.market_opportunity_agent import PROMPT_VERSION as MARKET_PROMPT_VERSION
from agents.market_opportunity_agent import STAGE_MARKET
from agents.market_opportunity_agent import WARNING_PREFIX as MARKET_LABEL
from agents.market_opportunity_agent import MarketOpportunityAgent
from agents.mvp_agent import PROMPT_VERSION as MVP_PROMPT_VERSION
from agents.mvp_agent import MvpAgent
from agents.notices import STAGE_GTM, STAGE_MVP, STAGE_SWOT, STRATEGY_TITLES
from agents.swot_risk_agent import PROMPT_VERSION as SWOT_PROMPT_VERSION
from agents.swot_risk_agent import SwotRiskAgent
from agents.prompt_profile import prompt_version
from agents.query_profile import search_region
from agents.web_search_agent import run_web_search
from config import get_settings
from models.schemas import (
    ExtractedIdea,
    IdeaSubmission,
    PipelineResult,
    StageError,
    StageUsage,
    StrategyConstraints,
    Usage,
    Versions,
)
from utils.deadline import extra_time, stop_check, stop_requested, time_left, time_limit
from utils.errors import AppError, RunCancelledError
from utils.llm_client import output_token_limit
from utils.usage import UsageCounter, counting

logger = logging.getLogger(__name__)

STAGE_EXTRACTION = "extraction"
STAGE_SEARCH = "search"
TOTAL_KEY = "total"

WARNING_SEARCH_UNAVAILABLE = (
    "Market and competitor research is not available, so only the structured idea is shown."
)
SKIP_NO_SEARCH = "{label}: skipped because the web search did not complete."
SKIP_NO_EVIDENCE = "{label}: skipped because the web search found no usable results."
SKIP_NO_TIME = "{label}: skipped because the request reached its time limit."
SKIP_CANCELLED = "{label}: skipped because the run was cancelled."
# Labels for the Milestone 1 stages in such a warning; the analysis stages carry their own.
STAGE_LABELS = {STAGE_EXTRACTION: "Idea extraction", STAGE_SEARCH: "Web search"}
# Milestone 3 (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 5.2): a strategy stage needs the
# idea and at least one finished analysis.
SKIP_NO_ANALYSIS = "{label}: skipped because it needs at least one finished analysis."

# Stage events for an optional `on_event` callback (UI upgrade, KIRO_UI_UPGRADE_SPEC.md 10.2).
EVENT_STARTED = "started"
EVENT_FINISHED = "finished"
EVENT_SKIPPED = "skipped"
EVENT_FAILED = "failed"
CODE_IDEA_PROVIDED = "idea_provided"
CODE_CANCELLED = RunCancelledError.code
MSG_IDEA_PROVIDED = "Used the idea you reviewed."

# The UI waits PIPELINE_TIMEOUT_S for a full run. The backend stops at this share of it, so its
# reply, with everything that finished, arrives before the UI gives up. The rest covers the call
# that is in flight at the limit and sending the reply.
TIME_LIMIT_SHARE = 0.9

# Milestone 3, Section 11.1.3: a strategy stage's reply needs about 2,000 to 3,500 tokens, and the
# Groq model reasons before it answers, inside the same limit. So a Groq attempt inside a strategy
# stage may use this many output tokens instead of groq_client.MAX_COMPLETION_TOKENS (4,096). Every
# other call keeps its limit.
STRATEGY_MAX_OUTPUT_TOKENS = 6144
MSG_STRATEGY_PENDING = "This part of the strategy is not available yet."
# The result field each strategy stage writes, so a strategy-only job can keep the ones it does not run.
STRATEGY_FIELDS = {STAGE_SWOT: "swot", STAGE_MVP: "mvp", STAGE_GTM: "gtm"}
PROMPT_VERSIONS = {
    STAGE_EXTRACTION: ("extraction", EXTRACTION_PROMPT_VERSION),
    STAGE_MARKET: ("market", MARKET_PROMPT_VERSION),
    STAGE_COMPETITOR: ("competitors", COMPETITOR_PROMPT_VERSION),
    STAGE_SWOT: ("swot", SWOT_PROMPT_VERSION),
    STAGE_MVP: ("mvp", MVP_PROMPT_VERSION),
    STAGE_GTM: ("gtm", GTM_PROMPT_VERSION),
}


class ExtractionStage:
    """Stage 1: the founder's text becomes a validated ExtractedIdea."""

    name = STAGE_EXTRACTION

    def run(self, context: AgentContext) -> AgentContext:
        context.idea = extract_idea(context.submission)
        return context


class WebSearchStage:
    """Stage 2: the extracted idea becomes live market and competitor results."""

    name = STAGE_SEARCH
    warning_on_failure = WARNING_SEARCH_UNAVAILABLE
    # Any stage after it checks for itself whether there are results to work with, so a
    # failed search is recorded without stopping the pipeline.
    stop_on_failure = False

    def run(self, context: AgentContext) -> AgentContext:
        if context.idea is None:
            raise ValueError("the web search stage needs an extracted idea")
        region = search_region(context.constraints)
        bundle = run_web_search(context.idea) if region is None else run_web_search(context.idea, region=region)
        context.search = bundle
        if bundle.queries_failed:
            context.warnings.append(
                f"{bundle.queries_failed} of {len(bundle.sections)} web searches failed, "
                "so some sections are empty."
            )
        return context


class AnalysisStage:
    """Stages 3 and 4 (Milestone 2): an analysis agent that works from the search evidence.

    It is skipped, with a warning naming it, when there is no search result or no usable one
    (Section 9.1.5), or when the run's time limit has passed. Its failure is recorded without
    stopping the stages after it, and an unexpected exception becomes a stage error with the
    generic safe message (Section 11).
    """

    stop_on_failure = False

    def __init__(self, agent: Agent, label: str) -> None:
        self.agent = agent
        self.name = agent.name
        self.label = label

    def skip_reason(self, context: AgentContext) -> str | None:
        if context.search is None:
            return SKIP_NO_SEARCH.format(label=self.label)
        if not sourced_items(build_evidence(context.search)):
            return SKIP_NO_EVIDENCE.format(label=self.label)
        left = time_left()
        if left is not None and left <= 0:
            return SKIP_NO_TIME.format(label=self.label)
        return None

    def run(self, context: AgentContext) -> AgentContext:
        try:
            return self.agent.run(context)
        except AppError:
            raise
        except Exception as exc:
            logger.exception("stage %s raised an unexpected error", self.name)
            raise AppError() from exc


# Adding an agent later means appending one item here. No framework needed.
STAGES: list[Agent] = [ExtractionStage(), WebSearchStage()]

# Milestone 2, Task 3: the market stage, then the competitor stage, after the Milestone 1 stages.
# The competitor agent reduces context.market to the compact market context itself
# (market_context_for_competitors), so it gets none when the market stage failed.
FULL_STAGES: list[Agent] = [
    *STAGES,
    AnalysisStage(MarketOpportunityAgent(), MARKET_LABEL),
    AnalysisStage(CompetitorAnalysisAgent(), COMPETITOR_LABEL),
]


class PendingStrategyAgent:
    """Stands in for a strategy agent that is not registered (tests use it). Its stage fails with
    a plain message, so a run with strategy ends partial and keeps everything else."""

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, context: AgentContext) -> AgentContext:
        raise AppError(MSG_STRATEGY_PENDING)


class StrategyStage:
    """Stages 5 to 7 (Milestone 3): a strategy agent that reasons over the idea, the founder's
    constraints, the analyses and the earlier strategy stages. It makes no search.

    It is skipped, with a warning naming it, without the idea or without at least one finished
    analysis (Section 5.2), or when the run's time limit has passed. Its failure never stops the
    stages after it or discards earlier results, and an unexpected exception becomes a stage error
    with the generic safe message. In a run with strategy it draws on the extra time
    (`uses_strategy_time`, D-11), and its LLM calls may use STRATEGY_MAX_OUTPUT_TOKENS.
    """

    stop_on_failure = False
    uses_strategy_time = True

    def __init__(self, agent: Agent, label: str) -> None:
        self.agent = agent
        self.name = agent.name
        self.label = label

    def skip_reason(self, context: AgentContext) -> str | None:
        if context.idea is None or (context.market is None and context.competitors is None):
            return SKIP_NO_ANALYSIS.format(label=self.label)
        left = time_left()
        if left is not None and left <= 0:
            return SKIP_NO_TIME.format(label=self.label)
        return None

    def run(self, context: AgentContext) -> AgentContext:
        try:
            with output_token_limit(STRATEGY_MAX_OUTPUT_TOKENS):
                return self.agent.run(context)
        except AppError:
            raise
        except Exception as exc:
            logger.exception("stage %s raised an unexpected error", self.name)
            raise AppError() from exc


# Milestone 3: SWOT and risk, then MVP, then go-to-market, each reading the ones before it.
# STRATEGY_STAGES is a run with strategy; STRATEGY_ONLY_STAGES adds them to a saved result (prior).
STRATEGY_ONLY_STAGES: list[Agent] = [
    StrategyStage(SwotRiskAgent(), STRATEGY_TITLES[STAGE_SWOT]),
    StrategyStage(MvpAgent(), STRATEGY_TITLES[STAGE_MVP]),
    StrategyStage(GtmAgent(), STRATEGY_TITLES[STAGE_GTM]),
]
STRATEGY_STAGES: list[Agent] = [*FULL_STAGES, *STRATEGY_ONLY_STAGES]


@dataclass(frozen=True)
class StageEvent:
    """What happened to one stage. `result` is what the run has produced so far, given after the
    stage ended; while the run goes on it is a partial snapshot, never the final result."""

    stage: str
    kind: str  # started, finished, skipped or failed
    duration_s: float | None = None
    code: str | None = None
    message: str | None = None
    result: PipelineResult | None = None


def _stage_label(stage: Agent) -> str:
    return getattr(stage, "label", None) or STAGE_LABELS.get(stage.name, stage.name)


def _notify(on_event: Callable[[StageEvent], None] | None, event: StageEvent) -> None:
    """A failing callback is logged and never stops the run."""
    if on_event is None:
        return
    try:
        on_event(event)
    except Exception as exc:  # noqa: BLE001 - a listener must not break the pipeline
        logger.warning("stage event callback failed (%s)", type(exc).__name__)


def analysis_time_limit_s() -> float:
    """The backend's time limit for a run with the analysis stages (TIME_LIMIT_SHARE)."""
    return get_settings().pipeline_timeout_s * TIME_LIMIT_SHARE


def _elapsed(since: float) -> float:
    return round(time.perf_counter() - since, 3)


def _skip_reason(stage: Agent, context: AgentContext) -> str | None:
    check = getattr(stage, "skip_reason", None)
    return check(context) if check is not None else None


def _status(context: AgentContext, errors: list[StageError], skipped: list[str]) -> str:
    """No idea at all means nothing to show, so the run failed: that is extraction failing, and
    also a cancel before it ran. A failed or skipped stage, or a partly failed search, still
    returns everything produced, so the run is partial."""
    if errors or skipped:
        return "failed" if context.idea is None else "partial"
    if context.search is not None and context.search.queries_failed:
        return "partial"
    return "complete"


def _app_version() -> str:
    from routes.meta_routes import APP_VERSION

    return APP_VERSION


def _usage(by_stage: dict[str, StageUsage]) -> Usage:
    return Usage(
        llm_calls=sum(entry.llm_calls for entry in by_stage.values()),
        search_calls=sum(entry.search_calls for entry in by_stage.values()),
        by_stage=dict(by_stage),
    )


def _prior_prompt_versions(prior: PipelineResult, rerun: set[str]) -> dict[str, str]:
    if prior.versions is None:
        return {}
    replaced = {PROMPT_VERSIONS[stage][0] for stage in rerun if stage in PROMPT_VERSIONS}
    return {agent: version for agent, version in prior.versions.prompt_versions.items() if agent not in replaced}


def _result(
    context: AgentContext,
    errors: list[StageError],
    timings: dict[str, float],
    status: str,
    usage: Usage | None = None,
    versions: Versions | None = None,
) -> PipelineResult:
    return PipelineResult(
        status=status,
        idea=context.idea,
        search=context.search,
        warnings=list(context.warnings),
        errors=list(errors),
        timings=dict(timings),
        market=context.market,
        competitors=context.competitors,
        market_search=context.market_search,
        competitor_candidates=list(context.competitor_candidates),
        competitor_search=context.competitor_search,
        swot=context.swot,
        mvp=context.mvp,
        gtm=context.gtm,
        constraints=context.constraints,
        usage=usage,
        versions=versions,
    )


def _seeded(
    submission: IdeaSubmission,
    prior: PipelineResult,
    pipeline: Sequence[Agent],
    constraints: StrategyConstraints | None,
) -> AgentContext:
    """The context of a strategy-only job: everything the saved result holds, except the results and
    the warnings of the strategy stages the job runs again (each such warning starts with the
    stage's label)."""
    rerun = {stage.name for stage in pipeline}
    stale = tuple(f"{_stage_label(stage)}:" for stage in pipeline)
    kept = {field: getattr(prior, field) for stage, field in STRATEGY_FIELDS.items() if stage not in rerun}
    return AgentContext(
        submission=submission,
        idea=prior.idea,
        search=prior.search,
        warnings=[warning for warning in prior.warnings if not warning.startswith(stale)],
        market=prior.market,
        market_search=prior.market_search,
        competitors=prior.competitors,
        competitor_candidates=list(prior.competitor_candidates),
        competitor_search=prior.competitor_search,
        constraints=constraints if constraints is not None else prior.constraints,
        **kept,
    )


def _earlier_stages_finished(context: AgentContext, rerun: set[str]) -> bool:
    """In a strategy-only job, whether every stage it does not run had produced its result."""
    produced = [context.idea, context.search, context.market, context.competitors]
    produced += [getattr(context, field) for stage, field in STRATEGY_FIELDS.items() if stage not in rerun]
    return all(value is not None for value in produced)


def run_pipeline(
    submission: IdeaSubmission,
    stages: Sequence[Agent] | None = None,
    time_limit_s: float | None = None,
    *,
    idea: ExtractedIdea | None = None,
    on_event: Callable[[StageEvent], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    constraints: StrategyConstraints | None = None,
    prior: PipelineResult | None = None,
    strategy_time_limit_s: float | None = None,
) -> PipelineResult:
    """Run each agent in order, passing one context along, and summarise the outcome.

    The default is the Milestone 1 pipeline (STAGES); FULL_STAGES adds the analysis stages.
    A stage that raises an AppError is recorded in `errors`. The pipeline stops there unless
    the stage sets `stop_on_failure = False`, as the search stage and the analysis stages do;
    a stage with a `skip_reason` that returns a message is skipped and the message becomes a
    warning. Unexpected exceptions from the Milestone 1 stages are left to the application's
    generic error handler.

    `time_limit_s` bounds the whole run (utils/deadline.py): every LLM call and search waits at
    most the time that is left, and none starts after it. None, the default, sets no limit.

    UI upgrade (KIRO_UI_UPGRADE_SPEC.md 10.2), all optional, so existing callers are unchanged:
    `idea` is an extracted idea the founder reviewed, so the extraction stage is not run; `on_event`
    is told when each stage starts, finishes, is skipped or fails; `should_stop` is a cooperative
    cancel check, asked before each stage and before each outside call (utils/deadline.py). After a
    cancel the remaining stages are skipped with a warning and what finished is returned.
    The result also carries the fields derived in code (agents/derived.py).

    Milestone 3 (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Sections 5.2 to 5.5), also optional:
    `constraints` are the founder's, for the strategy stages. `strategy_time_limit_s` moves the time
    limit later once the first strategy stage is reached (D-11), so the stages before it keep the
    limit they have today. `prior` is a saved result for a strategy-only job (STRATEGY_ONLY_STAGES):
    the run starts from it and keeps its warnings, errors and timings except those of the stages it
    runs again; its own time is added to the saved total, and it is complete only if every
    earlier stage had finished too.
    """
    pipeline = list(STAGES if stages is None else stages)
    rerun = {stage.name for stage in pipeline}
    context = AgentContext(submission=submission, idea=idea, constraints=constraints)
    errors: list[StageError] = []
    skipped: list[str] = []
    timings: dict[str, float] = {}
    earlier_total = 0.0
    if prior is not None:
        context = _seeded(submission, prior, pipeline, constraints)
        errors = [error for error in prior.errors if error.stage not in rerun]
        timings = {key: value for key, value in prior.timings.items() if key != TOTAL_KEY and key not in rerun}
        earlier_total = prior.timings.get(TOTAL_KEY, 0.0)
    settings = get_settings()
    counter = UsageCounter()
    stage_usage: dict[str, StageUsage] = {}
    prompt_versions: dict[str, str] = {}
    if prior is not None:
        if prior.usage is not None:
            stage_usage = {key: value for key, value in prior.usage.by_stage.items() if key not in rerun}
        prompt_versions = _prior_prompt_versions(prior, rerun)
    started = time.perf_counter()

    def versions() -> Versions:
        return Versions(
            query_profile=settings.query_profile,
            prompt_profile=settings.prompt_profile,
            prompt_versions=dict(prompt_versions),
            app_version=_app_version(),
        )

    def record(stage: Agent, calls_before: tuple[int, int]) -> None:
        llm_calls, search_calls = counter.totals()
        stage_usage[stage.name] = StageUsage(
            llm_calls=llm_calls - calls_before[0],
            search_calls=search_calls - calls_before[1],
            seconds=timings[stage.name],
        )
        if stage.name in PROMPT_VERSIONS:
            agent, version = PROMPT_VERSIONS[stage.name]
            version = prompt_version(version, settings.prompt_profile)
            if stage.name == STAGE_EXTRACTION:
                version = extraction_prompt_version(settings.query_profile, settings.prompt_profile)
            prompt_versions[agent] = version

    def snapshot() -> PipelineResult | None:
        if on_event is None:
            return None
        status = "failed" if context.idea is None else "partial"
        return with_derived_fields(_result(context, errors, timings, status, _usage(stage_usage), versions()))

    with time_limit(time_limit_s), stop_check(should_stop), counting(counter), ExitStack() as strategy_time:
        extended = False
        for index, stage in enumerate(pipeline):
            if not extended and getattr(stage, "uses_strategy_time", False):
                strategy_time.enter_context(extra_time(strategy_time_limit_s))
                extended = True
            if idea is not None and stage.name == STAGE_EXTRACTION:
                _notify(on_event, StageEvent(stage.name, EVENT_SKIPPED, code=CODE_IDEA_PROVIDED,
                                             message=MSG_IDEA_PROVIDED, result=snapshot()))
                continue
            if stop_requested():
                for rest in pipeline[index:]:
                    reason = SKIP_CANCELLED.format(label=_stage_label(rest))
                    skipped.append(rest.name)
                    context.warnings.append(reason)
                    _notify(on_event, StageEvent(rest.name, EVENT_SKIPPED, code=CODE_CANCELLED, message=reason,
                                                 result=snapshot()))
                logger.info("run cancelled before stage %s", stage.name)
                break
            reason = _skip_reason(stage, context)
            if reason is not None:
                skipped.append(stage.name)
                context.warnings.append(reason)
                logger.info("stage %s skipped", stage.name)
                _notify(on_event, StageEvent(stage.name, EVENT_SKIPPED, message=reason, result=snapshot()))
                continue
            _notify(on_event, StageEvent(stage.name, EVENT_STARTED))
            stage_started = time.perf_counter()
            calls_before = counter.totals()
            try:
                context = stage.run(context)
            except AppError as exc:
                timings[stage.name] = _elapsed(stage_started)
                record(stage, calls_before)
                errors.append(StageError(stage=stage.name, code=exc.code, message=exc.user_message))
                warning = getattr(stage, "warning_on_failure", None)
                if warning and not isinstance(exc, RunCancelledError):
                    context.warnings.append(warning)
                logger.warning("stage %s failed (%s)", stage.name, exc.code)
                _notify(on_event, StageEvent(stage.name, EVENT_FAILED, duration_s=timings[stage.name], code=exc.code,
                                             message=exc.user_message, result=snapshot()))
                if getattr(stage, "stop_on_failure", True):
                    break
                continue
            timings[stage.name] = _elapsed(stage_started)
            record(stage, calls_before)
            _notify(on_event, StageEvent(stage.name, EVENT_FINISHED, duration_s=timings[stage.name], result=snapshot()))

    timings[TOTAL_KEY] = round(earlier_total + _elapsed(started), 3) if prior is not None else _elapsed(started)
    status = _status(context, errors, skipped)
    if prior is not None and status == "complete" and not _earlier_stages_finished(context, rerun):
        status = "partial"
    logger.info(
        "pipeline %s in %.2fs (%d warnings, %d errors)",
        status,
        timings[TOTAL_KEY],
        len(context.warnings),
        len(errors),
    )
    return with_derived_fields(_result(context, errors, timings, status, _usage(stage_usage), versions()))

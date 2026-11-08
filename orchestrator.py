"""Orchestration: a plain function that runs the agents in order.

Milestone 1 runs two stages (STAGES): extraction, then web search. Milestone 2, Task 3 appends the
Market Opportunity and Competitor Analysis stages (FULL_STAGES). POST /api/validate runs the full
list when the client asks for the analysis, which the UI always does; without it the Milestone 1
pipeline runs unchanged.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Sequence

from agents.base import Agent, AgentContext
from agents.competitor_analysis_agent import STAGE_COMPETITOR
from agents.competitor_analysis_agent import WARNING_PREFIX as COMPETITOR_LABEL
from agents.competitor_analysis_agent import CompetitorAnalysisAgent
from agents.derived import with_derived_fields
from agents.evidence import build_evidence, sourced_items
from agents.extraction_agent import extract_idea
from agents.market_opportunity_agent import STAGE_MARKET
from agents.market_opportunity_agent import WARNING_PREFIX as MARKET_LABEL
from agents.market_opportunity_agent import MarketOpportunityAgent
from agents.web_search_agent import run_web_search
from config import get_settings
from models.schemas import ExtractedIdea, IdeaSubmission, PipelineResult, StageError
from utils.deadline import stop_check, stop_requested, time_left, time_limit
from utils.errors import AppError, RunCancelledError

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
        bundle = run_web_search(context.idea)
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


def _result(context: AgentContext, errors: list[StageError], timings: dict[str, float], status: str) -> PipelineResult:
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
    )


def run_pipeline(
    submission: IdeaSubmission,
    stages: Sequence[Agent] | None = None,
    time_limit_s: float | None = None,
    *,
    idea: ExtractedIdea | None = None,
    on_event: Callable[[StageEvent], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
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
    """
    pipeline = list(STAGES if stages is None else stages)
    context = AgentContext(submission=submission, idea=idea)
    errors: list[StageError] = []
    skipped: list[str] = []
    timings: dict[str, float] = {}
    started = time.perf_counter()

    def snapshot() -> PipelineResult | None:
        if on_event is None:
            return None
        return with_derived_fields(_result(context, errors, timings, "failed" if context.idea is None else "partial"))

    with time_limit(time_limit_s), stop_check(should_stop):
        for index, stage in enumerate(pipeline):
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
            try:
                context = stage.run(context)
            except AppError as exc:
                timings[stage.name] = _elapsed(stage_started)
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
            _notify(on_event, StageEvent(stage.name, EVENT_FINISHED, duration_s=timings[stage.name], result=snapshot()))

    timings[TOTAL_KEY] = _elapsed(started)
    status = _status(context, errors, skipped)
    logger.info(
        "pipeline %s in %.2fs (%d warnings, %d errors)",
        status,
        timings[TOTAL_KEY],
        len(context.warnings),
        len(errors),
    )
    return with_derived_fields(_result(context, errors, timings, status))

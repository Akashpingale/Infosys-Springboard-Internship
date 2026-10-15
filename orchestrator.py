"""Orchestration for Milestone 1: a plain function that runs the agents in order."""

import logging
import time
from typing import Sequence

from agents.base import Agent, AgentContext
from agents.extraction_agent import extract_idea
from agents.web_search_agent import run_web_search
from models.schemas import IdeaSubmission, PipelineResult, StageError
from utils.errors import AppError

logger = logging.getLogger(__name__)

STAGE_EXTRACTION = "extraction"
STAGE_SEARCH = "search"
TOTAL_KEY = "total"

WARNING_SEARCH_UNAVAILABLE = (
    "Market and competitor research is not available, so only the structured idea is shown."
)


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


# Adding an agent later means appending one item here. No framework needed.
STAGES: list[Agent] = [ExtractionStage(), WebSearchStage()]


def _elapsed(since: float) -> float:
    return round(time.perf_counter() - since, 3)


def _status(context: AgentContext, errors: list[StageError]) -> str:
    """Extraction failed means nothing to show. Anything else partial still returns the idea."""
    if errors:
        return "failed" if context.idea is None else "partial"
    if context.search is not None and context.search.queries_failed:
        return "partial"
    return "complete"


def run_pipeline(
    submission: IdeaSubmission, stages: Sequence[Agent] | None = None
) -> PipelineResult:
    """Run each agent in order, passing one context along, and summarise the outcome.

    A stage that raises an AppError is recorded in `errors` and stops the pipeline,
    because every later stage depends on what the failed one would have produced.
    Unexpected exceptions are left to the application's generic error handler.
    """
    pipeline = STAGES if stages is None else stages
    context = AgentContext(submission=submission)
    errors: list[StageError] = []
    timings: dict[str, float] = {}
    started = time.perf_counter()

    for stage in pipeline:
        stage_started = time.perf_counter()
        try:
            context = stage.run(context)
        except AppError as exc:
            timings[stage.name] = _elapsed(stage_started)
            errors.append(StageError(stage=stage.name, code=exc.code, message=exc.user_message))
            warning = getattr(stage, "warning_on_failure", None)
            if warning:
                context.warnings.append(warning)
            logger.warning("stage %s failed (%s)", stage.name, exc.code)
            break
        timings[stage.name] = _elapsed(stage_started)

    timings[TOTAL_KEY] = _elapsed(started)
    status = _status(context, errors)
    logger.info(
        "pipeline %s in %.2fs (%d warnings, %d errors)",
        status,
        timings[TOTAL_KEY],
        len(context.warnings),
        len(errors),
    )
    return PipelineResult(
        status=status,
        idea=context.idea,
        search=context.search,
        warnings=context.warnings,
        errors=errors,
        timings=timings,
    )

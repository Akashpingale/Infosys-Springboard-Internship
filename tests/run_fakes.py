"""Helpers for the background-run tests (KIRO_UI_UPGRADE_SPEC.md Section 10.6).

Fakes only: the store always writes to a temporary folder, so no test touches `data/runs.db`, and
the pipeline is replaced by a function that reports stage events without any LLM or search call.
"""

import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from models.schemas import ExtractedIdea, IdeaSubmission, PipelineResult, StageError
from orchestrator import (
    CODE_CANCELLED,
    EVENT_FAILED,
    EVENT_FINISHED,
    EVENT_SKIPPED,
    EVENT_STARTED,
    STAGE_COMPETITOR,
    STAGE_EXTRACTION,
    STAGE_MARKET,
    STAGE_SEARCH,
    StageEvent,
)
from tests.fakes import VALID_EXTRACTION
from utils.run_manager import RunManager
from utils.run_store import RunStore

SUBMISSION = IdeaSubmission(
    idea_description="A mobile app that detects crop diseases from a photo of a leaf for small farmers.",
    industry="Agriculture / AgriTech",
    target_customers="Small farmers in Maharashtra",
    relevant_details="Starting with two farming cooperatives.",
)
REVIEWED_IDEA = ExtractedIdea(**{**VALID_EXTRACTION, "idea_title": "Reviewed: leaf photo diagnosis"})
STAGES = (STAGE_EXTRACTION, STAGE_SEARCH, STAGE_MARKET, STAGE_COMPETITOR)


def result(status: str = "complete", **fields: Any) -> PipelineResult:
    """A small finished result. The analysis-shaped fields stay empty unless a test fills them."""
    timings = fields.pop("timings", {"extraction": 1.0, "search": 2.0, "total": 3.0})
    return PipelineResult(status=status, idea=ExtractedIdea(**VALID_EXTRACTION), timings=timings, **fields)


def store_in(tmp_path: Path, secrets: tuple[str | None, ...] = ()) -> RunStore:
    return RunStore(tmp_path / "runs.db", secrets=secrets)


class FakePipeline:
    """Stands in for the four-stage pipeline.

    It reports a started and a finished event per stage, honours the cancel check between stages,
    and returns `final`. `block` lets a test hold the run inside a stage; `fail_at` makes one stage
    raise, and `raise_before` makes the whole call fail.
    """

    def __init__(
        self,
        final: PipelineResult | None = None,
        *,
        stages: tuple[str, ...] = STAGES,
        block: threading.Event | None = None,
        block_at: str = STAGE_SEARCH,
        fail_at: str | None = None,
        raise_before: Exception | None = None,
        partial_results: dict[str, PipelineResult] | None = None,
    ) -> None:
        self.final = final if final is not None else result()
        self.stages = stages
        self.block = block
        self.block_at = block_at
        self.fail_at = fail_at
        self.raise_before = raise_before
        self.partial_results = partial_results or {}
        self.events: list[tuple[str, str]] = []
        self.calls: list[dict[str, Any]] = []
        self.entered = threading.Event()
        # Set once the blocking stage is running, so a test can act at a known point.
        self.reached = threading.Event()
        self.started_stages: list[str] = []

    def __call__(
        self,
        submission: IdeaSubmission,
        *,
        idea: ExtractedIdea | None,
        on_event: Callable[[StageEvent], None],
        should_stop: Callable[[], bool],
        time_limit_s: float | None,
    ) -> PipelineResult:
        self.calls.append({"submission": submission, "idea": idea, "time_limit_s": time_limit_s})
        self.entered.set()
        if self.raise_before is not None:
            raise self.raise_before
        cancelled = False
        for stage in self.stages:
            if idea is not None and stage == STAGE_EXTRACTION:
                self._emit(on_event, StageEvent(stage, EVENT_SKIPPED, code="idea_provided",
                                                message="Used the idea you reviewed.", result=self.final))
                continue
            if should_stop():
                cancelled = True
                self._emit(on_event, StageEvent(stage, EVENT_SKIPPED, code=CODE_CANCELLED,
                                                message=f"{stage}: skipped because the run was cancelled."))
                continue
            if cancelled:
                self._emit(on_event, StageEvent(stage, EVENT_SKIPPED, code=CODE_CANCELLED,
                                                message=f"{stage}: skipped because the run was cancelled."))
                continue
            self.started_stages.append(stage)
            self._emit(on_event, StageEvent(stage, EVENT_STARTED))
            if self.block is not None and stage == self.block_at:
                self.reached.set()
                self.block.wait(10)
            if stage == self.fail_at:
                self._emit(on_event, StageEvent(stage, EVENT_FAILED, duration_s=0.5, code="llm_api_error",
                                                message="The AI service is busy right now.",
                                                result=self.partial_results.get(stage, self.final)))
                continue
            # As the real orchestrator does, every ended stage carries the result so far.
            self._emit(on_event, StageEvent(stage, EVENT_FINISHED, duration_s=1.0,
                                            result=self.partial_results.get(stage, self.final)))
        return self.final

    def _emit(self, on_event: Callable[[StageEvent], None], event: StageEvent) -> None:
        self.events.append((event.stage, event.kind))
        on_event(event)


def manager_with(store: RunStore, pipeline: Callable[..., PipelineResult], **options: Any) -> RunManager:
    return RunManager(store, pipeline=pipeline, **options)


def finished(manager: RunManager, run_id: str, timeout: float = 10.0) -> Any:
    """Wait for a run to end, then return its detail."""
    assert manager.wait(run_id, timeout), "the run did not finish in time"
    return manager.get(run_id)


def stage_statuses(detail: Any) -> dict[str, str]:
    return {stage.key: stage.status for stage in detail.stages}


def failing_result() -> PipelineResult:
    return PipelineResult(
        status="failed",
        errors=[StageError(stage=STAGE_EXTRACTION, code="llm_api_error", message="The AI service is busy right now.")],
        timings={"extraction": 1.0, "total": 1.0},
    )


def iter_once(value: Any) -> Iterator[Any]:
    yield value

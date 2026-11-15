"""Background runs (KIRO_UI_UPGRADE_SPEC.md Section 10.2).

POST /api/runs hands the full pipeline to a small thread pool, so the browser polls
GET /api/runs/{id} instead of waiting on one long request. At most MAX_CONCURRENT_RUNS run at once;
one more is refused with RunLimitError. Cancelling is cooperative: the pipeline stops before its next
stage or outside call, a call already in flight is allowed to finish, and only then is the run marked
cancelled. Every state change is written to the run store (utils/run_store.py).

Runs started through POST /api/validate (the Streamlit UI) do not pass through here, so they are not
counted against the limit and are not saved in the history.
"""

import json
import logging
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from agents.notices import STAGE_TITLES, notice_for_warning
from config import get_settings
from models.api import ACTIVE_STATES, RunDetail, RunStage, RunSummary
from models.schemas import ExtractedIdea, IdeaSubmission, PipelineResult
from orchestrator import (
    CODE_CANCELLED,
    CODE_IDEA_PROVIDED,
    EVENT_FAILED,
    EVENT_FINISHED,
    EVENT_SKIPPED,
    EVENT_STARTED,
    FULL_STAGES,
    STAGE_EXTRACTION,
    StageEvent,
    analysis_time_limit_s,
    run_pipeline,
)
from utils.errors import AppError, HistoryUnavailableError, RunActiveError, RunLimitError, RunNotFoundError
from utils.run_store import RunStore, now_iso

logger = logging.getLogger(__name__)

MAX_CONCURRENT_RUNS = 2
TITLE_FROM_TEXT_MAX = 60
STAGE_KEYS = tuple(stage.name for stage in FULL_STAGES)

MSG_CANCELLED = "Cancelled. What finished before the cancel is shown below."
MSG_CANCELLED_EARLY = "Cancelled before it started."
MSG_PARTIAL = "Some parts could not be completed. What finished is shown below."
MSG_FAILED = "We couldn't understand the idea. Check the text and try again."
MSG_UNEXPECTED = AppError.default_message
MSG_NOT_RUN = "Not run because an earlier step did not finish."
MSG_STAGE_CANCELLED = "Cancelled before this step started."
MSG_UNREADABLE = "This saved validation could not be read."

Pipeline = Callable[..., PipelineResult]


def full_pipeline(
    submission: IdeaSubmission,
    *,
    idea: ExtractedIdea | None,
    on_event: Callable[[StageEvent], None],
    should_stop: Callable[[], bool],
    time_limit_s: float | None,
) -> PipelineResult:
    """The four stages, as POST /api/validate?include_analysis=true runs them."""
    return run_pipeline(submission, FULL_STAGES, time_limit_s, idea=idea, on_event=on_event, should_stop=should_stop)


def run_time_limit_s() -> float:
    """PIPELINE_TIME_LIMIT_S when set; otherwise the existing limit of an analysis run."""
    configured = get_settings().pipeline_time_limit_s
    return configured if configured is not None else analysis_time_limit_s()


def _title_from_text(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= TITLE_FROM_TEXT_MAX:
        return text
    cut = text[:TITLE_FROM_TEXT_MAX].rsplit(" ", 1)[0]
    return f"{cut}..."


def _new_stages() -> list[dict[str, Any]]:
    return [
        {"key": key, "label": STAGE_TITLES.get(key, key), "status": "waiting", "started_at": None,
         "duration_s": None, "message": None}
        for key in STAGE_KEYS
    ]


def _public(stage: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in stage.items() if not key.startswith("_")}


def _settle(stages: list[dict[str, Any]], state: str) -> list[dict[str, Any]]:
    """In an ended run, no stage is left waiting or running."""
    if state in ACTIVE_STATES:
        return stages
    settled = []
    for stage in stages:
        stage = dict(stage)
        if stage["status"] == "running":
            stage["status"] = "cancelled" if state == "cancelled" else "failed"
        elif stage["status"] == "waiting":
            stage["status"] = "cancelled" if state == "cancelled" else "skipped"
            stage["message"] = stage.get("message") or (MSG_STAGE_CANCELLED if state == "cancelled" else MSG_NOT_RUN)
        settled.append(stage)
    return settled


@dataclass
class _Run:
    id: str
    title: str
    industry: str
    created_at: str
    submission: IdeaSubmission
    idea_override: ExtractedIdea | None
    stages: list[dict[str, Any]] = field(default_factory=_new_stages)
    renamed: bool = False
    state: str = "queued"
    started_at: str | None = None
    finished_at: str | None = None
    duration_s: float | None = None
    message: str | None = None
    result: PipelineResult | None = None
    started_mono: float | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    ended: threading.Event = field(default_factory=threading.Event)


class RunManager:
    def __init__(
        self,
        store: RunStore,
        *,
        max_runs: int = MAX_CONCURRENT_RUNS,
        pipeline: Pipeline = full_pipeline,
        time_limit: Callable[[], float | None] = run_time_limit_s,
    ) -> None:
        self._store = store
        self._max_runs = max_runs
        self._pipeline = pipeline
        self._time_limit = time_limit
        self._executor = ThreadPoolExecutor(max_workers=max_runs, thread_name_prefix="validation-run")
        self._lock = threading.RLock()
        self._active: dict[str, _Run] = {}
        # Ended runs whose final state could not be written: kept in memory until the server stops.
        self._unsaved: dict[str, _Run] = {}
        self._closed = False

    # --- persistence ----------------------------------------------------------------------------

    def _columns(self, run: _Run) -> dict[str, Any]:
        ended = run.state not in ACTIVE_STATES
        return {
            "title": run.title,
            "renamed": int(run.renamed),
            "industry": run.industry,
            "state": run.state,
            "result_status": run.result.status if ended and run.result is not None else None,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "duration_s": run.duration_s,
            "cancel_requested": int(run.cancel.is_set()),
            "message": run.message,
            "stages_json": json.dumps([_public(stage) for stage in run.stages]),
            "result_json": run.result.model_dump_json() if run.result is not None else None,
        }

    def _save(self, run: _Run) -> bool:
        try:
            self._store.update(run.id, **self._columns(run))
            return True
        except HistoryUnavailableError:
            logger.warning("run %s could not be saved; it is kept in memory", run.id)
            return False

    # --- views ----------------------------------------------------------------------------------

    def _detail(self, run: _Run) -> RunDetail:
        now = time.monotonic()
        stages = []
        for stage in _settle(run.stages, run.state):
            elapsed = stage["duration_s"]
            if stage["status"] == "running" and stage.get("_t0") is not None:
                elapsed = round(now - stage["_t0"], 3)
            stages.append(RunStage(**_public(stage), elapsed_s=elapsed))
        elapsed = run.duration_s
        if run.state in ACTIVE_STATES and run.started_mono is not None:
            elapsed = round(now - run.started_mono, 3)
        return RunDetail(
            id=run.id, title=run.title, industry=run.industry, state=run.state, created_at=run.created_at,
            started_at=run.started_at, finished_at=run.finished_at, duration_s=run.duration_s, elapsed_s=elapsed,
            cancel_requested=run.cancel.is_set(), message=run.message, stages=stages, submission=run.submission,
            idea_override=run.idea_override, result=run.result,
        )

    @staticmethod
    def _detail_from_row(row: dict[str, Any]) -> RunDetail:
        try:
            stages = _settle(json.loads(row["stages_json"]), row["state"])
            submission = IdeaSubmission.model_validate_json(row["submission_json"])
            override = ExtractedIdea.model_validate_json(row["idea_override_json"]) if row["idea_override_json"] else None
            result = PipelineResult.model_validate_json(row["result_json"]) if row["result_json"] else None
            return RunDetail(
                id=row["id"], title=row["title"], industry=row["industry"], state=row["state"],
                created_at=row["created_at"], started_at=row["started_at"], finished_at=row["finished_at"],
                duration_s=row["duration_s"], elapsed_s=row["duration_s"], cancel_requested=bool(row["cancel_requested"]),
                message=row["message"], stages=[RunStage(**stage, elapsed_s=stage.get("duration_s")) for stage in stages],
                submission=submission, idea_override=override, result=result,
            )
        except (ValueError, TypeError, KeyError):
            logger.warning("saved run %s could not be read", row.get("id"))
            raise HistoryUnavailableError(MSG_UNREADABLE) from None

    @staticmethod
    def _summary(detail: RunDetail) -> RunSummary:
        ended = detail.state not in ACTIVE_STATES
        return RunSummary(
            id=detail.id, title=detail.title, industry=detail.industry, state=detail.state,
            status=detail.result.status if ended and detail.result is not None else None,
            created_at=detail.created_at, duration_s=detail.duration_s,
        )

    # --- the public operations ----------------------------------------------------------------

    def start(self, submission: IdeaSubmission, idea_override: ExtractedIdea | None = None) -> RunDetail:
        if not self._store.available:
            raise HistoryUnavailableError()
        with self._lock:
            if self._closed or len(self._active) >= self._max_runs:
                raise RunLimitError()
            source = idea_override if idea_override is not None else None
            run = _Run(
                id=uuid.uuid4().hex,
                title=source.idea_title if source is not None else _title_from_text(submission.idea_description),
                industry=source.industry if source is not None else submission.industry,
                created_at=now_iso(),
                submission=submission,
                idea_override=idea_override,
            )
            self._store.insert({
                "id": run.id,
                "created_at": run.created_at,
                "submission_json": submission.model_dump_json(),
                "idea_override_json": idea_override.model_dump_json() if idea_override is not None else None,
                **self._columns(run),
            })
            self._active[run.id] = run
            detail = self._detail(run)
        self._executor.submit(self._work, run)
        logger.info("run %s queued", run.id)
        return detail

    def get(self, run_id: str) -> RunDetail:
        with self._lock:
            run = self._active.get(run_id) or self._unsaved.get(run_id)
            if run is not None:
                return self._detail(run)
        row = self._store.get(run_id)
        if row is None:
            raise RunNotFoundError()
        return self._detail_from_row(row)

    def cancel(self, run_id: str) -> RunDetail:
        """Ask a queued or running run to stop. An ended run is returned unchanged."""
        with self._lock:
            run = self._active.get(run_id)
            if run is not None:
                if not run.cancel.is_set():
                    run.cancel.set()
                    logger.info("run %s: cancel requested", run_id)
                    self._save(run)
                return self._detail(run)
        return self.get(run_id)

    def list(self) -> list[RunSummary]:
        rows = self._store.list()
        with self._lock:
            unsaved = [self._summary(self._detail(run)) for run in self._unsaved.values()]
        saved = [
            RunSummary(
                id=row["id"], title=row["title"], industry=row["industry"], state=row["state"],
                status=row["result_status"], created_at=row["created_at"], duration_s=row["duration_s"],
            )
            for row in rows
            if row["id"] not in self._unsaved
        ]
        return [*unsaved, *saved]

    def rename(self, run_id: str, title: str) -> RunSummary:
        with self._lock:
            run = self._active.get(run_id) or self._unsaved.get(run_id)
            if run is not None:
                run.title, run.renamed = title, True
                self._save(run)
                return self._summary(self._detail(run))
        if not self._store.update(run_id, title=title, renamed=1):
            raise RunNotFoundError()
        return self._summary(self.get(run_id))

    def delete(self, run_id: str) -> None:
        with self._lock:
            if run_id in self._active:
                raise RunActiveError()
            kept_in_memory = self._unsaved.pop(run_id, None) is not None
        if not self._store.delete(run_id) and not kept_in_memory:
            raise RunNotFoundError()

    def wait(self, run_id: str, timeout: float | None = None) -> bool:
        """Block until the run has ended (for scripts and tests). True if it ended in time."""
        with self._lock:
            run = self._active.get(run_id)
        return True if run is None else run.ended.wait(timeout)

    def shutdown(self) -> None:
        """Ask every run to stop and stop taking new ones. Calls in flight finish on their own."""
        with self._lock:
            self._closed = True
            for run in self._active.values():
                run.cancel.set()
        self._executor.shutdown(wait=False, cancel_futures=True)

    # --- the worker -----------------------------------------------------------------------------

    def _work(self, run: _Run) -> None:
        if run.cancel.is_set():
            self._finish(run, None)
            return
        with self._lock:
            run.state = "running"
            run.started_at = now_iso()
            run.started_mono = time.monotonic()
            self._save(run)
        result: PipelineResult | None = None
        failure = None
        try:
            result = self._pipeline(
                run.submission,
                idea=run.idea_override,
                on_event=lambda event: self._on_event(run, event),
                should_stop=run.cancel.is_set,
                time_limit_s=self._time_limit(),
            )
        except Exception as exc:  # noqa: BLE001 - a run must always end with a saved state
            logger.error("run %s stopped unexpectedly (%s)", run.id, type(exc).__name__)
            failure = MSG_UNEXPECTED
        self._finish(run, result, failure)

    def _on_event(self, run: _Run, event: StageEvent) -> None:
        with self._lock:
            stage = next((item for item in run.stages if item["key"] == event.stage), None)
            if stage is None:
                stage = {"key": event.stage, "label": STAGE_TITLES.get(event.stage, event.stage), "status": "waiting",
                         "started_at": None, "duration_s": None, "message": None}
                run.stages.append(stage)
            if event.kind == EVENT_STARTED:
                stage.update(status="running", started_at=now_iso(), _t0=time.monotonic(), message=None)
            elif event.kind == EVENT_FINISHED:
                stage.update(status="done", duration_s=event.duration_s, message=None)
            elif event.kind == EVENT_SKIPPED:
                if event.code == CODE_IDEA_PROVIDED:
                    stage.update(status="done", message=event.message)
                elif event.code == CODE_CANCELLED:
                    stage.update(status="cancelled", message=MSG_STAGE_CANCELLED)
                else:
                    stage.update(status="skipped", message=notice_for_warning(event.message or "").message)
            elif event.kind == EVENT_FAILED:
                cancelled = event.code == CODE_CANCELLED
                stage.update(status="cancelled" if cancelled else "failed", duration_s=event.duration_s,
                             message=event.message)
            if event.result is not None:
                run.result = event.result
                if not run.renamed and event.stage == STAGE_EXTRACTION and event.result.idea is not None:
                    run.title = event.result.idea.idea_title
            self._save(run)

    def _finish(self, run: _Run, result: PipelineResult | None, failure: str | None = None) -> None:
        with self._lock:
            if result is not None:
                run.result = result
            run.finished_at = now_iso()
            if run.cancel.is_set():
                run.state = "cancelled"
                produced = run.result is not None and run.result.idea is not None
                run.message = MSG_CANCELLED if produced else MSG_CANCELLED_EARLY
            elif result is None:
                run.state, run.message = "failed", failure or MSG_UNEXPECTED
            elif result.status == "failed":
                run.state = "failed"
                run.message = result.errors[0].message if result.errors else MSG_FAILED
            else:
                run.state = "done"
                run.message = MSG_PARTIAL if result.status == "partial" else None
            if result is not None and "total" in result.timings:
                run.duration_s = result.timings["total"]
            elif run.started_mono is not None:
                run.duration_s = round(time.monotonic() - run.started_mono, 3)
            run.stages = _settle(run.stages, run.state)
            saved = self._save(run)
            self._active.pop(run.id, None)
            if not saved:
                self._unsaved[run.id] = run
            run.ended.set()
        logger.info("run %s ended: %s", run.id, run.state)


# --- the process-wide manager -------------------------------------------------------------------
# Created on first use, so importing the app or building it in a test never writes a database file.

_default: RunManager | None = None
_default_lock = threading.Lock()


def default_manager() -> RunManager:
    """The run manager the API uses, built from the settings on first use."""
    global _default
    with _default_lock:
        if _default is None:
            settings = get_settings()
            store = RunStore(
                settings.runs_db_path,
                secrets=(settings.llm_api_key, settings.tavily_api_key, settings.groq_api_key),
            )
            _default = RunManager(store)
        return _default


def shutdown_default_manager() -> None:
    """Stop the process-wide manager, if one was ever created."""
    global _default
    with _default_lock:
        manager, _default = _default, None
    if manager is not None:
        manager.shutdown()

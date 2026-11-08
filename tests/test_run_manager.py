"""The background run manager (KIRO_UI_UPGRADE_SPEC.md Section 10.2).

Fakes only: the pipeline is a stand-in that reports stage events (tests/run_fakes.py) and every
store writes to a temporary folder, so no LLM, no search and no `data/runs.db` is involved.
"""

import json
import threading
from pathlib import Path

import pytest

from models.schemas import PipelineResult
from orchestrator import STAGE_COMPETITOR, STAGE_EXTRACTION, STAGE_MARKET, STAGE_SEARCH
from tests.run_fakes import (
    REVIEWED_IDEA,
    SUBMISSION,
    FakePipeline,
    failing_result,
    finished,
    manager_with,
    result,
    stage_statuses,
    store_in,
)
from utils.errors import HistoryUnavailableError, RunActiveError, RunLimitError, RunNotFoundError
from utils.run_manager import (
    MAX_CONCURRENT_RUNS,
    MSG_CANCELLED,
    MSG_PARTIAL,
    MSG_STAGE_CANCELLED,
    RunManager,
    run_time_limit_s,
)
from utils.run_store import RunStore

# Deliberately not shaped like any real key, so the project's secret scan stays silent on this file.
SECRET = "fake-configured-value-for-the-redaction-test"


@pytest.fixture
def pipeline() -> FakePipeline:
    return FakePipeline()


@pytest.fixture
def manager(tmp_path: Path, pipeline: FakePipeline) -> RunManager:
    created = manager_with(store_in(tmp_path), pipeline)
    yield created
    created.shutdown()


# --- the lifecycle -------------------------------------------------------------------------------


def test_a_run_goes_from_queued_to_done_and_keeps_its_result(manager: RunManager, pipeline: FakePipeline) -> None:
    started = manager.start(SUBMISSION)

    assert started.state == "queued" and started.id
    assert [stage.status for stage in started.stages] == ["waiting"] * 4, "nothing has run yet"

    detail = finished(manager, started.id)

    assert detail.state == "done" and detail.message is None
    assert detail.result is not None and detail.result.status == "complete"
    assert stage_statuses(detail) == {stage: "done" for stage in (STAGE_EXTRACTION, STAGE_SEARCH, STAGE_MARKET, STAGE_COMPETITOR)}
    assert detail.started_at and detail.finished_at and detail.duration_s == 3.0
    assert detail.submission == SUBMISSION


def test_the_stages_are_reported_in_order_as_they_run(manager: RunManager, pipeline: FakePipeline) -> None:
    run_id = manager.start(SUBMISSION).id
    finished(manager, run_id)

    assert pipeline.events == [
        (STAGE_EXTRACTION, "started"), (STAGE_EXTRACTION, "finished"),
        (STAGE_SEARCH, "started"), (STAGE_SEARCH, "finished"),
        (STAGE_MARKET, "started"), (STAGE_MARKET, "finished"),
        (STAGE_COMPETITOR, "started"), (STAGE_COMPETITOR, "finished"),
    ]


def test_a_running_stage_is_visible_with_its_elapsed_time(tmp_path: Path) -> None:
    gate = threading.Event()
    pipeline = FakePipeline(block=gate, block_at=STAGE_SEARCH)
    manager = manager_with(store_in(tmp_path), pipeline)
    try:
        run_id = manager.start(SUBMISSION).id
        assert pipeline.reached.wait(10)

        detail = manager.get(run_id)
        statuses = stage_statuses(detail)

        assert detail.state == "running" and statuses[STAGE_EXTRACTION] == "done"
        assert statuses[STAGE_SEARCH] == "running" and statuses[STAGE_COMPETITOR] == "waiting"
        running = next(stage for stage in detail.stages if stage.key == STAGE_SEARCH)
        assert running.started_at and running.elapsed_s is not None and running.elapsed_s >= 0
        assert detail.elapsed_s is not None and detail.elapsed_s >= 0
    finally:
        gate.set()
        manager.shutdown()


def test_partial_results_arrive_while_the_run_is_still_going(tmp_path: Path) -> None:
    gate = threading.Event()
    half = result(status="partial")
    pipeline = FakePipeline(block=gate, block_at=STAGE_MARKET, partial_results={STAGE_SEARCH: half})
    manager = manager_with(store_in(tmp_path), pipeline)
    try:
        run_id = manager.start(SUBMISSION).id
        assert pipeline.reached.wait(10), "search finished, the market stage is running"

        detail = manager.get(run_id)

        assert detail.state == "running", "a partial result does not end the run"
        assert detail.result is not None and detail.result.idea is not None
    finally:
        gate.set()
        manager.shutdown()


def test_the_title_follows_the_extracted_idea_once_it_is_known(manager: RunManager, pipeline: FakePipeline) -> None:
    started = manager.start(SUBMISSION)
    assert started.title.startswith("A mobile app that detects crop"), "the submission text until extraction"

    detail = finished(manager, started.id)

    assert detail.title == "CropScan: AI crop disease detection", "the extracted title afterwards"


def test_a_reviewed_idea_skips_extraction_and_names_the_run(manager: RunManager, pipeline: FakePipeline) -> None:
    started = manager.start(SUBMISSION, REVIEWED_IDEA)

    assert started.title == REVIEWED_IDEA.idea_title

    detail = finished(manager, started.id)

    assert pipeline.calls[0]["idea"] == REVIEWED_IDEA, "the pipeline is given the reviewed idea"
    assert STAGE_EXTRACTION not in pipeline.started_stages, "extraction is not run again"
    assert stage_statuses(detail)[STAGE_EXTRACTION] == "done"
    assert detail.idea_override == REVIEWED_IDEA
    assert next(s for s in detail.stages if s.key == STAGE_EXTRACTION).message == "Used the idea you reviewed."


def test_the_run_gets_the_configured_time_limit(manager: RunManager, pipeline: FakePipeline) -> None:
    finished(manager, manager.start(SUBMISSION).id)
    assert pipeline.calls[0]["time_limit_s"] == run_time_limit_s()


@pytest.mark.parametrize(("raw", "expected"), [("120", 120.0), ("abc", 162.0), ("-4", 162.0), ("", 162.0)])
def test_pipeline_time_limit_s_falls_back_to_the_existing_rule(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: float
) -> None:
    if raw:
        monkeypatch.setenv("PIPELINE_TIME_LIMIT_S", raw)
    assert run_time_limit_s() == pytest.approx(expected)


# --- failures and partial runs -------------------------------------------------------------------


def test_a_partial_result_ends_as_done_with_a_plain_message(tmp_path: Path) -> None:
    manager = manager_with(store_in(tmp_path), FakePipeline(result(status="partial"), fail_at=STAGE_MARKET))
    try:
        detail = finished(manager, manager.start(SUBMISSION).id)

        assert detail.state == "done", "a result exists, so the run itself did not fail"
        assert detail.result.status == "partial" and detail.message == MSG_PARTIAL
        assert stage_statuses(detail)[STAGE_MARKET] == "failed"
        assert "busy" in next(s for s in detail.stages if s.key == STAGE_MARKET).message
    finally:
        manager.shutdown()


def test_a_failed_result_ends_as_failed_and_keeps_the_reason(tmp_path: Path) -> None:
    manager = manager_with(store_in(tmp_path), FakePipeline(failing_result(), fail_at=STAGE_EXTRACTION))
    try:
        detail = finished(manager, manager.start(SUBMISSION).id)

        assert detail.state == "failed"
        assert detail.message == "The AI service is busy right now." and "Traceback" not in detail.message
        assert detail.result is not None and detail.result.status == "failed"
    finally:
        manager.shutdown()


def test_an_unexpected_error_still_ends_the_run_safely(tmp_path: Path) -> None:
    manager = manager_with(store_in(tmp_path), FakePipeline(raise_before=RuntimeError("boom")))
    try:
        detail = finished(manager, manager.start(SUBMISSION).id)

        assert detail.state == "failed" and detail.result is None
        assert detail.message == "Something went wrong. Please try again."
        assert "boom" not in detail.message and "Traceback" not in detail.message
        assert all(stage.status in {"skipped", "failed"} for stage in detail.stages), "no stage is left waiting"
    finally:
        manager.shutdown()


# --- cancelling ----------------------------------------------------------------------------------


def test_cancelling_stops_the_next_stage_and_keeps_what_finished(tmp_path: Path) -> None:
    gate = threading.Event()
    pipeline = FakePipeline(result(status="partial"), block=gate, block_at=STAGE_SEARCH)
    manager = manager_with(store_in(tmp_path), pipeline)
    try:
        run_id = manager.start(SUBMISSION).id
        assert pipeline.reached.wait(10), "the search stage is running"

        asked = manager.cancel(run_id)
        assert asked.cancel_requested is True
        assert asked.state == "running", "the state changes only once the work has stopped"
        gate.set()
        detail = finished(manager, run_id)

        assert detail.state == "cancelled" and detail.message == MSG_CANCELLED
        assert detail.result is not None, "what finished before the cancel is kept"
        statuses = stage_statuses(detail)
        assert statuses[STAGE_SEARCH] == "done" and statuses[STAGE_MARKET] == "cancelled"
        assert STAGE_MARKET not in pipeline.started_stages, "no stage started after the cancel"
        assert next(s for s in detail.stages if s.key == STAGE_COMPETITOR).message == MSG_STAGE_CANCELLED
    finally:
        gate.set()
        manager.shutdown()


def test_cancelling_an_ended_run_changes_nothing(manager: RunManager) -> None:
    run_id = manager.start(SUBMISSION).id
    before = finished(manager, run_id)

    after = manager.cancel(run_id)

    assert (after.state, after.message) == (before.state, before.message) == ("done", None)


def test_cancelling_an_unknown_run_is_reported(manager: RunManager) -> None:
    with pytest.raises(RunNotFoundError) as info:
        manager.cancel("absent")
    assert info.value.status_code == 404


# --- the concurrency limit -----------------------------------------------------------------------


def test_two_runs_work_at_once_and_a_third_is_refused(tmp_path: Path) -> None:
    gate = threading.Event()
    pipeline = FakePipeline(block=gate, block_at=STAGE_EXTRACTION)
    manager = manager_with(store_in(tmp_path), pipeline)
    try:
        first, second = manager.start(SUBMISSION), manager.start(SUBMISSION)

        with pytest.raises(RunLimitError) as info:
            manager.start(SUBMISSION)

        assert MAX_CONCURRENT_RUNS == 2
        assert info.value.status_code == 409
        assert info.value.user_message.startswith("A validation is already running")
        gate.set()
        assert finished(manager, first.id).state == "done"
        assert finished(manager, second.id).state == "done"

        third = manager.start(SUBMISSION)  # room again
        assert finished(manager, third.id).state == "done"
    finally:
        gate.set()
        manager.shutdown()


def test_shutdown_asks_every_run_to_stop(tmp_path: Path) -> None:
    gate = threading.Event()
    pipeline = FakePipeline(block=gate, block_at=STAGE_SEARCH)
    manager = manager_with(store_in(tmp_path), pipeline)
    run_id = manager.start(SUBMISSION).id
    assert pipeline.reached.wait(10)

    manager.shutdown()
    gate.set()

    assert manager.wait(run_id, 10)
    assert manager.get(run_id).state == "cancelled"
    with pytest.raises(RunLimitError):
        manager.start(SUBMISSION)


# --- history -------------------------------------------------------------------------------------


def test_finished_runs_are_listed_newest_first_with_their_status(manager: RunManager) -> None:
    first = manager.start(SUBMISSION).id
    finished(manager, first)
    second = manager.start(SUBMISSION).id
    finished(manager, second)

    rows = manager.list()

    assert [row.id for row in rows] == [second, first]
    assert all(row.state == "done" and row.status == "complete" for row in rows)
    assert all(row.title and row.industry for row in rows)


def test_a_run_survives_a_new_manager_on_the_same_file(tmp_path: Path) -> None:
    store = store_in(tmp_path)
    first = manager_with(store, FakePipeline())
    run_id = manager_with(store, FakePipeline()) and first.start(SUBMISSION).id
    finished(manager := first, run_id)
    manager.shutdown()

    again = RunManager(RunStore(tmp_path / "runs.db"), pipeline=FakePipeline())
    try:
        detail = again.get(run_id)

        assert detail.state == "done" and detail.result is not None
        assert detail.result.idea is not None and detail.submission == SUBMISSION
        assert [row.id for row in again.list()] == [run_id]
    finally:
        again.shutdown()


def test_renaming_keeps_the_new_title_through_the_run_and_afterwards(manager: RunManager) -> None:
    run_id = manager.start(SUBMISSION).id

    manager.rename(run_id, "Leaf scanner for cooperatives")
    finished(manager, run_id)

    assert manager.get(run_id).title == "Leaf scanner for cooperatives", "extraction does not overwrite it"
    assert [row.title for row in manager.list()] == ["Leaf scanner for cooperatives"]


def test_renaming_an_unknown_run_is_reported(manager: RunManager) -> None:
    with pytest.raises(RunNotFoundError):
        manager.rename("absent", "x")


def test_a_finished_run_can_be_deleted_but_a_going_one_cannot(tmp_path: Path) -> None:
    gate = threading.Event()
    pipeline = FakePipeline(block=gate, block_at=STAGE_SEARCH)
    manager = manager_with(store_in(tmp_path), pipeline)
    try:
        run_id = manager.start(SUBMISSION).id
        assert pipeline.reached.wait(10)

        with pytest.raises(RunActiveError) as info:
            manager.delete(run_id)
        assert info.value.status_code == 409

        gate.set()
        finished(manager, run_id)
        manager.delete(run_id)

        assert manager.list() == []
        with pytest.raises(RunNotFoundError):
            manager.get(run_id)
    finally:
        gate.set()
        manager.shutdown()


def test_deleting_an_unknown_run_is_reported(manager: RunManager) -> None:
    with pytest.raises(RunNotFoundError):
        manager.delete("absent")


def test_no_key_reaches_a_saved_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The founder's own text is stored, so a key pasted into it is redacted on the way in."""
    monkeypatch.setenv("TAVILY_API_KEY", SECRET)
    store = RunStore(tmp_path / "runs.db", secrets=(SECRET,))
    leaky = SUBMISSION.model_copy(update={"relevant_details": f"my key is {SECRET}"})
    manager = manager_with(store, FakePipeline())
    try:
        run_id = manager.start(leaky).id
        finished(manager, run_id)

        text = (tmp_path / "runs.db").read_bytes().decode("utf-8", "ignore")
        assert SECRET not in text
        assert SECRET not in json.dumps(store.get(run_id))
    finally:
        manager.shutdown()


def test_without_history_a_run_is_refused_rather_than_lost(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    path.write_bytes(b"not a database")
    manager = manager_with(RunStore(path), FakePipeline())
    try:
        with pytest.raises(HistoryUnavailableError) as info:
            manager.start(SUBMISSION)
        assert info.value.status_code == 503
    finally:
        manager.shutdown()


def test_a_run_whose_saved_row_cannot_be_read_is_reported_plainly(tmp_path: Path) -> None:
    store = store_in(tmp_path)
    manager = manager_with(store, FakePipeline())
    try:
        run_id = manager.start(SUBMISSION).id
        finished(manager, run_id)
        store.update(run_id, stages_json="{not json")

        with pytest.raises(HistoryUnavailableError) as info:
            manager.get(run_id)
        assert "Traceback" not in info.value.user_message
    finally:
        manager.shutdown()


def test_nothing_is_written_outside_the_temporary_folder(tmp_path: Path) -> None:
    """A guard for this suite: a run here writes only inside tmp_path.

    The project's own data/runs.db may already exist, because running the server by hand creates
    it, so absence cannot be asserted. What must hold is that this suite neither creates nor
    writes it, which is what comparing it before and after checks.
    """
    real = Path(__file__).resolve().parent.parent / "data" / "runs.db"
    before = real.stat().st_mtime_ns if real.exists() else None

    manager = manager_with(store_in(tmp_path), FakePipeline())
    try:
        finished(manager, manager.start(SUBMISSION).id)
        assert (tmp_path / "runs.db").exists()
    finally:
        manager.shutdown()

    after = real.stat().st_mtime_ns if real.exists() else None
    assert after == before, "the suite must not create or write the project's run database"

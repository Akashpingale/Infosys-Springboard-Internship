"""Run history in SQLite (KIRO_UI_UPGRADE_SPEC.md Section 10.2).

Every test writes to a temporary folder, so `data/runs.db` is never created or read here.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from config import DEFAULT_RUNS_DB_PATH, get_settings
from utils.errors import HistoryUnavailableError
from utils.run_store import MSG_INTERRUPTED, REDACTED, RunStore, now_iso

# Deliberately not shaped like any real key, so the project's secret scan stays silent on this file.
SECRET = "fake-configured-value-for-the-redaction-test"


def row(run_id: str = "r1", **fields: object) -> dict[str, object]:
    base = {
        "id": run_id,
        "title": "Leaf photo diagnosis",
        "renamed": 0,
        "industry": "Agriculture / AgriTech",
        "state": "queued",
        "result_status": None,
        "created_at": now_iso(),
        "started_at": None,
        "finished_at": None,
        "duration_s": None,
        "cancel_requested": 0,
        "message": None,
        "stages_json": json.dumps([{"key": "extraction", "status": "waiting"}]),
        "submission_json": json.dumps({"idea_description": "x"}),
        "idea_override_json": None,
        "result_json": None,
    }
    return {**base, **fields}


def test_the_default_location_is_the_gitignored_data_folder() -> None:
    assert DEFAULT_RUNS_DB_PATH == get_settings().runs_db_path
    assert DEFAULT_RUNS_DB_PATH.parent.name == "data" and DEFAULT_RUNS_DB_PATH.name == "runs.db"
    ignored = (Path(__file__).resolve().parent.parent / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/runs.db" in ignored, "a run database must never be committed"
    assert {"data/runs.db-wal", "data/runs.db-shm"} <= set(ignored), "SQLite's side files too"


def test_a_new_file_is_created_and_reports_itself_available(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "nested" / "runs.db")
    assert store.available and store.path.exists()
    assert store.list() == []


def test_a_run_is_written_read_listed_and_deleted(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    store.insert(row())

    saved = store.get("r1")
    assert saved is not None and saved["title"] == "Leaf photo diagnosis" and saved["state"] == "queued"
    assert [item["id"] for item in store.list()] == ["r1"]
    assert store.update("r1", state="done", result_status="complete", duration_s=3.0)
    assert store.get("r1")["state"] == "done"
    assert store.delete("r1") is True
    assert store.get("r1") is None and store.list() == []


def test_missing_rows_are_reported_rather_than_raising(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    assert store.get("absent") is None
    assert store.delete("absent") is False
    assert store.update("absent", state="done") is False


def test_the_newest_run_is_listed_first(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    store.insert(row("old", created_at="2026-10-01T10:00:00.000+00:00"))
    store.insert(row("new", created_at="2026-10-29T10:00:00.000+00:00"))
    assert [item["id"] for item in store.list()] == ["new", "old"]


def test_an_unknown_column_is_refused_instead_of_being_written(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    store.insert(row())
    with pytest.raises(ValueError, match="unknown run columns"):
        store.update("r1", nonsense="x")


def test_a_configured_key_is_replaced_before_anything_is_written(tmp_path: Path) -> None:
    """Rows hold the founder's input and the result only; a key found in either is redacted."""
    store = RunStore(tmp_path / "runs.db", secrets=(SECRET, None, ""))
    store.insert(row(message=f"failed using {SECRET}", submission_json=json.dumps({"idea_description": SECRET})))
    store.update("r1", result_json=json.dumps({"note": SECRET}))

    text = (tmp_path / "runs.db").read_bytes().decode("utf-8", "ignore")
    assert SECRET not in text and REDACTED in text
    saved = store.get("r1")
    assert SECRET not in json.dumps(saved) and REDACTED in saved["message"]


def test_a_short_value_is_never_treated_as_a_key(tmp_path: Path) -> None:
    """A real key is long; a short string such as an industry name must survive untouched."""
    store = RunStore(tmp_path / "runs.db", secrets=("app",))
    store.insert(row(title="An app for farmers"))
    assert store.get("r1")["title"] == "An app for farmers"


def test_a_run_interrupted_by_a_restart_is_marked_failed(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    first = RunStore(path)
    first.insert(row("queued-run", state="queued"))
    first.insert(row("running-run", state="running"))
    first.insert(row("done-run", state="done", result_status="complete", finished_at=now_iso()))

    second = RunStore(path)  # a restart

    assert {item["id"]: item["state"] for item in second.list()} == {
        "queued-run": "failed", "running-run": "failed", "done-run": "done"
    }
    interrupted = second.get("running-run")
    assert interrupted["message"] == MSG_INTERRUPTED and interrupted["finished_at"]
    assert second.get("done-run")["message"] is None, "a finished run is left alone"


def test_an_unreadable_file_is_left_alone_and_history_reports_itself_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    path.write_bytes(b"this is not a database")

    store = RunStore(path)

    assert store.available is False
    assert path.read_bytes() == b"this is not a database", "a file we cannot read is never overwritten"
    for call in (store.list, lambda: store.get("r1"), lambda: store.delete("r1")):
        with pytest.raises(HistoryUnavailableError) as info:
            call()
        assert info.value.status_code == 503 and "Traceback" not in info.value.user_message


def test_a_file_that_breaks_after_opening_still_answers_with_a_safe_error(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    store = RunStore(path)
    store.insert(row())
    path.write_bytes(b"corrupted after the first write")

    with pytest.raises(HistoryUnavailableError):
        store.list()


def test_the_table_survives_a_second_opening(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    RunStore(path).insert(row())
    again = RunStore(path)
    assert again.available and again.get("r1") is not None


def test_rows_are_written_with_the_declared_columns_only(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    RunStore(path).insert(row())
    with sqlite3.connect(path) as connection:
        columns = {item[1] for item in connection.execute("PRAGMA table_info(runs)")}
    assert columns == set(row()), "the table matches the row shape the manager writes"

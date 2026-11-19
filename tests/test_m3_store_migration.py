import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from models.chat import ChatMessage, ChatParagraph
from models.schemas import StrategyConstraints, StrategySourceKey
from tests.run_fakes import SUBMISSION, result
from utils.chat_store import ChatStore
from utils.errors import HistoryUnavailableError
from utils.run_manager import RunManager
from utils.run_store import REDACTED, RunStore, ensure_schema

ROOT = Path(__file__).resolve().parent.parent
REAL_DB = ROOT / "data" / "runs.db"
SECRET = "-".join(("planted", "configured", "value", "for", "chat", "redaction"))

OLD_COLUMNS = (
    "id", "title", "renamed", "industry", "state", "result_status", "created_at", "started_at", "finished_at",
    "duration_s", "cancel_requested", "message", "stages_json", "submission_json", "idea_override_json",
    "result_json",
)
NEW_COLUMNS = ("constraints_json", "include_strategy", "report_json", "report_fingerprint", "report_generated_at")
OLD_SCHEMA = """
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    renamed INTEGER NOT NULL DEFAULT 0,
    industry TEXT NOT NULL,
    state TEXT NOT NULL,
    result_status TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    duration_s REAL,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    stages_json TEXT NOT NULL,
    submission_json TEXT NOT NULL,
    idea_override_json TEXT,
    result_json TEXT
)
"""
FOUR_STAGES = ("extraction", "search", "market", "competitor")
STRATEGY_STAGES = ("swot_risk", "mvp_recommendation", "go_to_market")


def stages(keys: tuple[str, ...], status: str = "done") -> str:
    return json.dumps([
        {"key": key, "label": key, "status": status, "started_at": "2026-11-01T10:00:00.000+00:00",
         "duration_s": 1.0, "message": None}
        for key in keys
    ])


def old_row(run_id: str, state: str, result_status: str | None, result_json: str | None, **fields: Any) -> dict[str, Any]:
    base = {
        "id": run_id,
        "title": f"Saved run {run_id}",
        "renamed": 0,
        "industry": SUBMISSION.industry,
        "state": state,
        "result_status": result_status,
        "created_at": "2026-11-05T10:00:00.000+00:00",
        "started_at": "2026-11-01T10:00:01.000+00:00",
        "finished_at": "2026-11-01T10:02:00.000+00:00",
        "duration_s": 119.0,
        "cancel_requested": 0,
        "message": None,
        "stages_json": stages(FOUR_STAGES),
        "submission_json": SUBMISSION.model_dump_json(),
        "idea_override_json": None,
        "result_json": result_json,
    }
    return {**base, **fields}


OLD_ROWS = (
    old_row("done", "done", "complete", result().model_dump_json(), created_at="2026-11-01T10:00:00.000+00:00"),
    old_row("partial", "done", "partial", result("partial").model_dump_json(),
            message="Some parts could not be completed.", created_at="2026-11-02T10:00:00.000+00:00"),
    old_row("failed", "failed", None, None, message="We couldn't understand the idea.",
            stages_json=stages(FOUR_STAGES, "failed"), created_at="2026-11-03T10:00:00.000+00:00"),
    old_row("cancelled", "cancelled", None, None, cancel_requested=1,
            stages_json=stages(FOUR_STAGES, "cancelled"), created_at="2026-11-04T10:00:00.000+00:00"),
)


@pytest.fixture
def old_file(tmp_path: Path) -> Path:
    path = tmp_path / "old_runs.db"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(OLD_SCHEMA)
        connection.executemany(
            f"INSERT INTO runs ({', '.join(OLD_COLUMNS)}) VALUES ({', '.join('?' for _ in OLD_COLUMNS)})",
            [tuple(item[column] for column in OLD_COLUMNS) for item in OLD_ROWS],
        )
    return path


def snapshot(path: Path) -> dict[str, Any]:
    with closing(sqlite3.connect(path)) as connection:
        return {
            "schema_version": connection.execute("PRAGMA schema_version").fetchone()[0],
            "schema": connection.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY name").fetchall(),
            "runs": connection.execute("SELECT * FROM runs ORDER BY id").fetchall(),
            "chat": connection.execute("SELECT * FROM chat_messages ORDER BY run_id, seq").fetchall(),
        }


def columns_of(path: Path, table: str) -> list[tuple[Any, ...]]:
    with closing(sqlite3.connect(path)) as connection:
        return [tuple(column) for column in connection.execute(f"PRAGMA table_info({table})")]


def question(message_id: str, text: str = "Why is the first risk rated high?") -> ChatMessage:
    return ChatMessage(id=message_id, role="user", created_at="2026-11-10T10:00:00.000+00:00", text=text)


def answer(message_id: str) -> ChatMessage:
    return ChatMessage(
        id=message_id,
        role="assistant",
        created_at="2026-11-10T10:00:05.000+00:00",
        paragraphs=[ChatParagraph(text="It rests on the pricing gap in your results.", basis="ai_interpretation",
                                  sections=["risks"], sources=[StrategySourceKey(analysis="market", id="S1")])],
        follow_ups=["Which competitor is closest?"],
        used_sections=["risks"],
    )


def test_an_old_file_gains_the_new_columns_and_the_chat_table(old_file: Path) -> None:
    store = RunStore(old_file)

    assert store.available
    runs = columns_of(old_file, "runs")
    assert [column[1] for column in runs] == [*OLD_COLUMNS, *NEW_COLUMNS]
    added = {column[1]: (column[2], column[3], column[4]) for column in runs[len(OLD_COLUMNS):]}
    assert added == {"constraints_json": ("TEXT", 0, None), "include_strategy": ("INTEGER", 1, "0"), "report_json": ("TEXT", 0, None), "report_fingerprint": ("TEXT", 0, None), "report_generated_at": ("TEXT", 0, None)}
    chat = [(column[1], column[2], column[3], column[5]) for column in columns_of(old_file, "chat_messages")]
    assert chat == [
        ("id", "TEXT", 0, 1), ("run_id", "TEXT", 1, 0), ("seq", "INTEGER", 1, 0), ("role", "TEXT", 1, 0),
        ("content_json", "TEXT", 1, 0), ("status", "TEXT", 1, 0), ("created_at", "TEXT", 1, 0),
    ]
    with closing(sqlite3.connect(old_file)) as connection:
        indexes = connection.execute("PRAGMA index_list(chat_messages)").fetchall()
        named = [index[1] for index in indexes if index[1] == "chat_messages_run_seq"]
        assert named, "an index on (run_id, seq)"
        assert [item[2] for item in connection.execute("PRAGMA index_info(chat_messages_run_seq)")] == ["run_id", "seq"]


def test_old_rows_are_intact_and_read_through_the_unchanged_detail_path(old_file: Path) -> None:
    store = RunStore(old_file)

    assert [item["id"] for item in store.list()] == ["cancelled", "failed", "partial", "done"]
    for original in OLD_ROWS:
        migrated = store.get(original["id"])
        assert migrated == {**original, "constraints_json": None, "include_strategy": 0, "report_json": None, "report_fingerprint": None, "report_generated_at": None}
        assert RunManager._detail_from_row(migrated) == RunManager._detail_from_row(original)


def test_a_second_open_is_a_no_op(old_file: Path) -> None:
    RunStore(old_file)
    first = snapshot(old_file)

    again = RunStore(old_file)
    with closing(sqlite3.connect(old_file)) as connection, connection:
        ensure_schema(connection)

    assert again.available
    assert snapshot(old_file) == first
    assert len(first["runs"]) == len(OLD_ROWS)


def test_a_new_file_has_the_same_schema_as_a_migrated_one(old_file: Path, tmp_path: Path) -> None:
    fresh = tmp_path / "fresh.db"
    RunStore(fresh)
    RunStore(old_file)

    for table in ("runs", "chat_messages"):
        assert columns_of(fresh, table) == columns_of(old_file, table)
    store = RunStore(fresh)
    store.insert(old_row("newrow", "queued", None, None))
    assert store.get("newrow")["include_strategy"] == 0 and store.get("newrow")["constraints_json"] is None


def test_a_strategy_job_can_run_on_an_old_row(old_file: Path) -> None:
    store = RunStore(old_file)
    constraints = StrategyConstraints(team_size=2, months_to_mvp=3, budget_level="bootstrapped")
    seven = stages(FOUR_STAGES + STRATEGY_STAGES)

    assert store.update("done", state="running", include_strategy=1, constraints_json=constraints.model_dump_json())
    assert store.update(
        "done", state="done", result_status="complete", stages_json=seven,
        result_json=result(constraints=constraints).model_dump_json(),
    )

    saved = store.get("done")
    assert saved["include_strategy"] == 1
    assert StrategyConstraints.model_validate_json(saved["constraints_json"]) == constraints
    detail = RunManager._detail_from_row(saved)
    assert detail.state == "done" and detail.result.constraints == constraints
    assert [stage.key for stage in detail.stages] == [*FOUR_STAGES, *STRATEGY_STAGES]
    assert detail.submission == SUBMISSION


def test_chat_works_on_an_old_row(old_file: Path) -> None:
    chat = ChatStore(RunStore(old_file))

    assert chat.append("done", question("q1"), answer("a1"))
    assert chat.append("done", question("q2", "What should I build first?"))

    assert [message.id for message in chat.list("done")] == ["q1", "a1", "q2"]
    assert chat.list("done")[1] == answer("a1")
    assert chat.count("done") == 3 and chat.count("done", "user") == 2 and chat.count("done", "assistant") == 1
    with closing(sqlite3.connect(old_file)) as connection:
        rows = connection.execute("SELECT id, run_id, seq, role, status FROM chat_messages ORDER BY seq").fetchall()
    assert rows == [("q1", "done", 1, "user", "ok"), ("a1", "done", 2, "assistant", "ok"), ("q2", "done", 3, "user", "ok")]

    assert chat.clear("done") == 3
    assert chat.list("done") == [] and chat.count("done") == 0
    assert chat.append("done", question("q3"))
    assert [message.id for message in chat.list("done")] == ["q3"]


def test_chat_for_a_missing_run_is_refused_and_nothing_is_stored(old_file: Path) -> None:
    chat = ChatStore(RunStore(old_file))

    assert chat.append("absent", question("q1")) is False
    assert chat.list("absent") == [] and chat.count("absent") == 0 and chat.clear("absent") == 0


def test_deleting_a_run_removes_its_chat_and_only_its_chat(old_file: Path) -> None:
    store = RunStore(old_file)
    chat = ChatStore(store)
    chat.append("done", question("q1"), answer("a1"))
    chat.append("partial", question("q2"))

    assert store.delete("done") is True

    assert store.get("done") is None
    assert chat.list("done") == [] and chat.count("done") == 0
    assert [message.id for message in chat.list("partial")] == ["q2"]
    with closing(sqlite3.connect(old_file)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM chat_messages WHERE run_id = 'done'").fetchone()[0] == 0


def test_a_configured_key_in_a_question_or_constraints_is_not_persisted(old_file: Path) -> None:
    store = RunStore(old_file, secrets=(SECRET,))
    chat = ChatStore(store)
    constraints = StrategyConstraints(launch_region=f"Pune {SECRET}")

    assert chat.append("done", question("q1", f"Is my key {SECRET} safe?"))
    assert store.update("done", constraints_json=constraints.model_dump_json())

    assert SECRET not in old_file.read_bytes().decode("utf-8", "ignore")
    assert chat.list("done")[0].text == f"Is my key {REDACTED} safe?"
    assert REDACTED in store.get("done")["constraints_json"]
    assert SECRET not in json.dumps(store.get("done"))


def test_chat_on_an_unreadable_file_answers_with_the_safe_error(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    path.write_bytes(b"this is not a database")
    chat = ChatStore(RunStore(path))

    for call in (lambda: chat.append("r1", question("q1")), lambda: chat.list("r1"),
                 lambda: chat.count("r1"), lambda: chat.clear("r1")):
        with pytest.raises(HistoryUnavailableError):
            call()
    assert path.read_bytes() == b"this is not a database"


def test_importing_the_app_creates_no_run_database(tmp_path: Path) -> None:
    target = tmp_path / "absent" / "runs.db"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", "import app; from utils import run_manager; assert run_manager._default is None"],
        cwd=ROOT,
        env={**os.environ, "RUNS_DB_PATH": str(target)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert not target.exists() and not target.parent.exists()


def test_this_suite_never_touches_the_real_run_database(old_file: Path) -> None:
    side_files = [REAL_DB.with_name(REAL_DB.name + suffix) for suffix in ("-wal", "-shm", "-journal")]
    before = REAL_DB.stat().st_mtime_ns if REAL_DB.exists() else None
    sides_before = [side.exists() for side in side_files]

    store = RunStore(old_file)
    chat = ChatStore(store)
    chat.append("done", question("q1"))
    store.delete("done")

    after = REAL_DB.stat().st_mtime_ns if REAL_DB.exists() else None
    assert after == before, "the migration tests must not create or write the project's run database"
    assert [side.exists() for side in side_files] == sides_before

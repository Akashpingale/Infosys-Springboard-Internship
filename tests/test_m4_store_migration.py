import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import create_app
from models.report import ReportDocument
from models.schemas import PipelineResult
from tests.m4_report_fixtures_synthetic import synthetic_no_strategy, synthetic_partial
from tests.run_fakes import manager_with
from tests.test_m3_store_migration import (
    FOUR_STAGES,
    OLD_COLUMNS,
    OLD_SCHEMA,
    REAL_DB,
    STRATEGY_STAGES,
    columns_of,
    old_row,
    snapshot,
    stages,
)
from tests.test_m4_report_agent import LIVE, SAVED, load, use_writer
from utils.run_manager import RunManager
from utils.run_store import CHAT_SCHEMA, REDACTED, REPORT_COLUMNS, RunStore

M3_COLUMNS = ("constraints_json", "include_strategy")
M3_ADDED = ("ALTER TABLE runs ADD COLUMN constraints_json TEXT",
            "ALTER TABLE runs ADD COLUMN include_strategy INTEGER NOT NULL DEFAULT 0")
SECRET = "-".join(("planted", "configured", "value", "for", "report", "column"))
STORED = {path.stem: path for path in [*SAVED, *LIVE]}


def old_rows() -> list[dict[str, Any]]:
    return [
        old_row("complete", "done", "complete", synthetic_no_strategy().model_dump_json(),
                created_at="2026-11-01T10:00:00.000+00:00"),
        old_row("partial", "done", "partial", synthetic_partial().model_dump_json(),
                message="Some parts could not be completed.", created_at="2026-11-02T10:00:00.000+00:00"),
        old_row("failed", "failed", None, None, stages_json=stages(FOUR_STAGES, "failed"),
                created_at="2026-11-03T10:00:00.000+00:00"),
    ]


def write_file(path: Path, rows: list[dict[str, Any]], *, milestone: int) -> Path:
    columns = OLD_COLUMNS if milestone < 3 else (*OLD_COLUMNS, *M3_COLUMNS)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(OLD_SCHEMA)
        if milestone >= 3:
            for statement in M3_ADDED:
                connection.execute(statement)
            connection.execute(CHAT_SCHEMA)
        connection.executemany(
            f"INSERT INTO runs ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            [tuple(row.get(column, 0 if column == "include_strategy" else None) for column in columns) for row in rows],
        )
    return path


@pytest.fixture(params=[2, 3], ids=["milestone-1-2-file", "milestone-3-file"])
def old_file(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    return write_file(tmp_path / f"m{request.param}_runs.db", old_rows(), milestone=request.param)


@pytest.fixture
def served(tmp_path: Path):
    made = []

    def factory(path: Path, secrets: tuple[str, ...] = ()) -> TestClient:
        manager = manager_with(RunStore(path, secrets=secrets), lambda *args, **kwargs: None)
        app = create_app()
        app.state.run_manager = manager
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()
        made.append((client, manager))
        return client

    yield factory
    for client, manager in made:
        client.__exit__(None, None, None)
        manager.shutdown()


def test_an_old_file_gains_the_report_columns_and_keeps_its_rows(old_file: Path) -> None:
    before = {row["id"]: row for row in old_rows()}

    store = RunStore(old_file)

    assert store.available
    names = [column[1] for column in columns_of(old_file, "runs")]
    assert names == [*OLD_COLUMNS, *M3_COLUMNS, *REPORT_COLUMNS]
    added = {column[1]: (column[2], column[3], column[4]) for column in columns_of(old_file, "runs")[-3:]}
    assert added == {name: ("TEXT", 0, None) for name in REPORT_COLUMNS}
    for run_id, original in before.items():
        migrated = store.get(run_id)
        assert {key: migrated[key] for key in OLD_COLUMNS} == {key: original[key] for key in OLD_COLUMNS}
        assert [migrated[name] for name in REPORT_COLUMNS] == [None, None, None]
        assert RunManager._detail_from_row(migrated).report.exists is False


def test_opening_a_migrated_file_again_changes_nothing(old_file: Path) -> None:
    RunStore(old_file)
    first = snapshot(old_file)

    RunStore(old_file)

    assert snapshot(old_file) == first


def test_a_new_file_and_a_migrated_one_have_the_same_runs_table(old_file: Path, tmp_path: Path) -> None:
    fresh = tmp_path / "fresh.db"
    RunStore(fresh)
    RunStore(old_file)

    assert columns_of(fresh, "runs") == columns_of(old_file, "runs")


def test_a_report_can_be_made_for_an_old_complete_row_and_an_old_partial_row(
    monkeypatch: pytest.MonkeyPatch, served, old_file: Path
) -> None:
    writer = use_writer(monkeypatch)
    client = served(old_file)

    complete = client.post("/api/runs/complete/report")
    partial = client.post("/api/runs/partial/report")
    failed = client.post("/api/runs/failed/report")

    assert complete.status_code == 200, complete.text
    assert partial.status_code == 200, partial.text
    assert complete.json()["meta"]["run_status"] == "complete"
    assert "swot" in {entry["id"] for entry in complete.json()["meta"]["sections_missing"]}
    assert partial.json()["meta"]["run_status"] == "partial"
    assert failed.status_code == 409 and failed.json()["error"]["code"] == "report_unavailable"
    assert len(writer.calls) == 2
    for run_id in ("complete", "partial"):
        assert client.get(f"/api/runs/{run_id}").json()["report"]["exists"] is True
        assert client.get(f"/api/runs/{run_id}/report/markdown").status_code == 200


def test_deleting_an_old_row_removes_its_report(monkeypatch: pytest.MonkeyPatch, served, old_file: Path) -> None:
    use_writer(monkeypatch)
    client = served(old_file)
    assert client.post("/api/runs/complete/report", json={"narrative": False}).status_code == 200

    assert client.delete("/api/runs/complete").status_code == 204

    assert client.get("/api/runs/complete/report").json()["error"]["code"] == "run_not_found"
    with closing(sqlite3.connect(old_file)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs WHERE id = 'complete'").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM runs WHERE report_json IS NOT NULL").fetchone()[0] == 0


def test_the_existing_key_redaction_covers_the_report_columns(tmp_path: Path) -> None:
    path = write_file(tmp_path / "runs.db", old_rows(), milestone=3)
    store = RunStore(path, secrets=(SECRET,))

    assert store.update("complete", report_json=json.dumps({"text": f"a {SECRET} b"}),
                        report_fingerprint=f"f{SECRET}", report_generated_at=SECRET)

    assert SECRET not in path.read_bytes().decode("utf-8", "ignore")
    row = store.get("complete")
    assert json.loads(row["report_json"]) == {"text": f"a {REDACTED} b"}
    assert row["report_fingerprint"] == f"f{REDACTED}" and row["report_generated_at"] == REDACTED


@pytest.mark.parametrize("name", sorted(STORED))
def test_every_saved_milestone_result_gets_a_report_from_an_old_file(
    monkeypatch: pytest.MonkeyPatch, served, tmp_path: Path, name: str
) -> None:
    result: PipelineResult = load(STORED[name])
    keys = STRATEGY_STAGES if result.swot is not None else ()
    row = old_row(name, "done", result.status, result.model_dump_json(), stages_json=stages(FOUR_STAGES + keys))
    client = served(write_file(tmp_path / "saved.db", [row], milestone=2))

    response = client.post(f"/api/runs/{name}/report", json={"narrative": False})

    assert response.status_code == 200, response.text
    document = ReportDocument.model_validate(response.json())
    assert (document.meta.consistency.passed_count, document.meta.consistency.total_count) == (12, 12)
    assert client.get(f"/api/runs/{name}").json()["report"]["stale"] is False


def test_this_suite_never_touches_the_real_run_database(tmp_path: Path) -> None:
    side_files = [REAL_DB.with_name(REAL_DB.name + suffix) for suffix in ("-wal", "-shm", "-journal")]
    before = REAL_DB.stat().st_mtime_ns if REAL_DB.exists() else None
    sides_before = [side.exists() for side in side_files]

    path = write_file(tmp_path / "runs.db", old_rows(), milestone=2)
    store = RunStore(path)
    store.update("complete", report_json="{}")
    store.delete("complete")

    after = REAL_DB.stat().st_mtime_ns if REAL_DB.exists() else None
    assert after == before
    assert [side.exists() for side in side_files] == sides_before

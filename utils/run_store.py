"""Run history in SQLite (KIRO_UI_UPGRADE_SPEC.md Section 10.2). Standard library only.

One row per run: the submission, the reviewed idea if any, the stages, the result, the state and
the timestamps. No key or request header is stored: rows hold only the founder's input and the
pipeline result, and any configured key value found in them is replaced before writing.

A file that cannot be opened or read (missing folder rights, a corrupt file) is never deleted or
overwritten. History then reports itself unavailable, and every call raises
HistoryUnavailableError, so the run routes answer 503 while the rest of the API keeps working.
"""

import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.errors import HistoryUnavailableError

logger = logging.getLogger(__name__)

COLUMNS = (
    "id",
    "title",
    "renamed",
    "industry",
    "state",
    "result_status",
    "created_at",
    "started_at",
    "finished_at",
    "duration_s",
    "cancel_requested",
    "message",
    "stages_json",
    "submission_json",
    "idea_override_json",
    "result_json",
)
LIST_COLUMNS = ("id", "title", "industry", "state", "result_status", "created_at", "duration_s")
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
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
REDACTED = "[redacted]"
MIN_SECRET_CHARS = 8
BUSY_TIMEOUT_S = 10
MSG_INTERRUPTED = "The server stopped before this validation finished."


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class RunStore:
    def __init__(self, path: Path, secrets: tuple[str | None, ...] = ()) -> None:
        self.path = Path(path)
        self._secrets = tuple(secret for secret in secrets if secret and len(secret) >= MIN_SECRET_CHARS)
        self._lock = threading.Lock()
        self.available = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as connection:
                connection.execute(SCHEMA)
                # A run that was going when the server stopped can never finish now.
                interrupted = connection.execute(
                    "UPDATE runs SET state = 'failed', message = ?, finished_at = COALESCE(finished_at, ?) "
                    "WHERE state IN ('queued', 'running')",
                    (MSG_INTERRUPTED, now_iso()),
                ).rowcount
            self.available = True
            if interrupted:
                logger.info("marked %d interrupted run(s) as failed", interrupted)
        except (sqlite3.Error, OSError) as exc:
            logger.warning("run history is not available (%s); the file was left as it is", type(exc).__name__)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=BUSY_TIMEOUT_S)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @contextmanager
    def _use(self) -> Iterator[sqlite3.Connection]:
        if not self.available:
            raise HistoryUnavailableError()
        try:
            with self._lock, self._connection() as connection:
                yield connection
        except sqlite3.Error as exc:
            logger.warning("run history query failed (%s)", type(exc).__name__)
            raise HistoryUnavailableError() from None

    def _clean(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        for secret in self._secrets:
            value = value.replace(secret, REDACTED)
        return value

    def insert(self, row: dict[str, Any]) -> None:
        values = [self._clean(row.get(column)) for column in COLUMNS]
        with self._use() as connection:
            connection.execute(
                f"INSERT INTO runs ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})", values
            )

    def update(self, run_id: str, **fields: Any) -> bool:
        unknown = set(fields) - set(COLUMNS[1:])
        if unknown:
            raise ValueError(f"unknown run columns: {sorted(unknown)}")
        if not fields:
            return True
        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = [self._clean(value) for value in fields.values()]
        with self._use() as connection:
            return connection.execute(f"UPDATE runs SET {assignments} WHERE id = ?", (*values, run_id)).rowcount > 0

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._use() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row is not None else None

    def list(self) -> list[dict[str, Any]]:
        with self._use() as connection:
            rows = connection.execute(
                f"SELECT {', '.join(LIST_COLUMNS)} FROM runs ORDER BY created_at DESC, rowid DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def delete(self, run_id: str) -> bool:
        with self._use() as connection:
            return connection.execute("DELETE FROM runs WHERE id = ?", (run_id,)).rowcount > 0

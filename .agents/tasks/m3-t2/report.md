# Milestone 3 T2 final report: store migration and chat store

Status: all 7 verification items pass. I re-ran them in this step on the current working tree (branch `main`, HEAD `a098aef`, nothing committed). This step changed no project files, did not start `app.py`, ran no git write operations and did not begin T3.

## Files changed or created

| File | Status | Purpose |
|---|---|---|
| `utils/run_store.py` | modified (+42/-2) | Adds the two `runs` columns, the `chat_messages` table and index, an idempotent `ensure_schema(connection)`, default-aware `insert`, and a `delete` that also removes the run's chat. |
| `utils/chat_store.py` | new | `ChatStore(store)` with `append`, `list`, `count`, `clear`. It works on the same `RunStore` file and connection helper, and runs values through the same redaction. |
| `tests/test_m3_store_migration.py` | new (12 tests) | Migration, idempotency, compatibility, chat, cascade, redaction, lazy-import and real-DB-untouched tests. All of them use pytest `tmp_path` files. |
| `tests/test_run_store.py` | modified (1 line) | Not in the expected list. The user approved this change (option A, recorded in coder-notes.md). Line 162 now expects the 16 old columns plus `constraints_json` and `include_strategy`, and the assertion is still an exact set comparison. Without the change, the existing test fails once 13.1's columns are added. |

`utils/run_manager.py`, `app.py`, `routes/`, `agents/`, `web/`, `frontend/`, the plan, `KIRO_*.md` and `docs/assets/ui_v2/` are unmodified (`git status --porcelain` on those paths printed nothing).

## How each requirement was met

- **13.1 columns.** `ADDED_COLUMNS` holds `constraints_json TEXT` and `include_strategy INTEGER NOT NULL DEFAULT 0`. `ensure_schema` runs `CREATE TABLE IF NOT EXISTS runs`, reads `PRAGMA table_info(runs)`, and runs `ALTER TABLE runs ADD COLUMN` only for columns that are missing. Old rows read `NULL` and `0`. `COLUMNS` grows from 16 to 18 entries.
- **13.1 chat table.** `chat_messages(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, seq INTEGER NOT NULL, role TEXT NOT NULL, content_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)` and index `chat_messages_run_seq ON (run_id, seq)`. Both use `IF NOT EXISTS`. `test_an_old_file_gains_the_new_columns_and_the_chat_table` asserts the exact column types, NOT NULL flags, defaults, primary key and index columns.
- **ensure_schema idempotent.** It only creates or adds what is missing and never rewrites rows. `test_a_second_open_is_a_no_op` opens the migrated file again, calls `ensure_schema` directly as well, and asserts that `PRAGMA schema_version`, all of `sqlite_master`, every `runs` row and every `chat_messages` row are identical to the first snapshot.
- **Chat append, list, count, clear.** `append(run_id, *messages) -> bool` returns `False` and stores nothing when the run does not exist. It writes several messages in one transaction, continuing `seq` from `MAX(seq)`, and stores `content_json = ChatMessage.model_dump_json()` using the T1 model. `list` returns `ChatMessage` objects ordered by `seq`. `count(run_id, role=None)` and `clear(run_id) -> int` return counts. Covered by `test_chat_works_on_an_old_row` (seq 1..3) and `test_chat_for_a_missing_run_is_refused_and_nothing_is_stored`.
- **Cascade delete.** `RunStore.delete` deletes `chat_messages WHERE run_id = ?` and then the run inside one `_use()` connection context, which is one transaction. Foreign keys are not used. `test_deleting_a_run_removes_its_chat_and_only_its_chat` passes.
- **Redaction of constraints_json and content_json.** `ChatStore.append` passes every value, including `content_json`, through `RunStore._clean`. `constraints_json` goes through the existing `insert`/`update` path, which already cleans values. `test_a_configured_key_in_a_question_or_constraints_is_not_persisted` builds a fake key from parts, puts it in a question and in the constraints, and asserts it is stored as `[redacted]`, including a raw-bytes check of the file.
- **13.3 stored vs not stored.** Chat rows hold only the `ChatMessage` JSON, its status and timestamps. The only new log line is `run history: added column %s`, which logs a column name and never question text or secrets.
- **13.4 compatibility test.** The fixture builds a 16-column old-schema file with cancelled, failed, partial and done rows. Tests cover: rows intact (dict equality plus the new defaults); new columns present; a fresh file has the same schema as a migrated one and inserts default `include_strategy = 0`; chat works on an old row. The plan says "a strategy job can run on an old row", and strategy jobs do not exist until T4/T8, so this is tested at store level. `test_a_strategy_job_can_run_on_an_old_row` updates a migrated row to running with `include_strategy=1` and `constraints_json`, then to done with seven stages and `PipelineResult.constraints`, then reads it back through `get` and `_detail_from_row`.
- **`_detail_from_row` unchanged.** Its real location is `RunManager._detail_from_row`, a `@staticmethod` in `utils/run_manager.py`, defined at line 204 and called from `RunManager.get` at line 268. The file is unmodified. The function reads row keys by name, so the two extra keys are ignored. `test_old_rows_are_intact_and_read_through_the_unchanged_detail_path` asserts that it returns an equal `RunDetail` for each original row and its migrated row.
- **Lazy `default_manager()`.** `run_manager.py` is unchanged (`_default: RunManager | None = None`, built on first use). The store migrates only when a `RunStore` is constructed, and nothing does that at import time. `test_importing_the_app_creates_no_run_database` checks this in a subprocess, and verification item 3 checks it again separately.

## Verification results (run in this step)

1. **T2 tests.** `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_store_migration.py` gave `12 passed, 1 warning in 2.39s`. The warning is the existing Starlette `httpx` deprecation warning.
2. **Full backend suite.** `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE` gave `1772 passed, 1 warning in 30.83s`. That is the 1760 baseline plus 12 new tests, with 0 failures or errors and the same single warning.
3. **Lazy check.** In a fresh interpreter, with `RUNS_DB_PATH` set to a non-existent `%TEMP%\m3t2_lazy_<guid>\runs.db`, I ran `import app; from app import app`. Output: `app imported: FastAPI`, `default_manager built: False`, target file exists after import `False`, target folder exists after import `False`. PASS.
4. **Idempotency.** `test_a_second_open_is_a_no_op` passed within items 1 and 2. It compares schema_version, sqlite_master, runs rows and chat rows before and after a second open plus a direct `ensure_schema` call. PASS.
5. **`data/runs.db`.** Before and after all runs: SHA-256 `00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D`, 311296 bytes, LastWriteTimeUtc `2026-11-08T15:31:17.0443165Z`. All three match the pre-edit baseline. A read-only URI open (`?mode=ro`) showed 9 rows, 16 columns in `runs`, no `constraints_json`, and only the table `runs`, so the real file is not migrated. `runs.db-wal`, `runs.db-shm` and `runs.db-journal` do not exist, and `data/` holds only `runs.db` and `test_ideas`. The backup `C:\Users\akash\Infosys-Springboard-backups\runs_20261110_114900.db` exists and was not opened. PASS.
6. **`git status --porcelain`.**
   ```
    M .env.example
    M config.py
    M models/api.py
    M models/schemas.py
    M tests/test_run_store.py
    M utils/errors.py
    M utils/run_store.py
   ?? .agents/
   ?? models/chat.py
   ?? models/strategy_drafts.py
   ?? tests/test_m3_schemas.py
   ?? tests/test_m3_store_migration.py
   ?? utils/chat_store.py
   ```
   T2 accounts for `utils/run_store.py`, `utils/chat_store.py`, `tests/test_m3_store_migration.py`, and `tests/test_run_store.py` (user-approved). All 8 T1 files hash identically to the coder-notes baseline, so T1 files were not modified further:
   - `.env.example` `0EE7C4BF150AC001EE42C04E7CAA0463A548DD7B464481430C65E512D6047C53`
   - `config.py` `0E5BD22FD2CD8BD5F562228EB4EFB00C5AC8F3AE553A2F2CBC7EF7EFCAB58A6E`
   - `models/api.py` `C0B2D6E76C41A9BC089F910C32A7364F74B7E1FE96DBAC070C1B3DCED70E3F8A`
   - `models/schemas.py` `46C02616B345E0B11E5EFFF56B6247771FFB110C78E921DD6F4ED813FCE41BCF`
   - `utils/errors.py` `D931AF3B70510EBA924467852B1392510AD5CFEFBFD9AC22EE94704F7AEE105A`
   - `models/chat.py` `60F45CD64D7204CF0FE694A6BA1D99F9C9C024D94ED77B60DB0F8C5D39910BEA`
   - `models/strategy_drafts.py` `01E7BBBF762864CCC21250E0407989137190EB007BC2B38F762898F70FDFE8D0`
   - `tests/test_m3_schemas.py` `1BAB66868D468410891653819765FF5EB2325F54932B3EA33AEF4AC1A1ED7026`

   PASS, with the approved fourth file noted.
7. **Secret scan.** I scanned `utils/run_store.py`, `utils/chat_store.py`, `tests/test_m3_store_migration.py` and `tests/test_run_store.py`. Token patterns (`AIza…`, `gsk_…`, `tvly-…`, `sk-…`, `Bearer <token>`, `PRIVATE KEY`) gave 0 hits. A looser bare-substring search for the same prefixes also gave 0 hits. No `.env` file was opened. PASS.

## Plan-vs-code conflicts and unresolved issues

- **Existing test pinned the column set.** `tests/test_run_store.py::test_rows_are_written_with_the_declared_columns_only` asserted exactly the 16 old columns, which conflicts with 13.1. The user chose option A: a one-line, add-only edit that keeps the exact set comparison. This means four files changed instead of the three the task listed.
- **`has_strategy` deferred.** Plan 17.2 lists `has_strategy` under `run_store.py`, but it is an API list-row field (12.1) and would change `GET /api/runs`. It was left for T8. T2's requirement line (13.1-13.4) does not include it.
- **Strategy on an old row tested at store level only (13.4).** Strategy jobs do not exist until T4/T8, so only the store columns and the read path are tested now.
- **Chat not wired yet.** Chat is not connected to `default_manager()` or to routes. That belongs to T11.
- **Real file migrates on the next backend start.** The real `data/runs.db` is still on the old 16-column schema. The first backend start (`app.py`) after T2 will run `ensure_schema` on it and add the two columns and the chat table in place. The rows are unchanged, but the file hash and mtime will change. The verified backup above is available before that happens.
- No failing tests and no other unresolved issues.

Stopped after T2 verification. T3 not started.

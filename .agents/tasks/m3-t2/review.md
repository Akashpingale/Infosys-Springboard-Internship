# M3 T2 review (store migration and chat store)

Verdict: APPROVED. No blockers found.

## Evidence checked

- `git status --porcelain`: T2 touched `utils/run_store.py` (M), `tests/test_run_store.py` (M), `utils/chat_store.py` (new), `tests/test_m3_store_migration.py` (new). `utils/run_manager.py`, routes, agents, web/frontend and the plan are unmodified.
- T1 files: SHA-256 of `.env.example`, `config.py`, `models/api.py`, `models/schemas.py`, `utils/errors.py`, `models/chat.py`, `models/strategy_drafts.py`, `tests/test_m3_schemas.py` all match the hashes in coder-notes.md.
- `data/runs.db`: SHA-256 00A4F859...8337D, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17.0443165Z, identical to baseline; `data/` holds only `runs.db` and `test_ideas` (no -wal/-shm). Not opened by this review.

## Requirements against the diff

- 13.1 columns: `ensure_schema` (run_store.py:95-107) runs `CREATE TABLE IF NOT EXISTS runs`, reads `PRAGMA table_info(runs)`, and issues `ALTER TABLE ADD COLUMN` only for missing `constraints_json TEXT` and `include_strategy INTEGER NOT NULL DEFAULT 0`. Old rows read NULL and 0.
- 13.1 chat table: `CHAT_SCHEMA` matches the seven columns and constraints in the plan; `CHAT_INDEX` on `(run_id, seq)`; both `IF NOT EXISTS`.
- 13.1 cascade: `RunStore.delete` (run_store.py:190-194) deletes `chat_messages` then the run inside one `_use()` connection context (single transaction), no foreign keys.
- Idempotent: a second open adds nothing; `test_a_second_open_is_a_no_op` compares `schema_version`, `sqlite_master`, runs and chat rows.
- 13.2 redaction: `ChatStore.append` passes every value, including `content_json`, through `RunStore._clean`; `constraints_json` goes through `update`/`insert`, which already clean. Tested with a key built from parts, including a raw-bytes check of the file.
- 13.3: chat rows hold only the `ChatMessage` JSON (T1 model reused), status and timestamps. The only new log line names a column, never message text.
- 13.4: old-schema fixture built from the 16-column list; rows intact (dict equality plus defaults); new columns present; strategy-on-old-row interpreted at store level (update/get of the new columns, seven stages, `PipelineResult.constraints`), as the brief allowed; chat on an old row.
- `_detail_from_row`: real location `RunManager._detail_from_row`, a staticmethod in `utils/run_manager.py` (about lines 204-221). The file is unmodified; the function reads keys by name, so the two extra row keys are ignored. The test asserts equal `RunDetail` for each pre- and post-migration row.
- Insert compatibility: `RunManager` inserts rows without the new keys; `insert` falls back to `COLUMN_DEFAULTS` (include_strategy 0) and NULL, so the NOT NULL column cannot fail. `update` accepts the new columns through `COLUMNS[1:]`.
- Lazy `default_manager()`: run_manager.py is unchanged; a subprocess test imports `app` with `RUNS_DB_PATH` (the real setting name, config.py:200) pointed at a missing tmp path and asserts no file and `_default is None`.
- Real database untouched by tests: every test uses `tmp_path`; the mtime_ns and side-file check copies the existing pattern.

## Existing test change

`tests/test_run_store.py:162` gains `| {"constraints_json", "include_strategy"}` in an exact set comparison. The task forbids editing existing tests unless the user approves. coder-notes.md records that the coder raised the conflict and the user chose option A. The assertion is still an exact set comparison, so it is no weaker. I treated this as an approved trade-off.

## Verification evidence (from coder-notes.md, not re-run)

- `pytest tests/test_m3_store_migration.py`: 12 passed.
- Full backend suite: 1772 passed (baseline 1760 + 12), 0 failed.
- Lazy-import check, real-DB fingerprint (hash, size, mtime, 9 rows read-only, 16 columns, no -wal/-shm) and secret scan: all recorded as clean.

## Noted, not blocking

- `has_strategy` (plan 17.2 lists it under run_store.py) was deferred to the API task. T2's requirement line (13.1-13.4) does not include it, and the coder notes record the deferral.

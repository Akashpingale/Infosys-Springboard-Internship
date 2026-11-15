# M3 T2 coder notes

## Baseline fingerprints (recorded before the first edit, iteration 1)

data/runs.db
- SHA-256: 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D
- Size: 311296
- LastWriteTimeUtc: 2026-11-08T15:31:17.0443165Z
- data/ contains only runs.db and test_ideas/ (no runs.db-wal / runs.db-shm)

T1 uncommitted files (SHA-256)
- .env.example            0EE7C4BF150AC001EE42C04E7CAA0463A548DD7B464481430C65E512D6047C53
- config.py               0E5BD22FD2CD8BD5F562228EB4EFB00C5AC8F3AE553A2F2CBC7EF7EFCAB58A6E
- models/api.py           C0B2D6E76C41A9BC089F910C32A7364F74B7E1FE96DBAC070C1B3DCED70E3F8A
- models/schemas.py       46C02616B345E0B11E5EFFF56B6247771FFB110C78E921DD6F4ED813FCE41BCF
- utils/errors.py         D931AF3B70510EBA924467852B1392510AD5CFEFBFD9AC22EE94704F7AEE105A
- models/chat.py          60F45CD64D7204CF0FE694A6BA1D99F9C9C024D94ED77B60DB0F8C5D39910BEA
- models/strategy_drafts.py 01E7BBBF762864CCC21250E0407989137190EB007BC2B38F762898F70FDFE8D0
- tests/test_m3_schemas.py 1BAB66868D468410891653819765FF5EB2325F54932B3EA33AEF4AC1A1ED7026

## Findings before editing (iteration 1)

- `_detail_from_row` real name/location: `RunManager._detail_from_row` (a `@staticmethod`) in
  `utils/run_manager.py`, lines 204-221, called from `RunManager.get` (line 268). It reads row keys by
  name, so extra columns in the row dict are ignored. Not to be changed.
- Blocking conflict: `tests/test_run_store.py::test_rows_are_written_with_the_declared_columns_only`
  (lines 157-162) asserts `PRAGMA table_info(runs)` equals exactly the 16 old columns. Plan 13.1 adds
  `constraints_json` and `include_strategy` to `runs`, so that existing test fails as written. 20.4
  does not list this test. Asked the user (send_message warning) which way to go; no source edits made.
- User answer: option A. Add the two columns to `runs`; make one add-only change to that test so the
  expected set is the 16 old columns plus `constraints_json` and `include_strategy` (still an exact
  set comparison). No other existing test pins the column set (grep for `table_info`, `sqlite_master`,
  `== row(`, `dict(row)` in tests/ found only this one).

## Iteration 1: implementation

Files
- `utils/run_store.py` (modified): `ADDED_COLUMNS` (constraints_json TEXT; include_strategy INTEGER NOT
  NULL DEFAULT 0), `COLUMN_DEFAULTS = {"include_strategy": 0}`, `COLUMNS` now 18 (16 old + 2 added),
  `CHAT_SCHEMA` (`chat_messages` exactly as 13.1) and `CHAT_INDEX` (`chat_messages_run_seq` on
  `(run_id, seq)`), module function `ensure_schema(connection)` (CREATE TABLE IF NOT EXISTS runs;
  `PRAGMA table_info` then `ALTER TABLE ADD COLUMN` only for missing columns; CREATE TABLE/INDEX IF NOT
  EXISTS for chat). `RunStore.__init__` calls `ensure_schema` in place of `execute(SCHEMA)`; the
  interrupted-run rule is unchanged. `insert` uses `row.get(column, COLUMN_DEFAULTS.get(column))` so
  existing callers that omit the new columns still insert (old columns behave exactly as before).
  `update` accepts the new columns through `COLUMNS[1:]`. `delete` deletes `chat_messages` rows for the
  run and then the run in one `with connection:` transaction (no foreign keys). `SCHEMA`, `list`,
  `LIST_COLUMNS`, `get`, `_clean` unchanged.
- `utils/chat_store.py` (new, no comments/docstrings): `ChatStore(store)` reusing `RunStore._use`
  (same connection helper, lock and HistoryUnavailableError mapping) and `RunStore._clean` (redaction).
  `append(run_id, *messages) -> bool` (refuses when the run does not exist; several messages in one
  transaction so T11 can store a user+assistant exchange atomically; seq continues from MAX(seq)),
  `list(run_id) -> list[ChatMessage]` ordered by seq, `count(run_id, role=None) -> int`,
  `clear(run_id) -> int`. content_json = `ChatMessage.model_dump_json()` (T1 model reused).
- `tests/test_m3_store_migration.py` (new, 12 tests, all on pytest tmp_path files).
- `tests/test_run_store.py` (existing, one add-only line, approved by the user as option A):
  - before (line 162): `assert columns == set(row()), "the table matches the row shape the manager writes"`
  - after  (line 162): `assert columns == set(row()) | {"constraints_json", "include_strategy"}, "the table matches the row shape the manager writes"`
  - why: 13.1 adds those two columns to `runs`; the assertion stays an exact set comparison.
- No change to `utils/run_manager.py`; `default_manager()` still builds the store on first use.

`_detail_from_row`: real name `RunManager._detail_from_row`, a `@staticmethod` in
`utils/run_manager.py` lines 204-221 (called from `RunManager.get`, line 268). Not edited. It reads
row keys by name, so the two extra keys in a migrated row are ignored; the test
`test_old_rows_are_intact_and_read_through_the_unchanged_detail_path` asserts it returns an equal
`RunDetail` for each pre-migration row dict and its migrated row.

Interpretation of "a strategy job can run on an old row" (13.4): strategy jobs arrive in T4/T8, so at
the store level only. On a migrated old row, `update` accepts `state="running"`, `include_strategy=1`,
`constraints_json`, then `state="done"`, a seven-entry `stages_json` and a `result_json` carrying
`PipelineResult.constraints`; `get` returns them and `_detail_from_row` reads the row into a `RunDetail`
with seven stages and the constraints (`test_a_strategy_job_can_run_on_an_old_row`).

Deferred / not done (out of T2 scope): `has_strategy` on list rows (plan 17.2 mentions it for
run_store, but it is an API row field per 12.1 and changes `GET /api/runs`; left for T8). No chat
wiring into `default_manager()` or routes (T11).

Tests in test_m3_store_migration.py: old file gains columns + chat table + index; old rows intact
(dict equality plus defaults) and `_detail_from_row` equal; second open + direct `ensure_schema` is a
no-op (schema_version, sqlite_master, all runs and chat rows identical); new file schema equals
migrated schema and inserts default include_strategy 0; strategy job on old row; chat append/list/
count/clear on old row with seq 1..3; append to a missing run refused; delete run removes its chat
only; fake key (built from parts) in a question and in constraints not persisted ([redacted]);
chat on unreadable file raises HistoryUnavailableError and leaves the file; importing `app` in a
subprocess with RUNS_DB_PATH at a missing tmp path creates no file and no `_default`; real
data/runs.db mtime_ns and -wal/-shm/-journal existence unchanged.

Verification run (iteration 1)
1. `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_store_migration.py`
   -> 12 passed, 1 warning (the existing Starlette httpx deprecation warning).
2. `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE` -> 1772 passed, 1 warning
   (baseline 1760 + 12 new), 0 failed.
3. Lazy check (script %TEMP%\m3t2_checks.ps1): RUNS_DB_PATH set to a non-existent %TEMP% path,
   `python -B -c "import app; from app import app as a; ..."` -> `default_manager built: False`,
   target file exists: False, parent folder exists: False.
4. Idempotency: covered by `test_a_second_open_is_a_no_op` (passed).
5. data/runs.db after all runs: SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D,
   311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17.0443165Z (identical); read-only URI
   (`?mode=ro`) count = 9 rows, 16 columns (not migrated); data/ holds only runs.db and test_ideas
   (no -wal/-shm), hash identical again after the read-only open.
6. `git status --porcelain`: M .env.example, config.py, models/api.py, models/schemas.py,
   utils/errors.py (T1); M tests/test_run_store.py, utils/run_store.py (T2); ?? .agents/,
   models/chat.py, models/strategy_drafts.py, tests/test_m3_schemas.py (T1);
   ?? tests/test_m3_store_migration.py, utils/chat_store.py (T2). T1 file hashes all identical to the
   baseline above.
7. Secret scan (AIza, gsk_, tvly-, sk-, Bearer, PRIVATE KEY) over utils/run_store.py,
   utils/chat_store.py, tests/test_m3_store_migration.py, tests/test_run_store.py -> 0 hits.

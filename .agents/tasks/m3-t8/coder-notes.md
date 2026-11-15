# M3 T8 coder notes

## Iteration 1

No review.json existed, so this iteration implements the task. The parent answered the T1-test conflict below with option A plus three exact conditions. Those conditions are applied as given.

### Files

| File | Status | Change |
|---|---|---|
| `models/api.py` | modified (already M from T1) | New `NumberLimit`, `ConstraintLimits`, `StrategyInfo`, `ChatLimits`. `MetaResponse.strategy` / `.chat` (`X \| None = None`, always sent). `RunDetail.constraints: StrategyConstraints \| None = None`. `RunSummary.has_strategy: bool \| None = None` (always sent as a bool). The RunRequest comment "accepted, not yet used" is updated. |
| `utils/run_manager.py` | modified (already M from T2/T4) | `start_strategy(run_id, constraints=None, mode="missing")`. `_missing_strategy(result)` lists the stages whose result field is None. `strategy_pipeline(..., rerun=STRATEGY_ONLY_KEYS)` runs that subset of `STRATEGY_ONLY_STAGES` in order. `_with_strategy_stages(stages, keys)` resets or appends only the stages that run. `_Run.rerun`. Detail views carry `constraints` (`_detail_from_row` reads `row.get("constraints_json")`, so old-schema row dicts still work). `_summary` sets `has_strategy` from the stage list. `list()` reads `include_strategy` per row via `_row_has_strategy`. |
| `routes/run_routes.py` | modified | `manager.start(..., include_strategy=body.include_strategy, constraints=body.constraints)`; docstring. +5/-2 |
| `routes/meta_routes.py` | modified | `strategy_info()`, `chat_limits()`; `strategy=`, `chat=` in the reply. +34/-2 |
| `app.py` | modified | Registers `strategy_router`. +2 |
| `routes/strategy_routes.py` | new, 18 lines | `POST /api/runs/{run_id}/strategy`, body `StrategyRequest` (required JSON object; `{}` = missing), 202 `RunStarted`, documented 404/409/503 (+422). |
| `tests/test_m3_runs_api.py` | new, 452 lines | 39 tests |
| `tests/test_m3_strategy_route.py` | new, 601 lines | 38 tests |
| `tests/test_m3_no_search.py` | new, 150 lines | 4 tests |
| `tests/test_m3_schemas.py` | T1 test, 1 test edited | See "Existing-test edit" below. |
| `orchestrator.py` | **not changed** | `_seeded` and `_earlier_stages_finished` already handle a subset of `STRATEGY_ONLY_STAGES`. They keep the strategy fields, errors and timings of stages not run, and drop the warnings, errors and timings of the stages run again. Verified by `test_m3_no_search.py::test_a_subset_of_the_strategy_stages_keeps_the_others_and_makes_no_search` and the `missing` tests in `test_m3_strategy_route.py`. |

### Behaviour (12.1 to 12.4)

- `POST /api/runs`: optional `include_strategy` and `constraints` are passed through. A default request takes the unchanged `self._pipeline(...)` path with the same kwargs (`submission`, `idea`, `time_limit_s`; `FakePipeline` accepts no others). 202 `{run_id, state}`.
- `POST /api/runs/{id}/strategy` (rules from 12.2), checked in this order:
  1. active run → 409 `run_not_finished` (rule 2)
  2. unknown run → 404 `run_not_found` (rule 1)
  3. queued/running row → 409 `run_not_finished` (rule 2)
  4. no result, no idea, or neither market nor competitors → 409 `strategy_not_ready` (rule 3)
  5. `missing` with nothing missing → 409 `strategy_already_complete` (rule 5)
  6. limit full → 409 `run_limit_reached` (rule 4)
  
  Bad body → 422 `invalid_input`. Store unavailable → 503 `history_unavailable`. Success → 202 `{run_id, state: "running"}`, the same model as `POST /api/runs`.
- `mode=missing` (default): runs only the strategy stages whose stored result field (`swot`/`mvp`/`gtm`) is None. That covers stages never run, failed, skipped or cancelled. It runs them in SWOT→MVP→GTM order, and later stages read the kept earlier results. Stage entries of stages not run are left byte-for-byte as they were. New `constraints` replace the stored ones; without them the stored ones are used (T4 behaviour).
- `mode=all`: runs all three in order. The prior result's `swot`/`mvp`/`gtm`/`constraints` are cleared before the job, so the old strategy is not shown while it runs and is not used as input. Only the request's `constraints` are used: `null` clears the stored ones (column and result) and the MVP defaults apply (rule 6, "invalidates previous strategy results and constraints").
- Rule 7: no search and no rerun of stages 1-4 (spy tests below).
- `GET /api/runs/{id}`: gains `constraints` (null when none). `result.swot/mvp/gtm` already come from T1/T4.
- `GET /api/runs`: rows gain `has_strategy`. It is true when the run was created with `include_strategy` or later got a strategy job (`include_strategy` column; for in-memory runs, the presence of strategy stage entries; the two are always set together).
- `GET /api/meta`: gains
  - `strategy`: `{available, time_limit_s, constraints: {team_size{min_value,max_value}, months_to_mvp{...}, launch_region{TextLimit}, budget_levels, technical_skills}}`. `available` = no strategy stage has `PendingStrategyAgent`.
  - `chat`: `{max_message_chars, max_user_turns}` from settings. 12.1 assigns the chat meta block to `/api/meta`; no chat routes were added (T10/T11).
  
  Existing keys and the four `stages` are unchanged.

### Existing-test edit (approved by the parent: option A with exact conditions)

`tests/test_m3_schemas.py::test_every_saved_run_fixture_validates_unchanged` (T1). It is not in 20.4, so the parent was asked by warning notification and approved option A with conditions (1) to (3). The reason: 12.1 adds `RunDetail.constraints` (or null), so the exact dump equality failed with one extra `"constraints": null` key on `liveAgritech.json` and `liveFintech.json`.

Before:
```python
    run = RunDetail.model_validate(original)
    assert run.model_dump(mode="json", exclude={"result"}) == {key: value for key, value in original.items() if key != "result"}
    assert_unchanged(original["result"], run.result)
```
After:
```python
    run = RunDetail.model_validate(original)
    dumped = run.model_dump(mode="json", exclude={"result"})
    assert {key: dumped[key] for key in original if key != "result"} == {key: value for key, value in original.items() if key != "result"}
    assert set(dumped) - set(original) == {"constraints"}
    assert dumped["constraints"] is None
    assert_unchanged(original["result"], run.result)
```
How the after lines meet the conditions:
- (1) Every fixture key is in the dump with an equal value; a missing key raises KeyError.
- (2) The extra keys are exactly `{"constraints"}`.
- (3) `constraints` is None.
- `exclude={"result"}` and `assert_unchanged` are untouched. Nothing else in the file changed.

Hashes:
- Before: `1BAB66868D468410891653819765FF5EB2325F54932B3EA33AEF4AC1A1ED7026` (equals `baseline-hashes.json`; a copy is saved as `test_m3_schemas.before.py.txt` in this folder).
- After: `CC293D27A68FC6B66E3833D9FA50220BE6EBD6C69D3EA7330946C9B713E0027C`.
- Undo proof: `.\.venv\Scripts\python.exe -B .agents\tasks\m3-t8\undo_check.py` reverses the edit in memory and prints `undone 1BAB6686...7026` and `undone == before: True`.

`tests/test_runs_api.py` and `tests/test_meta_route.py` are **not** edited: they pin neither the exact row key set nor the exact meta key set, and `meta["stages"]` stays four. Their hashes equal the baseline.

### Commands and results

1. T8 tests: `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_runs_api.py tests/test_m3_strategy_route.py tests/test_m3_no_search.py` → **81 passed**, 1 warning (Starlette/httpx deprecation).
2. and 3. Full backend suite (covers tests/test_runs_api.py, tests/test_meta_route.py and all tests/test_m3_*.py): `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE` → **2195 passed, 0 failed**, 1 warning. 2195 = 2114 baseline + 81 new. Before the approved test edit, the same command gave 2 failed / 2193 passed (the two fixture cases above).
4. Default-contract comparison: `capture_api.py post`, then `.\.venv\Scripts\python.exe -B .agents\tasks\m3-t8\compare_api.py` (compares `baseline-api.json` / `baseline-openapi.json` with `post-*.json`):
   - `post_runs`: identical (202, `{"run_id": "<RUN_ID>", "state": "queued"}`).
   - `run_detail`: the body is identical apart from added `constraints: null`. Stage keys, labels, statuses, entry keys, state, result status and pipeline call kwargs are identical.
   - `run_list`: identical apart from `has_strategy: false`.
   - `meta`: every baseline key and value is identical. The additions are `strategy` = `{"available": true, "constraints": {"budget_levels": ["bootstrapped","small","funded"], "launch_region": {"max_chars": 60, "min_chars": null, "min_words": null}, "months_to_mvp": {"max_value": 12, "min_value": 1}, "team_size": {"max_value": 10, "min_value": 1}, "technical_skills": ["non_technical","some","strong"]}, "time_limit_s": 150.0}` and `chat` = `{"max_message_chars": 1000, "max_user_turns": 25}`.
   - OpenAPI: the only new path is `/api/runs/{run_id}/strategy`. New schemas: `ChatLimits`, `ConstraintLimits`, `NumberLimit`, `StrategyInfo`, `StrategyRequest`. Nothing was removed. Every existing operation is unchanged, apart from the description text of `POST /api/runs`. Existing schemas changed only by the added optional properties (`MetaResponse.chat/strategy`, `RunDetail.constraints`, `RunSummary.has_strategy`). No existing property or `required` list changed.
   - checks: building the app created no `RUNS_DB_PATH` file, and the real runs.db mtime is unchanged.
5. No-search spy (`test_m3_no_search.py`, real SwotRiskAgent/MvpAgent/GtmAgent with fake model replies):
   - Spies on `agents.web_search_agent.search` (the only caller of the Tavily client) and `utils.search_client.requests.post`, plus the stage-2/3/4 search fakes.
   - `missing` then `all`: 0 search calls, 0 extraction/search/analysis calls, stages[:4] unchanged, one model reply per strategy stage per job.
   - A seven-stage run makes exactly the searches of a four-stage run.
   - A subset run (MVP+GTM) makes no search.
6. Modes and validation: `test_m3_strategy_route.py`.
   - `missing` tests: one parametrized test (each of the three stages failed), plus tests for two missing stages, a four-stage run, a cancel, a time-limit skip, and stored vs new constraints. Each runs only the absent stages.
   - `already_complete` 409 tests: 3 bodies, plus a run completed by a strategy job.
   - `all` tests: replaces all three in order, drops errors, handles `null` constraints, and hides the old strategy while the job runs.
   - Constraints validation (12.3 bounds, enums, 61-char region, unknown field, non-object) gives a 422 `invalid_input` with the existing `{"error": {...}}` shape, on both `POST /api/runs` and the strategy route. Control characters are stripped (`"Pune,\x00 India\x1b[31m\x7f"` → `"Pune, India [31m"`; control-only → null).
7. Frontend:
   - OpenAPI was dumped to `%TEMP%\m3t8-openapi.json` with `RUNS_DB_PATH` pointing at a non-existent temp file (not created).
   - `npx openapi-typescript <temp> -o src/api/types.gen.ts` in web/; the temp file was deleted.
   - `npm run typecheck` → clean (exit 0).
   - `npm test` → **295 passed, 20 files**.
   - No web/ source edited; the Playwright screenshots spec was not run.
   - The new response fields are optional in the schema (`X | None = None`). A field with a non-null default would become required in the generated TS, and typed fixtures (`web/src/test/fixtures.ts` META, `HistoryPage.test.tsx` ROWS) would then fail the typecheck.
8. Lazy check: in a fresh interpreter with `RUNS_DB_PATH=%TEMP%\m3t8-lazy-<guid>\runs.db`, `from app import app` imported (9 routes). Neither the file nor its folder was created.
9. Fingerprints:
   - `hashes.ps1 post` → 41 files, none missing. The files differing from baseline are exactly `app.py`, `models/api.py`, `routes/meta_routes.py`, `routes/run_routes.py`, `utils/run_manager.py`, `tests/test_m3_schemas.py` and the 4 new files. Every other T1-T7 file, `orchestrator.py`, `tests/test_runs_api.py` and `tests/test_meta_route.py` are byte-identical.
   - data/runs.db: SHA-256 `00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D`, size 311296, LastWriteTimeUtc 2026-11-08T15:31:17Z: matches. HEAD a098aef, branch main.
   - `git status --porcelain` vs baseline adds only ` M app.py`, ` M routes/meta_routes.py`, ` M routes/run_routes.py`, `?? routes/strategy_routes.py`, `?? tests/test_m3_no_search.py`, `?? tests/test_m3_runs_api.py`, `?? tests/test_m3_strategy_route.py`. `tests/test_m3_schemas.py` and `models/api.py`/`utils/run_manager.py` were already listed.
   - Secret scan (AIza, gsk_, tvly-, sk-, Bearer token, PRIVATE KEY) over the 10 changed/new project files and this folder's scripts and notes: 0 hits.

Post-T8 SHA-256:
- app.py `3CA9A5B3B31874256CF9846B2845B7CA0D743A33327196B2D039728BAE03ED31`
- models/api.py `8898994873F04348018127A2517387057930865735C8541EC5B98BFD5D23620C`
- routes/meta_routes.py `D81AED9C8BE1AA27D8D89AB45EE2D49738F2351511B28925BE5BF6906D1F8AE9`
- routes/run_routes.py `09B8882524528FFA6C26DE8DEC1FBB0F05D2E3CB1357C5D3A75217F9D69E4DDC`
- routes/strategy_routes.py `A60BE0CA5B8144451F367327FC371EC2DA98C4D45286747D0D0ED9EBBD1F78DC`
- utils/run_manager.py `5D14643E0139D8B7E32B9AF3BA85BD7BE6CA9BD2E5C056625EF10A70E6D18990`
- tests/test_m3_runs_api.py `A2841062AC1F9B194047B48C69DDCC9212283D8E335FECE92BCAF6E2C6CF0B5D`
- tests/test_m3_strategy_route.py `B79E163F3F2D5E68C23186FA3C576F42F510D7A483669526E291AFBD94A9DD77`
- tests/test_m3_no_search.py `110160C91D4BE52608B3DCDC87AE66E8D2543D6952323D6E0778103ED56120CB`
- tests/test_m3_schemas.py `CC293D27A68FC6B66E3833D9FA50220BE6EBD6C69D3EA7330946C9B713E0027C`

### Plan-vs-code conflicts and decisions

- **Plan 17.2 puts `has_strategy` in `run_store.py`, which T8 may not change.** `RunStore.list()` returns `LIST_COLUMNS` without `include_strategy`, so `RunManager.list()` reads each saved row with `store.get` (one extra query per row). A later one-line change (`include_strategy` in `LIST_COLUMNS`) would remove the extra reads.
- **New response fields are typed `X | None = None` (always filled by the server)** so the generated TS keeps them optional (frontend typecheck, see 7).
- **Check order.** `strategy_already_complete` is checked before `run_limit_reached`. The plan numbers them 5 and 4 without stating precedence; a complete strategy cannot be helped by retrying later.
- **`RunManager.start_strategy` defaults to `mode="missing"`, like the API.** All T4 manager tests still pass unchanged. The T4 report's conflict C-9 (no `mode`, no StrategyAlreadyCompleteError) is resolved here.
- **The strategy route body is required** (`{}` means missing), like `POST /api/runs`. A request with no body gets 422.
- **No `stages` list in `meta.strategy`.** Run detail entries carry the strategy labels, and 12.1 lists no such field.
- **Chat:** only the 12.1 meta `chat` block was added. No chat routes (T10/T11).
- **`test_m3_no_search.py` covers strategy jobs only.** The Advisor part of 17.3 is left for T10/T11.
- **`_detail_from_row` can now refuse a row with an unreadable `constraints_json`** (HistoryUnavailableError, same as `_stored_constraints`). Existing fields are read exactly as before.

### Helper files in this folder (not in the project tree)

- `compare_api.py`: baseline-vs-post comparison.
- `undo_check.py`: undo-hash proof.
- `test_m3_schemas.before.py.txt`: pre-edit copy.
- `post-api.json`, `post-openapi.json`, `post-hashes.json`: post-T8 capture.

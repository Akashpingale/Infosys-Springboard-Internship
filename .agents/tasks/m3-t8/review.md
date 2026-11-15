# M3 T8 review (iteration 1)

Verdict: APPROVED. No blockers.

## Scope and fingerprints
- Current SHA-256 vs `baseline-hashes.json` (37 files): changed only `app.py`, `models/api.py`, `routes/meta_routes.py`, `routes/run_routes.py`, `utils/run_manager.py`, `tests/test_m3_schemas.py`. `orchestrator.py`, `tests/test_runs_api.py`, `tests/test_meta_route.py` and every other T1-T7 file are byte-identical.
- New files hash to the values in coder-notes: `routes/strategy_routes.py` A60BE0CA…78DC, `tests/test_m3_runs_api.py` A2841062…0B5D, `tests/test_m3_strategy_route.py` B79E163F…DD77, `tests/test_m3_no_search.py` 110160C9…20CB.
- `git status --porcelain` vs `baseline-git-status.txt`: the only additions are ` M app.py`, ` M routes/meta_routes.py`, ` M routes/run_routes.py` and the four new files. Nothing under web/, frontend/, docs/, the plan or KIRO_*.md.
- data/runs.db (Get-FileHash/Get-Item only): 00A4F859…337D, 311296 bytes, 2026-11-08T15:31:17Z, unchanged.
- Secret-pattern scan of the 10 changed/new files: 0 hits.

## Existing-test edit
`tests/test_m3_schemas.py::test_every_saved_run_fixture_validates_unchanged` is not listed in 20.4. The coder records that the parent was asked and approved option A with three conditions. I relied on that record for the approval itself. The diff against the saved pre-edit copy (hash 1BAB6686…7026, equal to the baseline) changes only that assertion. It still requires every fixture key to be present with an equal value, pins the extra keys to exactly `{"constraints"}`, and requires that value to be None. The test is not weakened, and 12.1 makes the extra key unavoidable. `undo_check.py` reverses the edit in memory, and the result matches the before copy.

## Requirements check
- **12.1:** `POST /api/runs` passes `include_strategy`/`constraints` through. The default path still calls `self._pipeline` with the same kwargs (`run_manager.py` `_call_pipeline`). `RunDetail.constraints`, `RunSummary.has_strategy` and `MetaResponse.strategy`/`chat` are additive and optional in the schema. They are always filled. `meta.stages` stays at four entries.
- **12.2 rules 1-7:** `start_strategy` checks the active run (409), then the unknown run (404), then a queued/running row (409), then not ready (409), then already complete (409), then the run limit (409). `mode=missing` uses `_missing_strategy`, which treats any result field that is None as absent. `_with_strategy_stages` resets or appends only the stages being run. `mode=all` clears swot/mvp/gtm/constraints before the job and uses only the request's constraints. The orchestrator's `_seeded` and `_earlier_stages_finished` already handle a subset of `STRATEGY_ONLY_STAGES`, so `orchestrator.py` is unchanged.
- **Rule order:** `strategy_already_complete` comes before `run_limit_reached`. The plan states no precedence, and the coder documented the choice.
- **12.4:** The codes and messages are asserted literally in the tests.
- **Strategy route:** reuses `RunStarted` with 202, the same reply as `POST /api/runs`, and is registered in `app.py`.
- **Tests:** they cover every 12.2 rule, unchanged defaults, constraints bounds/enums/unknown field/control characters, `has_strategy` (including after a restart and on rename), the meta additions, a no-search spy using the real agents with fake replies in both modes, `missing` subsets (failed, cancelled, time-skipped), and `all` replacement in order.

## Verification evidence (coder-notes; suites not re-run)
- T8 tests: 81 passed.
- Full suite: 2195 passed, 0 failed (2114 + 81).
- Frontend: types regenerated, typecheck clean, `npm test` 295 passed in 20 files.
- Lazy import created no file.
- Spot-check: I re-ran `compare_api.py`, which only reads the recorded JSON. `post_runs` is identical. `run_detail` differs only by `constraints: null`, `run_list` only by `has_strategy: false`, and `meta` only by `strategy`/`chat`. The only new OpenAPI path is the strategy route, and no existing property or `required` list changed.

## Non-blocking notes (no action required for T8)
- `RunManager.list()` reads each saved row with `store.get` to get `has_strategy`, because `run_store.py` is outside T8's file list (recorded conflict with plan 17.2). This costs one extra query per row and is correct.
- In `mode=missing`, new constraints replace the stored ones even though kept stages were built with the old ones. The plan leaves this open, and each MVP result keeps its own `constraints_used`.

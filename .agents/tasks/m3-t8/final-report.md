# M3 T8 final report: Strategy API and meta

Branch `main`, HEAD `a098aef` (unchanged). Nothing was committed, pushed, reset, reverted or stashed. No branch was created. The review (`review.json`) verdict is APPROVED with no findings, after 1 iteration. Every check below was re-run in this final step, on the current working tree.

## 1. Files changed and created

Diff sizes for `app.py` and the two route files are T8 only: they were clean at baseline. For `models/api.py` and `utils/run_manager.py`, `git diff --numstat` against HEAD also counts the earlier T1-T4 work, so the T8-only part is smaller. No pre-T8 copy of those two files exists, only their hashes.

| File | Status | Diff | Purpose |
|---|---|---|---|
| `routes/strategy_routes.py` | new | 18 lines | `POST /api/runs/{run_id}/strategy`: body `StrategyRequest`, 202 `RunStarted`, documents 404/409/503. |
| `routes/run_routes.py` | modified | +5 / -2 | Passes `include_strategy` and `constraints` to `manager.start`; docstring. |
| `routes/meta_routes.py` | modified | +34 / -2 | `strategy_info()` and `chat_limits()`; adds `strategy` and `chat` to the meta reply. |
| `app.py` | modified | +2 / -0 | Registers `strategy_router`. |
| `models/api.py` | modified (already M from T1) | +55 / -2 vs HEAD | New `NumberLimit`, `ConstraintLimits`, `StrategyInfo`, `ChatLimits`. Adds `MetaResponse.strategy` / `.chat`, `RunDetail.constraints` and `RunSummary.has_strategy`, all `X \| None = None` and always filled by the server. `StrategyRequest` and `RunRequest.include_strategy` / `.constraints` came from T1 (OpenAPI lists `StrategyRequest` now that a route uses it). |
| `utils/run_manager.py` | modified (already M from T2/T4) | +232 / -25 vs HEAD | `start_strategy(run_id, constraints=None, mode="missing")`, `_missing_strategy`, `strategy_pipeline(..., rerun=...)`, `_with_strategy_stages`, `constraints` on detail views, `has_strategy` on summaries and list rows. |
| `tests/test_m3_runs_api.py` | new | 452 lines, 39 tests | `POST /api/runs` defaults and strategy, detail/list fields, constraints validation, meta. |
| `tests/test_m3_strategy_route.py` | new | 601 lines, 38 tests | Strategy route rules 1-7 and the `missing` / `all` modes. |
| `tests/test_m3_no_search.py` | new | 150 lines, 4 tests | No-search spy with the real SWOT, MVP and GTM agents and fake replies. |
| `tests/test_m3_schemas.py` | T1 test, 1 assertion edited | see section 5 | Approved deviation (not in 20.4). |
| `orchestrator.py` | **not changed** | 0 | `_seeded` and `_earlier_stages_finished` already handle a subset of `STRATEGY_ONLY_STAGES`. |

`web/src/api/types.gen.ts` was regenerated. It is git-ignored, and its SHA-256 `CA3902DF…04F6` is the same before and after this step's regeneration. No web/ source, frontend/, docs/, plan or KIRO_*.md file changed.

## 2. Endpoints and fields added (mapped to 12.1-12.4)

| Plan item | Method and path | Body | Success | Errors |
|---|---|---|---|---|
| 12.1 | `POST /api/runs` | Adds optional `include_strategy` (bool, default false) and `constraints` (`StrategyConstraints` or null). | 202 `{run_id, state}`, unchanged. | Existing errors. Bad constraints or a bad `include_strategy` give 422 `invalid_input` in the existing `{"error": {code, message}}` shape. |
| 12.1 | `GET /api/runs/{id}` | none | Adds `constraints` (object or null). `result.swot/mvp/gtm` come from T1/T4. `stages` has 7 entries when strategy was requested, 4 otherwise. | unchanged |
| 12.1 | `GET /api/runs` | none | Each row adds `has_strategy` (bool, always sent). | unchanged |
| 12.1 | `GET /api/meta` | none | Adds `strategy` and `chat` (section 4). | unchanged |
| 12.2 | `POST /api/runs/{id}/strategy` (new) | `{"mode": "missing" \| "all" (default "missing"), "constraints": StrategyConstraints \| null}`. Extra fields are forbidden; `{}` means missing; a JSON body is required. | 202 `{run_id, state: "running"}` (`RunStarted`, the same model and status as `POST /api/runs`). | 404 `run_not_found` (rule 1); 409 `run_not_finished` (rule 2); 409 `strategy_not_ready` (rule 3); 409 `run_limit_reached` (rule 4); 409 `strategy_already_complete` (rule 5); 422 `invalid_input`; 503 `history_unavailable`. |
| 12.3 | StrategyConstraints validation (T1 model, now exposed) | `team_size` 1-10, `months_to_mvp` 1-12, `budget_level` and `technical_skill` from 3 values each, `launch_region` up to 60 chars. Control characters are stripped (control-only becomes null). Unknown fields are rejected. | | 422 `invalid_input` |
| 12.4 | Error codes | `run_not_finished` "This validation is still running."; `strategy_not_ready` "There is no market or competitor analysis to build a strategy on."; `strategy_already_complete` "This validation already has a strategy." The tests assert these literally. | | |

The strategy route checks in this order: active run (409 `run_not_finished`), unknown run (404), queued or running saved row (409), not ready (409), `missing` with nothing missing (409 `strategy_already_complete`), then the run limit (409 `run_limit_reached`).

These items were not added because they belong to later tasks: chat routes (12.2 `GET/POST/DELETE /api/runs/{id}/chat`, T10/T11), chat error codes (T10/T11), `report.md` strategy sections (T9), and derived fields (12.5, T9). `DELETE /api/runs/{id}` chat cascade is store-level work done in T2 and was not changed. T8 adds only the 12.1 meta `chat` block for chat.

## 3. How `mode=missing` and `mode=all` work

- **`missing`** (default): `_missing_strategy(result)` lists the strategy stages whose stored result field (`swot` / `mvp` / `gtm`) is None. That covers stages that never ran, failed, were cancelled or were skipped by the time limit. Only those stages run, in SWOT→MVP→GTM order, and later stages read the kept earlier results. `_with_strategy_stages` resets or appends only the stage entries being run, and leaves the other entries byte-for-byte as they were. New `constraints` replace the stored ones; without them the stored constraints are used. When nothing is missing, the route answers 409 `strategy_already_complete` and runs nothing.
- **`all`**: all three stages run in order. Before the job, the stored `swot` / `mvp` / `gtm` / `constraints` are cleared, so the old strategy is neither shown nor used as input (rule 6). Only the request's `constraints` are used: `null` clears the stored ones, and the MVP defaults apply.
- **Both modes** reuse the stored idea and stage 1-4 results. The job uses the strategy-only stage set from T4. It makes no search call and does not re-run stages 1-4 (rule 7).

## 4. `/api/meta` before and after

- Before: `app_name, examples, industries, limits, providers, run_limits, stages, version`.
- After: the same keys plus `chat` and `strategy`. Every existing key and value is identical, and `stages` is still the 4 entries.
- `strategy` = `{"available": true, "time_limit_s": 150.0, "constraints": {"team_size": {"min_value": 1, "max_value": 10}, "months_to_mvp": {"min_value": 1, "max_value": 12}, "launch_region": {"max_chars": 60, "min_chars": null, "min_words": null}, "budget_levels": ["bootstrapped", "small", "funded"], "technical_skills": ["non_technical", "some", "strong"]}}`. `available` is false if any strategy stage still has `PendingStrategyAgent`.
- `chat` = `{"max_message_chars": 1000, "max_user_turns": 25}` (from settings).

## 5. Existing-test edits

- `tests/test_runs_api.py` and `tests/test_meta_route.py` are **not** edited (hashes equal baseline). They do not pin the exact row or meta key set, and `meta["stages"]` stays at 4, so the 20.4 entries for them were not needed.
- `tests/test_m3_schemas.py::test_every_saved_run_fixture_validates_unchanged` (a T1 test) **was edited**. This test is **not listed in 20.4**. The coder stopped and asked the parent by warning notification, and the parent approved "option A" with three conditions. The reason for the edit: 12.1 adds `RunDetail.constraints`, so the exact dump equality on `liveAgritech.json` and `liveFintech.json` gained one `"constraints": null` key (2 failures before the edit).
  - Before: `assert run.model_dump(mode="json", exclude={"result"}) == {key: value for key, value in original.items() if key != "result"}`
  - After: every fixture key must be present with an equal value, `set(dumped) - set(original) == {"constraints"}`, and `dumped["constraints"] is None`. `assert_unchanged(original["result"], run.result)` is untouched.
  - Hashes: before `1BAB66868D468410891653819765FF5EB2325F54932B3EA33AEF4AC1A1ED7026` (equals baseline), after `CC293D27A68FC6B66E3833D9FA50220BE6EBD6C69D3EA7330946C9B713E0027C`. Re-run in this step, `undo_check.py` printed `undone == before: True`.
  - **For the user's review:** the original rule says only 20.4 tests may change. This edit was approved inside the workflow, not by the user directly.

## 6. T8 tests, grouped by the T8 entry's test bullets

- **Every rule in 12.2:**
  - `test_strategy_on_a_saved_run_answers_like_starting_a_run`, `test_an_empty_body_means_missing`
  - `test_rule_1_an_unknown_run_is_a_404`
  - `test_rule_2_a_running_run_is_refused`
  - `test_rule_3_a_run_without_an_idea_or_an_analysis_is_refused[no-market-and-no-competitors|no-idea]`, `test_rule_3_one_finished_analysis_is_enough`
  - `test_rule_4_the_run_limit_is_shared_with_normal_runs`
  - `test_rule_5_missing_with_nothing_missing_is_refused[None|body1|body2]`, `test_rule_5_a_strategy_job_that_completed_the_run_also_counts`
  - `test_rule_6_all_replaces_the_three_results_and_the_constraints_in_order`, `test_rule_6_all_without_constraints_drops_the_stored_ones`, `test_rule_6_all_drops_the_old_errors_and_warnings_of_the_strategy_stages`, `test_rule_6_the_old_strategy_is_not_shown_while_all_runs`
  - `test_without_history_the_route_answers_503`, `test_the_result_still_validates_after_each_mode`
  - Rule 7 is covered by the spy group below.
- **Defaults leave `POST /api/runs` identical:** `test_a_default_run_answers_exactly_as_before`, `test_the_explicit_defaults_are_the_same_as_leaving_them_out`, `test_a_default_run_row_only_gains_has_strategy`, `test_constraints_without_strategy_are_kept_and_the_run_has_four_stages`, `test_a_run_with_strategy_has_seven_stages_and_the_same_start_reply`, `test_a_run_with_strategy_without_constraints_reports_none`, `test_a_failed_strategy_stage_makes_the_run_partial_with_seven_entries`, `test_the_saved_detail_carries_the_constraints_after_a_restart`, `test_the_detail_still_matches_its_model`, `test_the_schema_keeps_the_start_reply_and_adds_the_strategy_route`.
- **Constraints validation:** `test_bad_constraints_are_refused_with_the_error_shape[11 cases]`, `test_a_bad_include_strategy_is_refused[4 cases]`, `test_constraints_at_their_limits_are_accepted`, `test_control_characters_are_stripped_from_the_region`, `test_a_region_of_control_characters_only_becomes_none`, `test_a_bad_body_is_refused_with_the_error_shape_and_starts_nothing[10 cases, incl. unknown field and 61-char region]`, `test_a_request_without_a_body_is_refused`, `test_control_characters_are_stripped_from_the_region_of_a_strategy_job`.
- **`has_strategy`:** `test_has_strategy_follows_the_run`, `test_has_strategy_is_in_the_reply_of_a_rename`, `test_an_old_row_without_the_new_columns_reads_as_without_strategy`.
- **`/api/meta` additions:** `test_meta_keeps_its_keys_and_gains_strategy_and_chat`, `test_meta_publishes_the_constraint_limits_and_choices_the_backend_enforces`, `test_the_published_constraint_limits_are_usable`, `test_meta_publishes_the_chat_limits`, `test_meta_follows_the_configured_strategy_and_chat_settings`, `test_meta_says_strategy_is_unavailable_without_a_registered_agent`, `test_meta_still_names_no_key`.
- **Spy proves no search in strategy jobs:**
  - `test_m3_no_search.py`: `test_the_real_agents_are_the_ones_under_test`, `test_a_strategy_job_in_either_mode_makes_no_search_and_does_not_rerun_stages_1_to_4`, `test_a_run_with_strategy_searches_only_in_the_first_four_stages`, `test_a_subset_of_the_strategy_stages_keeps_the_others_and_makes_no_search`
  - `test_m3_runs_api.py::test_a_run_with_strategy_searches_only_in_the_search_stages`
- **`mode=missing` runs only absent stages:** `test_missing_runs_only_the_failed_stage[swot_risk|mvp_recommendation|go_to_market]`, `test_missing_runs_the_absent_stages_in_order_and_the_later_ones_see_the_kept_results`, `test_missing_on_a_run_without_strategy_runs_all_three`, `test_missing_runs_the_stages_a_cancel_stopped`, `test_missing_runs_the_stages_the_time_limit_skipped`, `test_missing_keeps_the_stored_constraints_unless_new_ones_are_given`.
- **`all` replaces:** the four `test_rule_6_*` tests above.

## 7. Verification results (this step)

| # | Check | Result |
|---|---|---|
| 1 | `pytest -q -p no:cacheprovider -rfE tests/test_m3_runs_api.py tests/test_m3_strategy_route.py tests/test_m3_no_search.py` | **81 passed**, 1 warning (Starlette/httpx deprecation) |
| 2 | `tests/test_runs_api.py` (32), `tests/test_meta_route.py` (15), all 12 `tests/test_m3_*.py` | **606 passed**, 0 failed, 1 warning. The two existing API test files are byte-identical to baseline. |
| 3 | Full backend suite | **2195 passed**, 0 failed, 1 warning (2114 baseline + 81 new) |
| 4 | Default-contract equivalence (`capture_api.py final` + `final_compare.py`, against the pre-T8 `baseline-api.json`) | See below. |
| 5 | No-search spy (`tests/test_m3_no_search.py`) | **4 passed**. In both modes: 0 calls to `agents.web_search_agent.search` and to `utils.search_client.requests.post`, 0 extraction/search/analysis calls, `stages[:4]` unchanged. |
| 6 | Modes and validation (`-k "missing or rule_5 or rule_6 or bad_constraints or bad_body or control_characters or limits_are_accepted or without_a_body"`) | **43 passed** (34 deselected). `missing` runs only absent stages. Nothing missing gives 409 `strategy_already_complete`. `all` replaces all three. Bounds, enums, the 61-char region and unknown fields give 422 `invalid_input` in the existing error shape. Control characters are stripped. |
| 7 | Frontend | See below. |
| 8 | Lazy import (`lazy_check.py`, fresh interpreter, `RUNS_DB_PATH=%TEMP%\m3t8-final-lazy-<uuid>\runs.db`) | `from app import app` succeeded. The file was not created and its folder was not created. |
| 9 | Fingerprints, git status, secret scan | See section 8. |

Check 4 details:
- `post_runs`: identical (202, `{"run_id": "<RUN_ID>", "state": "queued"}`).
- `run_detail`: identical apart from the added `constraints: null`. Stage keys, labels and statuses are identical, as are entry keys, state, `result.status`, the full `result` body and the pipeline call kwargs.
- `run_list`: identical apart from `has_strategy: false`.
- `meta`: identical apart from the added `chat` and `strategy`.
- OpenAPI:
  - The only new path is `/api/runs/{run_id}/strategy`.
  - New schemas: `ChatLimits`, `ConstraintLimits`, `NumberLimit`, `StrategyInfo`, `StrategyRequest`. Nothing was removed.
  - Existing operations are unchanged, apart from the description text of `POST /api/runs`.
  - Changed schemas only add optional properties: `MetaResponse` (`chat`, `strategy`), `RunDetail` (`constraints`), `RunSummary` (`has_strategy`). No `required` list changed.
- The fresh capture equals the coder's `post-api.json`.

Check 7 details:
- OpenAPI was dumped to `.agents\tasks\m3-t8\openapi-temp.json`. `RUNS_DB_PATH` pointed at a non-existent folder, and no file was created.
- `npx openapi-typescript ..\.agents\tasks\m3-t8\openapi-temp.json -o src/api/types.gen.ts` (openapi-typescript 7.13.0) ran in web/. The temp file was deleted afterwards (confirmed `False`).
- `npm run typecheck`: **clean**, exit 0.
- `npm test`: **295 passed in 20 files**, exit 0.
- The Playwright screenshots spec was not run.

## 8. Fingerprint evidence

- `data/runs.db` (Get-FileHash / Get-Item only): SHA-256 `00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D`, size 311296, LastWriteTimeUtc 2026-11-08T15:31:17Z. **Matches expected**, same as baseline.
- `hashes.ps1 final` hashed 41 files, none missing.
  - 31 of the 37 baseline files are byte-identical. These include every T1-T7 file, `orchestrator.py`, `tests/test_runs_api.py` and `tests/test_meta_route.py`.
  - Changed vs baseline: `app.py`, `models/api.py`, `routes/meta_routes.py`, `routes/run_routes.py`, `utils/run_manager.py`, `tests/test_m3_schemas.py`.
  - New: `routes/strategy_routes.py`, `tests/test_m3_runs_api.py`, `tests/test_m3_strategy_route.py`, `tests/test_m3_no_search.py`.
  - The final hashes equal the coder's `post-hashes.json` and the values the reviewer checked:
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
- `git status --porcelain` vs `baseline-git-status.txt`: added only ` M app.py`, ` M routes/meta_routes.py`, ` M routes/run_routes.py`, `?? routes/strategy_routes.py`, `?? tests/test_m3_no_search.py`, `?? tests/test_m3_runs_api.py`, `?? tests/test_m3_strategy_route.py`. Nothing was removed. HEAD `a098aef`, branch `main`.
- Secret scan (patterns: AIza…, gsk_…, tvly-…, sk-…, Bearer tokens, PRIVATE KEY):
  - The 10 changed/new project files: **0 hits**.
  - This folder's files: 1 false positive. `coder-notes.md` contains the words "PRIVATE KEY" in the list of patterns scanned; it is not a key.

## 9. Plan-vs-code conflicts (recorded, not blocking)

1. Plan 17.2 puts `has_strategy` in `run_store.py`, which is outside T8's file list. `RunStore.list()` does not return `include_strategy`, so `RunManager.list()` reads each saved row with `store.get`: one extra query per row. This is correct, and a later one-line `LIST_COLUMNS` change would remove the extra reads.
2. New response fields are typed `X | None = None` (always filled) so the generated TypeScript keeps them optional and the existing typed web fixtures still typecheck.
3. The plan numbers `run_limit_reached` (rule 4) before `strategy_already_complete` (rule 5) but states no precedence. The code checks `already_complete` first, because retrying later cannot help a complete strategy.
4. The strategy route requires a JSON body, like `POST /api/runs` (`{}` means `missing`). A request with no body gets 422.
5. `meta.strategy` has no `stages` list, because 12.1 lists none. Run detail entries carry the strategy labels.
6. `_detail_from_row` now reads `constraints_json`. An unreadable value raises `HistoryUnavailableError`, the same as `_stored_constraints`. Existing fields are read as before. Plan 13.1 says the `_detail_from_row` fragility is not changed, and it is not.
7. In `mode=missing`, new constraints replace the stored ones even though the kept stages were built with the old ones. The plan leaves this open, and each MVP result keeps its own `constraints_used`.

## 10. Unresolved issues and what remains

- No verification failed.
- One item needs the user's review: the `tests/test_m3_schemas.py` assertion edit (section 5). It is outside the 20.4 list and was approved inside the workflow.
- Remaining for T9+:
  - T9: derived fields (12.5), notice templates, Markdown export / `report.md` strategy sections.
  - T10/T11: chat routes and their error codes (`chat_unavailable`, `chat_limit_reached`, `chat_busy`, `chat_cooldown`, `chat_message_invalid`), and the Advisor part of the 17.3 no-search spy.
  - Later React tasks: every web/ change (constraints panel, Strategy tabs, History `has_strategy` use), including the 20.4 frontend test edits.
  - Optional: add `include_strategy` to `RunStore.LIST_COLUMNS`.
- Helper scripts added in this step, all under `.agents\tasks\m3-t8\`: `final_compare.py`, `dump_openapi.py`, `lazy_check.py`, `final_checks.py`, plus the outputs `final-api.json`, `final-openapi.json`, `final-hashes.json`. The temp OpenAPI file was deleted.

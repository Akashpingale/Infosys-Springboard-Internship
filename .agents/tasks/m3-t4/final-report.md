# Milestone 3 Task T4 (Strategy stage plumbing): final report

The review loop ended APPROVED after 2 iterations. Iteration 1 drew finding B-1: a strategy-only job kept stale strategy warnings from the saved result. Iteration 2 fixed it, and the review then raised no findings. All nine verification items pass on the current working tree. Branch is `main`, HEAD is `a098aef0408fcef8ec8bd497ee42dbedebc334f7`, and nothing was committed, pushed, reset or stashed.

## Files changed or created

Line counts come from `git diff --no-index --numstat --ignore-cr-at-eol` against the pre-T4 copies in `.agents/tasks/m3-t4/baseline/`. Each file kept its original line endings.

| File | Change | +/- | Purpose |
|---|---|---|---|
| `agents/base.py` | modified | +11 / -0 | `AgentContext` gains `constraints`, `swot`, `mvp`, `gtm` (all default `None`). |
| `orchestrator.py` | modified | +144 / -6 | New pieces: `StrategyStage`, `PendingStrategyAgent`, `STRATEGY_ONLY_STAGES`, `STRATEGY_STAGES`, `SKIP_NO_ANALYSIS`, `STRATEGY_MAX_OUTPUT_TOKENS = 6144`, `STRATEGY_FIELDS`, `_seeded`, `_earlier_stages_finished`. `run_pipeline` gains three keyword-only arguments, `constraints`, `prior` and `strategy_time_limit_s`, all defaulting to `None`. `_result` now carries swot, mvp, gtm and constraints. |
| `utils/deadline.py` | modified | +13 / -0 | `extra_time(seconds)` context manager. It moves the current deadline later inside the block (D-11) and does nothing when there is no limit or `seconds` is `None`. |
| `utils/run_manager.py` | modified | +195 / -22 | New constants `STRATEGY_STAGE_KEYS`, `STRATEGY_ONLY_KEYS`, `TITLES`. New functions `strategy_pipeline`, `strategy_time_limit_s`, `_stage_entry`, `_new_stages(keys)`, `_with_strategy_stages`, `_stored_constraints`. `start(..., *, include_strategy=False, constraints=None)` gains two arguments and there is a new `start_strategy(run_id, constraints=None)`. `_call_pipeline` routes each run to the right pipeline. `_finish` has a strategy-job branch. `_Run` gains `include_strategy`, `constraints`, `prior`. |
| `agents/notices.py` | modified (add-only) | +12 / -0 | `STAGE_SWOT`, `STAGE_MVP`, `STAGE_GTM` and `STRATEGY_TITLES` (the 5.1 labels), plus three `WARNING_LABELS` entries generated from them. `STAGE_TITLES` is unchanged. |
| `utils/llm_client.py` | modified (add-only) | +18 / -0 | ContextVar `_output_tokens` and the `output_token_limit(tokens)` context manager. `_call_groq` now passes `max_completion_tokens=_output_tokens.get()`, which is `None` outside a strategy stage. |
| `utils/groq_client.py` | modified | +11 / -4 | `request_body` and `generate_json` take an optional `max_completion_tokens=None`. With `None` the request carries `MAX_COMPLETION_TOKENS` (4096), as before. |
| `tests/m3_fakes.py` | new | 189 lines | Fake strategy agents and synthetic SWOT/MVP/GTM results. `use_fake_strategy` swaps the agents on the real `STRATEGY_ONLY_STAGES`. Also a gate agent, a fake clock, capturing Gemini/Groq providers (the fake key is built from string parts) and `full_result`. |
| `tests/test_m3_orchestrator.py` | new | 692 lines | 40 tests. |

The modified files total +404 / -32. These files are unchanged: `utils/structured.py`, `config.py`, `.env.example`, everything under `routes/`, `frontend/`, `web/` and `docs/`, the plan, and the `KIRO_*.md` files. `git status --porcelain` on those paths shows 0 entries.

## How each T4 requirement was met

- **New stage objects with `stop_on_failure = False`.** `orchestrator.StrategyStage` sets `stop_on_failure = False`, `uses_strategy_time = True` and its own `label`. In `run()`, an `AppError` propagates and becomes a stage error. Any other exception is logged and becomes the generic `AppError()`, as the existing analysis stages do.
- **`STRATEGY_STAGES` and `STRATEGY_ONLY_STAGES`.** `STRATEGY_ONLY_STAGES` holds swot_risk, mvp_recommendation and go_to_market in that order. `STRATEGY_STAGES` is `[*FULL_STAGES, *STRATEGY_ONLY_STAGES]`. The production entries hold `PendingStrategyAgent` placeholders, which fail with "This part of the strategy is not available yet." until T5-T7 supply the real agents. The tests use fake agents from `tests/m3_fakes.py`.
- **Prior-result seeding.** When `run_pipeline(..., prior=...)` is called, `_seeded` builds the context from the saved result:
  - It copies idea, search, market, competitors, candidates and search bundles.
  - It keeps the strategy fields of stages the job does not re-run.
  - It drops the saved warnings that start with the label of a re-run stage (the B-1 fix).
  - It uses the given constraints, or else the saved result's constraints.
  - It drops errors and timings of re-run stages. The job's own time is added to the saved `total`.
  - The result is downgraded to `partial` unless every earlier stage had produced its result.
- **Deadline extension (D-11).** `run_pipeline` enters `extra_time(strategy_time_limit_s)` at the first stage with `uses_strategy_time`. Stages 1-4 therefore run inside `PIPELINE_TIME_LIMIT_S` as before, and stages 5-7 see the total `PIPELINE_TIME_LIMIT_S + STRATEGY_TIME_LIMIT_S`.
  - The run manager passes `time_limit_s=run_time_limit_s()` and `strategy_time_limit_s=settings.strategy_time_limit_s` (default 150 from T1's `config.py`).
  - A strategy-only job runs within `STRATEGY_TIME_LIMIT_S` alone (see conflict C-6).
- **`include_strategy` and `constraints` through the run manager and store.** `RunManager.start(..., include_strategy=..., constraints=...)` writes the `include_strategy` (0/1) and `constraints_json` columns that T2 added. A run with `include_strategy` goes to `strategy_pipeline`. The default call takes the same `self._pipeline(...)` path with the same arguments as before.
- **Seven stage entries.** A run with `include_strategy` starts with seven `waiting` entries. They are labelled from `TITLES = {**STAGE_TITLES, **STRATEGY_TITLES}`.
- **Strategy-only job.** `start_strategy(run_id, constraints=None)` works as follows:
  - It returns 404 (`RunNotFoundError`) for an unknown run and 409 (`RunNotFinishedError`) for a run that is still active.
  - It returns 409 (`StrategyNotReadyError`) when the saved run has no idea or no analysis.
  - It returns `RunLimitError` when the shared limit is full.
  - Otherwise it moves the run to `running`. Three entries are appended, or existing strategy entries are reset in place. It runs `STRATEGY_ONLY_STAGES` with `prior`, with no search.
  - `_finish` always returns the run to `done`. If the job produced no result, the saved result is kept and marked `partial`.
  - `started_at` and `created_at` keep their original values. `duration_s` becomes the saved duration plus the job's time.
- **Cancel between strategy stages.** `run_pipeline` checks the same `should_stop` before each stage, using the existing `SKIP_CANCELLED` path. A run with `include_strategy` that is cancelled ends `cancelled`. A cancelled strategy-only job ends `done` with `partial` status and its remaining entries `cancelled` (C-7).
- **11.1.3 output-token setting.** `StrategyStage.run` wraps the agent call in `llm_client.output_token_limit(6144)`. Inside that block a Groq fallback sends `max_completion_tokens: 6144`; every other call still sends 4096. Gemini requests are not changed: they set no `max_output_tokens` today, so the model default (above the 2,000-3,500 tokens a stage needs) still applies. M1/M2 calls are unaffected. `test_an_existing_call_sends_the_same_requests_as_before` pins the exact Gemini `GenerateContentConfig` and the exact Groq body (4096). `tests/test_m2_groq_fallback.py` (75 tests) is unchanged and passes.
- **Labels per I-03.** The labels live in the backend.
  - `notices.STRATEGY_TITLES` holds them and the run-manager `TITLES` uses them.
  - `StrategyStage.label` uses them for warning prefixes.
  - `STAGE_TITLES` and `orchestrator.STAGE_LABELS` were not extended (C-1). `/api/meta` therefore still lists four stages.
- **`STAGES`, `FULL_STAGES` and `POST /api/validate` unchanged.** `test_the_existing_stage_sets_are_unchanged` covers the stage sets. No file under `routes/` was touched.
- **Same `StageEvent` callback and `should_stop`.** `StageEvent` is unchanged. The strategy stages emit the existing started, finished, failed and skipped events through `on_event`.

## 5.2 skip rules implemented

1. SWOT, MVP and GTM each run only if the idea exists and the market or competitor analysis produced a result. Otherwise each is skipped with `"{label}: skipped because it needs at least one finished analysis."` and the run is `partial`.
2. One finished analysis is enough. A run with only the market result, or only the competitor result, still runs all three stages.
3. MVP runs when SWOT failed or is missing.
4. GTM runs when MVP failed or is missing.
5. If extraction failed, nothing else runs, as before. The run is `failed` and the strategy stages are skipped.
6. A strategy stage reached after the time limit has passed is skipped with the existing `SKIP_NO_TIME` text. This is the time-limit skip, not a 5.2 rule.
7. A failed or skipped strategy stage makes the run `partial`. The run is `complete` only if all requested stages finished. A strategy-only job is also `partial` if an earlier stage of the saved run had not finished.

Not in T4: 5.2 asks for notices saying "risks were not considered" and "not tied to a feature set" in rules 3 and 4. Those are agent and notice output and belong to T6, T7 and T9.

## T4 tests, grouped by the plan's test bullets (40 tests)

- **Stage objects and sets:** `test_the_strategy_sets_add_three_stages_after_the_four`, `test_every_strategy_stage_continues_on_failure_and_carries_its_label`, `test_without_a_registered_agent_a_strategy_stage_fails_plainly`
- **Order:** `test_a_seven_stage_run_runs_in_order_and_is_complete`, `test_each_strategy_stage_reads_the_ones_before_it`
- **`complete` versus `partial`:** `test_a_failed_strategy_stage_makes_the_run_partial_and_keeps_everything_else`, `test_go_to_market_runs_without_an_mvp`, `test_an_unexpected_error_in_a_strategy_agent_becomes_the_generic_stage_error`, `test_a_failed_strategy_stage_leaves_the_run_done_and_partial`
- **Skip rules from 5.2:** `test_one_finished_analysis_is_enough[market_only]`, `test_one_finished_analysis_is_enough[competitors_only]`, `test_without_any_finished_analysis_every_strategy_stage_is_skipped`, `test_a_failed_extraction_runs_nothing_else`, `test_skipped_strategy_stages_are_shown_as_skipped`
- **Cancel between strategy stages:** `test_a_cancel_between_strategy_stages_skips_the_rest_and_keeps_what_finished`, `test_a_cancel_between_strategy_stages_of_a_run`, `test_a_cancelled_strategy_job_returns_the_run_to_done`
- **Time-limit skipping and D-11:** `test_a_strategy_stage_after_the_time_limit_is_skipped`, `test_the_strategy_time_is_added_only_from_the_first_strategy_stage`, `test_the_strategy_stages_draw_on_the_second_part_of_the_budget`, `test_without_a_time_limit_the_strategy_time_changes_nothing`
- **Strategy-only job on a stored result, orchestrator level:** `test_a_strategy_only_job_starts_from_the_saved_result_without_searching`, `test_a_strategy_only_job_on_a_partial_result_stays_partial`, `test_a_strategy_only_job_with_an_earlier_skipped_stage_is_partial`, `test_a_strategy_only_job_replaces_earlier_strategy_results_and_errors`, `test_a_strategy_only_job_drops_the_old_warnings_of_the_stages_it_runs_again[cancelled]`, `test_a_strategy_only_job_drops_the_old_warnings_of_the_stages_it_runs_again[time_limit]`, `test_new_constraints_replace_the_saved_ones`
- **Strategy-only job on a stored result, run manager level:** `test_a_run_with_strategy_has_seven_stage_entries_and_saves_its_request`, `test_a_strategy_job_appends_three_stages_and_returns_the_run_to_done`, `test_a_failed_strategy_job_keeps_the_earlier_result`, `test_a_strategy_job_that_stops_unexpectedly_keeps_the_earlier_result`, `test_a_strategy_job_on_a_run_with_strategy_resets_its_stages_in_place`, `test_a_strategy_job_needs_a_saved_finished_run_with_an_analysis`
- **Concurrency limit shared with normal runs:** `test_a_strategy_job_shares_the_run_limit_with_normal_runs`
- **`FULL_STAGES` runs identical to before:** `test_the_existing_stage_sets_are_unchanged`, `test_a_full_stages_run_is_identical_to_before`, `test_a_default_background_run_is_identical_to_before`
- **Output-token setting (11.1.3):** `test_only_a_strategy_stage_raises_the_groq_output_limit`, `test_an_existing_call_sends_the_same_requests_as_before`

## Verification results (run in this step)

| # | Check | Result |
|---|---|---|
| 1 | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_orchestrator.py` | **40 passed**, 0 failed, 1 warning (Starlette/httpx deprecation), 2.41 s |
| 2 | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE` | **1932 passed**, 0 failed, 1 warning, 33.77 s. That is 1892 baseline tests plus 40 new ones. No existing test was edited; the only modified existing test file is the T1-T3 `tests/test_run_store.py`, whose hash equals the baseline. |
| 3 | FULL_STAGES equivalence | PASS, details below the table. |
| 4 | Existing LLM calls unchanged | PASS. `test_an_existing_call_sends_the_same_requests_as_before` passed. It pins the Gemini config (`system_instruction`, `temperature=0.2`, `response_mime_type="application/json"`, no `max_output_tokens`) and the Groq body (`max_completion_tokens: 4096`). `test_only_a_strategy_stage_raises_the_groq_output_limit` shows 6144 only inside a strategy stage, then 4096 for the next call. `tests/test_m2_groq_fallback.py` passed (75 tests). |
| 5 | Lazy check: `verify_app.py` sets `RUNS_DB_PATH=%TEMP%\m3t4_lazy_check\runs.db`, deletes the file first, then runs `from app import app` in a fresh interpreter | PASS. The file does not exist after the import, after `openapi()`, or after a TestClient `/api/meta` request. |
| 6 | OpenAPI and `/api/meta` | PASS. `app.openapi()` returns 9 paths. `GET /api/meta` returns 200 with stages `['extraction', 'search', 'market_opportunity', 'competitor_analysis']`. `tests/test_meta_route.py` passed (14 tests). |
| 7 | Fingerprints | PASS, details below the table. |
| 8 | `git status --porcelain` | PASS, details below the table. |
| 9 | Secret scan of the 9 changed or new files | PASS. The scan used key-shaped patterns: `AIza…`, `gsk_…`, `tvly-…`, `sk-…`, `Bearer <token>` and `PRIVATE KEY`. It found **0 hits**. A looser prefix-only scan found 3 lines, none of them a key and all present before T4: the `f"Bearer {settings.groq_api_key}"` header template (`groq_client.py:249`) and two redaction regexes (`llm_client.py:49,51`). |

**Item 3 details.** `test_a_full_stages_run_is_identical_to_before` and `test_a_default_background_run_is_identical_to_before` pass. Their expected values (`BASELINE_RESULT_SHA256 = EA97276944FC16D80D335C8E241FE907BAA7F0FBCFBB4654C769AAEDB6D2F37A`, events, the four manager stage entries) were captured from the pre-T4 code. I re-ran the side-by-side capture in this step, once with the baseline `orchestrator.py` and `utils/run_manager.py` loaded in place of the current modules and once on the current code. All 10 compared fields were equal: `stage_names`, `status` (`complete`), `timing_keys`, `events`, `result_sha256` (EA972769…F37A), `manager_state` (`done`), `manager_message`, `manager_stages`, `manager_status`, `manager_result_sha256`. The baseline capture swaps only those two modules; `llm_client`, `notices` and `base.py` are the current versions in both runs.

**Item 7 details.**
- `data/runs.db` was checked with Get-FileHash and Get-Item only. SHA-256 is `00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D`, size 311296, LastWriteTimeUtc 2026-11-08T15:31:17Z. This is identical to baseline.md.
- All 17 T1-T3 file hashes equal baseline.md (0 mismatches of 17). There were no add-only edits to T1-T3 files; `config.py` and `.env.example` are byte-identical to their baseline copies.

**Item 8 details.** Beyond the T1-T3 set recorded in baseline.md and `.agents/`, `git status --porcelain` shows exactly:
- modified: `agents/base.py`, `agents/notices.py`, `orchestrator.py`, `utils/deadline.py`, `utils/groq_client.py`, `utils/llm_client.py`, `utils/run_manager.py`
- new: `tests/m3_fakes.py`, `tests/test_m3_orchestrator.py`

## Plan-vs-code conflicts and decisions

- **C-1 Stage labels.** The T0 proposal was to add the three keys to `notices.STAGE_TITLES`. The existing `tests/test_notices.py::test_the_stage_titles_are_the_specified_ones` pins `STAGE_TITLES` to the four M1/M2 titles, and that test is not in the 20.4 list. The labels were therefore put in a new add-only `STRATEGY_TITLES`, on `StrategyStage.label`, and in the run manager's `TITLES`. `/api/meta` still publishes four stages; adding strategy stages there is T8.
- **C-2 Warning labels.** Three `WARNING_LABELS` entries were added to `notices.py` (add-only), so that strategy warnings map to their stage.
- **C-3 Skip wording.** 5.2 gives the reason as "Needs at least one finished analysis." The code follows the existing `"{label}: skipped because …"` convention: `"{label}: skipped because it needs at least one finished analysis."`.
- **C-4 Notice text.** The notice templates for strategy skips belong to T9. Until then, a no-analysis skip shows the generic notices fallback text in the stage tracker, and `{stage}` renders as "This step" or "One step".
- **C-5 Output tokens (11.1.3, I-06).**
  - Gemini sets no output limit, so it is left unchanged.
  - Groq's 4096 limit is raised to 6144 for strategy-stage calls only, via a ContextVar.
  - 12.6 defines no setting for this, so the value is a code constant and `config.py` and `.env.example` were not touched.
  - Risk for T20: Groq may answer 413 when the prompt plus 6144 requested completion tokens exceeds the account's tokens-per-minute (TPM) limit.
- **C-6 Strategy-only job budget.** D-11 defines a deadline only for `include_strategy` runs. The strategy-only job uses `STRATEGY_TIME_LIMIT_S` alone.
- **C-7 Cancel during a strategy-only job.** 5.5 shows only running → done for the job. A cancelled job therefore ends `done` with `partial` status and its remaining stages `cancelled`.
- **C-8 Job bookkeeping.** `started_at` and `created_at` are kept and `finished_at` is updated. Duration and total are cumulative. Warnings, errors and timings of the re-run stages are replaced and all others kept. This superseded iteration 1, which kept all saved warnings.
- **C-9 Scope left to T8.** `start_strategy` has no `mode` argument and never raises `StrategyAlreadyCompleteError`. It always re-runs all three stages. Constraints come from the argument, then the stored `constraints_json`, then the saved result. There is no route, `has_strategy` field or `/api/meta` change.
- **C-10 Placeholders.** Production stage lists hold `PendingStrategyAgent` placeholders. A seven-stage run with them would end `partial` with three plain stage errors. No API route can start such a run in T4.
- **C-11 Server stop during a job.** If the server stops during a strategy job, T2's store marks the row `failed` (interrupted) on the next start. The earlier `result_json` is kept. Store behaviour belongs to T2 and was not changed.

## Unresolved issues and what remains for T5-T8

- T5, T6 and T7 must provide the real SWOT and Risk, MVP and GTM agents with their prompts, register them in place of the `PendingStrategyAgent` placeholders in `STRATEGY_ONLY_STAGES`, and add the missing-SWOT and missing-MVP notices from 5.2.
- T8 must add the API surface: `include_strategy` and `constraints` on `POST /api/runs`, `routes/strategy_routes.py` (with `mode = missing` or `all` and the `StrategyAlreadyCompleteError` case), `has_strategy`, `/api/meta` additions, and the no-search spy test.
- T9 must add notice templates and titles for the strategy stages (C-4).
- T20 must measure strategy-stage time and output tokens live and tune `STRATEGY_MAX_OUTPUT_TOKENS` against the Groq TPM limit (C-5).
- Nothing was run live. All T4 evidence comes from fake agents and fake providers.

Helper scripts used in this step stayed in `.agents/tasks/m3-t4/` (`verify_app.py`, `check_hashes.ps1`, `capture_full_stages_test.py`, `final_checks.ps1`). Capture output went to `%TEMP%`. T5 has not been started.

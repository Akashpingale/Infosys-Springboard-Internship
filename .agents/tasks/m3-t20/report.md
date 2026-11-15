# T20 report: Live verification scripts and protocol

Plan entry: `MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md` Section 18, T20 (line 1323), with Section 20.7 (live protocol and review checklist), 5.4 (credit and time budget), 10.4 and 10.8 (Advisor routing, missing sections, A-R4), 12.2 (strategy on a saved run), 15.1 and 15.4 (secrets, credit controls), 17.1 (script names), 22.3 and I-21 (existing runner pattern: `scripts/run_live_m2.py`, `scripts/make_m2_report.py`, `tests/test_m2_live_runner.py`).

**None of the three scripts was run live.** They were run only with `--fake`, inside pytest (socket block and placeholder keys from `tests/conftest.py`) and in two helper runs from this folder with placeholder keys, a socket guard (`fake_demo.py`) and the fake transports' own blocks (`cli_smoke.py`). No provider was called and no credit was used. Nothing from T21 was done.

## Files

`hashes.py check` against `baseline_hashes.json` (recorded before the first edit, 138 uncommitted files) lists only these six new files. No existing file was changed, so there is no existing-test edit and no undo proof to give.

| File | Status | Size | SHA-256 (tested state) | Purpose |
|---|---|---|---|---|
| `scripts/run_m3_live.py` | new | 449 lines | 3A0873B4…25F0B71 | L-1: the three Milestone 2 ideas through all seven stages; per-stage seconds and calls; JSON, Markdown and `run_summary.json`; printed checklist. Also holds the shared pieces the other two scripts import (flags, key check, meter, fake-client switch, redaction, checklist, Markdown) |
| `scripts/run_m3_retro_live.py` | new | 155 lines | 958BC01C…4BAEC81D | L-2: strategy on a saved run (default `docs/test_runs_m2/agritech.json`), no search; compares strategy seconds with the L-1 run |
| `scripts/check_advisor_live.py` | new | 215 lines | DA56B331…F6C9BDC8 | L-3: the eight fixed Advisor questions on a saved run (default `docs/test_runs_m3/agritech.json`) |
| `docs/test_runs_m3/README.md` | new | 54 lines | 36B44C0A…15DD72FC | What each output file is, how to run the scripts, the fixed questions, the counting rules, and **"Status: not executed."** |
| `tests/m3_live_fakes.py` | new | 54 lines | 568B05F8…A4E8A3A9 | The fake clients `--fake` selects (see plan-vs-code point 1) |
| `tests/test_m3_live_scripts.py` | new | 504 lines, 38 tests | 0487F09E…F38CA088 | Runs each script with `--fake` end to end and checks the files; guard, key, failure and counting tests |

Full hashes and modification times are in `tested-hashes.txt`. The scripts were last edited at 14:08:15 and the README at 14:07:10; the CLI smoke run (`cli-smoke.log`, written 14:09:53) ran after both. The test file was last edited at 14:17:04 (it now reads the placeholder key values through the settings loader instead of repeating them as literals); the final full suite (`pytest-full-3.log`, written 14:19:42) and the final T20 run (`pytest-t20-4.log`) ran after it. New files carry no comments or docstrings (plan 0.5).

Helper files (only in this folder): `hashes.py` (copy of the T19 helper; `save` refuses to overwrite an existing baseline), `baseline_hashes.json`, `tested-hashes.txt`, `fake_demo.py` and `fake-demo.log` (first fake run of the three scripts, before two output fixes; its output folder was deleted as stale), `cli_smoke.py`, `cli-smoke.log` and `cli-output/` (the scripts started as real processes, final code), `pytest-*.log`.

## Requirement mapping

| T20 / 20.7 requirement | Where |
|---|---|
| `run_m3_live.py`: three ideas from `data/test_ideas` | `IDEAS = ("agritech.json", "fintech_cashflow.json", "foodtech_surplus.json")`, the Milestone 2 domains (20.7 L-1). Test `test_a_live_run_calls_the_seven_stages_as_the_run_manager_does` checks the three industries |
| Full seven stages | `utils.run_manager.strategy_pipeline(..., prior=None)` with `run_time_limit_s()` and `strategy_time_limit_s()`, exactly the call `RunManager._call_pipeline` makes for a run with strategy. No constraints are passed (point 5) |
| Per-stage timings | `seconds` per stage key and `total` from `PipelineResult.timings`; `strategy_seconds` = sum of the three strategy stages |
| Call counts | `Meter` wraps, for the run only, the `generate_json` name of the seven agent modules (LLM calls), `groq_client.generate_json` (Groq fallback attempts) and `web_search_agent.search` (Tavily requests), and files each call under the stage that was running (from the `on_event` callback). Seams are restored afterwards |
| Warnings | `warnings` and `errors` (stage, code, safe message) per idea |
| 20.7 "What to look at" | `counts`: SWOT items per quadrant, risks, `risks_by_category`, `coverage_gaps`; MVP `in_scope` and `deferred` names, capacity, planned, `over_capacity`, `constraints_assumed`; GTM target segment, differentiator status, channels, `start_here`, its first experiment, phase count. `contract_violations` = `check_m3_contracts.check_result` lines ("zero rule violations") |
| Saved JSON and Markdown to `docs/test_runs_m3/` | `<idea>.json` (the full result) and `<idea>.md` (submitted idea, seconds and calls table, rule check, checklist, then `report_markdown(result, full=True)` with headings pushed one level down) |
| Summary file | `run_summary.json`: `generated`, `fake`, `model`, `ideas_attempted`, `ideas_executed`, `runs` |
| `run_m3_retro_live.py`: strategy on a saved run, no searches | `strategy_pipeline(..., prior=saved, rerun=<missing stages>, time_limit_s=strategy_time_limit_s(), strategy_time_limit_s=None, constraints=saved.constraints)`, the call the strategy route's job makes in `missing` mode. Refuses, like the route, a run without an idea or analysis (`StrategyNotReadyError` message) and a run with nothing missing (`StrategyAlreadyCompleteError` message). Searches are counted and printed with the note that a strategy job on a saved run makes none; seconds are those of the job alone and are compared with the strategy seconds of the L-1 run in `run_summary.json` of the same folder |
| `check_advisor_live.py`: the fixed question set | `QUESTIONS`: market, competitor, a risk, MVP priority, first GTM channel, out of scope, injection attempt, missing section (20.7 L-3). Each is sent through `advisor_agent.answer`, the function the chat route calls; refuses a saved run whose status the chat route refuses (`AVAILABLE_STATUSES`) |
| A printed review checklist per output | The Section 20.7 checklist, unticked, printed after each idea, after the retro run (items 1 to 6 and 8) and after the Advisor set (item 7), with measured values next to items 3, 4, 5, 6, 7 and 8. The same lines are in each Markdown file |
| No key output | Keys are only checked for presence (`missing_keys` names the variable). Every printed line and written file passes through `redact`, which replaces each configured key with the store's `[redacted]` token. Tests check that the placeholder keys appear in no file and no output, and that the model name is never printed |
| Runners use the settings loader and never print settings | `config.get_settings()` for keys and model; the time limits through `run_manager`. Nothing from settings is printed; the summary files record the model name (point 6) |
| Honest "not executed" markers | `docs/test_runs_m3/README.md` opens with **Status: not executed.** and says the scripts were tested only with `--fake`. Fake outputs say "Fake run … nothing here is evidence" at the top and carry `"fake": true` |
| Integration with the existing runner pattern (I-21) | Same `--yes` guard, missing-key messages and "No result or summary file was written." as `run_live_m2.py`; an unreadable idea or an unexpected error is recorded as not executed without a result file; exit 0 only when every idea ran |
| Tests: unit tests run each script with fakes (`--fake`) end to end and write valid files | `--fake` (mutually exclusive with `--yes`) installs `tests/m3_live_fakes.fake_clients`; the tests below run all three scripts that way, validate every JSON file as `PipelineResult`, and run `scripts/check_m3_contracts.py` on them (exit 0) |

## Tests (`tests/test_m3_live_scripts.py`, 38)

Guards and keys (13):
- `test_without_yes_or_fake_nothing_runs_and_no_file_is_written` (3, one per script): exit 1, no folder, the message names `--yes` and `--fake`.
- `test_yes_and_fake_cannot_be_combined` (3).
- `test_a_missing_key_is_named_and_nothing_is_written` (7): L-1 needs `LLM_API_KEY`, `LLM_MODEL`, `TAVILY_API_KEY`; L-2 and L-3 need the two LLM ones. No key value and no model name is printed.

`run_m3_live.py` (8):
- `test_the_fake_run_writes_valid_files_for_the_three_ideas`: exit 0; summary `fake` true, 3 of 3 executed; each result validates and is `complete`; seconds equal the result's timings for the seven stages and total; LLM calls per stage exactly extraction 1, search 0, market 1, competitors 2, SWOT 1, MVP 1, GTM 1 (total 7, Groq 0, searches 0); counts equal the result's; no rule violation; `check_m3_contracts.main` on the three files returns 0; each Markdown starts with the fake-run line and holds the stage table, the checklist (items 1 to 6 and 8, not 7) and the exported report with its strategy sections; three printed checklists; no key anywhere.
- `test_a_fake_run_without_out_writes_to_a_new_temporary_folder`: files land in a new `m3_fake_*` folder; `docs/test_runs_m3/` is unchanged.
- `test_a_live_run_calls_the_seven_stages_as_the_run_manager_does`: with `--yes` and a spy in place of `strategy_pipeline`: no idea override, no prior, no constraints, `run_time_limit_s()` and `strategy_time_limit_s()`; summary `fake` false with the model; the model name is not printed.
- `test_a_partial_run_is_recorded_as_it_happened`: status `partial`, GTM counts null, the stage error kept, no "start here" hint.
- `test_an_unexpected_error_is_recorded_without_a_result_file`: exit 1, every idea "unexpected error (RuntimeError)", only the summary file, no exception text in it.
- `test_the_meter_counts_each_search_request_in_its_stage_and_restores_the_seam`: the real `run_queries` over a fake Tavily transport: 2 searches in `search`, 1 in `market_opportunity`; the seam is restored.
- `test_printing_a_character_the_console_cannot_show_does_not_stop_a_run`: a cp1252 console gets `?` for the rupee sign and Devanagari instead of an error (point 10).
- `test_the_meter_counts_a_groq_takeover_in_the_stage_that_made_the_call`: the real `llm_client` path with a fake Gemini 429 and a fake Groq reply: 1 LLM call and 1 Groq call in `swot_risk`.

`run_m3_retro_live.py` (12):
- `test_the_fake_retro_run_adds_the_strategy_to_a_saved_run_without_a_search`: a saved four-stage result gains SWOT, MVP and GTM, `complete`; idea, search, market and competitors unchanged; 1 LLM call per strategy stage, 0 searches; seconds of the job alone; the L-1 strategy seconds (63.5) shown; no rule violation; contract script exit 0. The analysis fakes are not installed in this mode, so any search would reach the counted seam.
- `test_the_retro_job_runs_the_missing_stages_as_the_strategy_route_does`: with SWOT saved, only MVP and GTM run, with the saved constraints and `strategy_time_limit_s()`; no Tavily key needed.
- `test_a_saved_run_the_strategy_job_would_refuse_is_left_alone` (3: strategy complete, no analysis, no idea).
- `test_an_unreadable_saved_run_is_reported_and_nothing_is_written` (6: absent, not JSON, not a result × L-2 and L-3).
- `test_a_saved_run_without_an_idea_file_is_refused`.

`check_advisor_live.py` (4):
- `test_the_fake_advisor_check_asks_the_eight_fixed_questions`: statuses ok ×5, out_of_scope, out_of_scope, no_evidence; 1 LLM call each except the missing-section question (0); 0 searches; the five topic answers cite market, competitors, risks, mvp and gtm; the out-of-scope text is the Advisor's message; the missing-section text is "Your results do not include the MVP feature plan yet. …"; Markdown and printed checklist item 7.
- `test_a_failed_question_is_recorded_and_the_others_are_still_asked`: a provider error on question 2 is stored with its code and message, the other seven are answered, exit 1.
- `test_the_advisor_check_needs_a_finished_result`: a `failed` saved run gets the chat route's "Questions open once the validation has finished." and nothing is asked.
- `test_the_advisor_check_uses_the_l1_agritech_result_by_default`: defaults, and (while no L-1 output exists) the "Run scripts/run_m3_live.py first" message.

README (1):
- `test_the_readme_explains_every_file_and_every_fixed_question`: every default output name, the three `--yes` commands and the eight question texts are in the README; while `docs/test_runs_m3/run_summary.json` does not exist it must say **Status: not executed.**

## Fake-run evidence (`cli-smoke.log`, final code, scripts started as processes)

```
run_m3_live.py --help / run_m3_retro_live.py --help / check_advisor_live.py --help -> exit 0
run_m3_live.py (no flag)  -> exit 1 "This script makes real API calls and spends credits. Nothing has been run." ... "No result or summary file was written."
run_m3_live.py --fake     -> exit 0  agritech complete total=0.1 s strategy=0.1 s llm=7 groq=0 searches=0 warnings=7 errors=0 violations=0 (same for the other two)
run_m3_retro_live.py --fake (default saved run docs/test_runs_m2/agritech.json) -> exit 0  complete llm=3 groq=0 searches=0 violations=0
check_advisor_live.py --fake -> exit 0  statuses ok x5, out_of_scope x2, no_evidence; llm 1 x7 and 0 for question 8
files: advisor_agritech.json/.md, agritech/fintech_cashflow/foodtech_surplus .json/.md, retro_agritech.json/.md, retro_summary.json, run_summary.json
store file created: False   (RUNS_DB_PATH pointed at a temp path; the scripts never open a store)
```

In fake mode the search stages get the canned bundles of `tests/pipeline_fakes.py`, so the search count of a fake full run is 0 (point 2). The fake strategy replies are the agritech drafts of the T5 to T7 tests, so all three fake ideas produce the same agritech strategy, and on the real saved M2 run the fake MVP adds the founder's real features as deferred items. That is expected of fakes and is why fake outputs are marked as not evidence.

## Plan-vs-code points (recorded, not stop conditions)

1. **Test files not named by the entry.** T20 names only the scripts and the README as new files and asks for unit tests that run each script with fakes; 17.3 lists no T20 test file. Added `tests/test_m3_live_scripts.py` (as `tests/test_m2_live_runner.py` did for M2) and `tests/m3_live_fakes.py`, the fake clients the `--fake` flag selects. They live with the other fakes and reuse them (`use_full_pipeline`, the T5 to T7 draft replies); the scripts import them only under `--fake`, so the live path imports nothing from `tests/`. `fake_clients` also blocks the real transports (`genai.Client`, `requests.post`) for the duration, so a missed seam fails instead of calling a provider. `tests/m3_fakes.py` (T4) was not edited.
2. **Search counts in fake mode.** Searches are counted at `web_search_agent.search`, the single function that sends a Tavily request, which is exact for live runs. The fake search stages return canned bundles without a request, so a fake full run reports 0 searches; the seam is proven with the real `run_queries` in its own test.
3. **L-3 cost.** 20.7 budgets 8 LLM calls. The Advisor answers a question about a missing section in code (`advisor_agent.answer` → `missing_reply`, 10.4), so the set makes 7. The README says so.
4. **"A question about a missing section".** L-1 normally produces every section, so question 8 is asked on the same saved run with SWOT, MVP and GTM removed (a run without strategy, A-R4 #8). It is labelled "the saved run without its strategy" in every output.
5. **Constraints.** The plan does not say whether L-1 passes resource constraints. The scripts pass none, so each MVP plan shows its assumed defaults (`constraints_assumed`); L-4 covers constraints entered in the UI. The README says so.
6. **Model name.** "Never print settings" is kept for printed output. The summary files record `model` (LLM_MODEL), as the M2 runner's summary does, so results can be traced; the README says so. No key or other setting is written.
7. **Retro inputs.** The saved run is a file, so its submission is read from `data/test_ideas/<saved file stem>.json` (the idea that produced it) and its stored constraints are the result's `constraints`. Only `missing` mode exists in the script, the API default; `mode=all` is not part of L-2. The retro summary's seconds are those of the job alone; the result file keeps the run's cumulative total, as the API stores it.
8. **Advisor questions are independent.** Each question is asked with no history, so each answer belongs to one question. The chat route's cooldown and turn limits sit around `advisor_agent.answer` and are not exercised (they are unit-tested in T11).
9. **Observed, not changed (T9 code):** the "Time taken" line of `report_markdown(full=True)` prints the three strategy stage keys raw (`swot_risk 0.0s, mvp_recommendation 0.0s, go_to_market 0.0s`) because `stage_label` knows only the M1/M2 stages. This also affects `GET /api/runs/{id}/report.md`. Outside T20's files; listed for the final report.
10. **Console encoding.** On Windows a redirected `stdout` uses the ANSI code page; a feature or channel name with "₹" or Hindi text would make `print` raise mid-run. `say` replaces such characters for the console only; files are always UTF-8.

## Fingerprints

| Check | Start of T20 | End of T20 |
|---|---|---|
| `data/runs.db` SHA-256 (Get-FileHash) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D |
| `data/runs.db` size, LastWriteTimeUtc (Get-Item) | 311296, 2026-11-08T15:31:17Z | 311296, 2026-11-08T15:31:17Z |
| Uncommitted files vs. baseline (`hashes.py check`) | 138 hashed | only the six new files above |
| Branch, HEAD | main, a098aef | main, a098aef |
| `docs/test_runs_m3/` | absent | `README.md` only |

## Commands run and results

| # | Command (PowerShell, `$env:PYTHONIOENCODING="utf-8"`) | Result |
|---|---|---|
| 1 | `Get-ChildItem -Force .agents\tasks`; `Get-ChildItem -Force .agents\tasks\m3-t20` | task folders listed; exit 1 because `m3-t20` did not exist yet |
| 2 | `Test-Path .agents\tasks\m3-t20`; `Get-ChildItem -Force .agents\tasks\m3-t19` | False; T19 folder listed (review.json present) |
| 3 | `git status --porcelain=v1 -uall \| Measure-Object -Line`; `git log --oneline -3`; listing of m3-t10..t12 | 388 lines; HEAD a098aef |
| 4 | `python -B .agents\tasks\m3-t20\hashes.py save`; `Get-FileHash data\runs.db` | "saved 138 files" (before any project edit); 00A4F859…8337D |
| 5 | `Get-Item data\runs.db`; `Get-ChildItem scripts`, `data\test_ideas` | 311296, 2026-11-08T15:31:17Z; 6 ideas, existing runners |
| 6 | Listings of backend files, `tests\__init__.py` (True), `scripts\__init__.py` (False), `docs`, `docs\test_runs_m2`; `Get-Content` of the three idea files | read only |
| 7 | Lint-config search and longest-line scan of the new files | only `pytest.ini`; long lines wrapped to the existing M3 files' width |
| 8 | `python -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_live_scripts.py` (`pytest-t20-1.log`) | 37 passed, 1 warning |
| 9 | `python -B .agents\tasks\m3-t20\fake_demo.py` (`fake-demo.log`) | three fake runs, exit 0 each; showed a double full stop in the retro timing hint and a retro "total" that included the saved run's seconds; both fixed, output folder deleted as stale (row 16) |
| 10 | `Get-Content` of the fake `agritech.md` and `advisor_agritech.md` | format checked; point 9 observed |
| 11 | same pytest command (`pytest-t20-2.log`) | 37 passed, 1 warning |
| 12 | full backend suite `python -B -m pytest -q -p no:cacheprovider -rfE` (`pytest-full.log`) | 2453 passed, 1 warning (Starlette/httpx deprecation) |
| 13 | `hashes.py check`; runs.db fingerprint; `docs\test_runs_m3` listing; branch and HEAD | six new files only; fingerprint unchanged; README only; main a098aef |
| 14 | same pytest command after the console-encoding change and its test (`pytest-t20-3.log`) | 38 passed, 1 warning |
| 15 | `python -B .agents\tasks\m3-t20\cli_smoke.py` (`cli-smoke.log`) | `--help` exit 0 ×3; no flag exit 1; `--fake` exit 0 ×3; 12 files; no store file |
| 16 | `Remove-Item .agents\tasks\m3-t20\fake-output -Recurse` | stale output of row 9 removed (my own helper output) |
| 17 | full backend suite (`pytest-full-2.log`) | 2454 passed, 1 warning, 0 failures (2416 before T20 + 38) |
| 18 | `hashes.py check`; runs.db fingerprint; `Get-FileHash` of the six files; key-pattern scan (AIza, gsk_, tvly-, sk-, Bearer, PRIVATE KEY) of the six files; `git status --porcelain -uall` count; branch, HEAD | six new files only; fingerprint unchanged; hashes as in the Files table; 0 hits; 417 lines (the six files plus this folder's helpers and logs); main a098aef |
| 19 | `pytest --collect-only tests/test_m3_live_scripts.py` (`pytest-t20-collect.log`) | 38 test ids, listed above |
| 20 | `Get-FileHash` and `Get-Item` of the six files into `tested-hashes.txt` | first version of the file (superseded by row 23) |
| 21 | Test-file edit only (placeholder keys read through `get_settings()`), then the full backend suite (`pytest-full-3.log`) | **2454 passed, 1 warning**, 0 failures |
| 22 | `pytest tests/test_m3_live_scripts.py` (`pytest-t20-4.log`) | **38 passed**, 1 warning |
| 23 | `hashes.py check`; runs.db fingerprint; hashes, line counts and write times of the six files into `tested-hashes.txt`; key-pattern scan of the six files (also for the placeholder values); `docs\test_runs_m3` listing; branch, HEAD; `git status --porcelain -uall` count | six new files only; fingerprint unchanged; hashes as in the Files table; 0 hits; `README.md` only; main a098aef; 422 lines (the six files plus this folder's helpers and logs) |

No backend or dev server was started. No live script was run without `--fake`. No network or provider call was made. Nothing was committed, pushed, reset, reverted or stashed; no branch was created or switched. No `.env` file was opened or printed and `data/runs.db` was only fingerprinted.

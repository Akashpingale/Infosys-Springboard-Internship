# T20 review: Live verification scripts and protocol

Verdict: **APPROVED**. No blockers.

Sources: the plan's T20 entry (l.1323), 20.7, 5.4, 10.4, 10.8, 12.2, 15.1, 15.4, 17.1 and 17.3; the brief with all addenda; `report.md`; the six new files; `scripts/run_live_m2.py` (I-21). I also read the unchanged code the scripts copy: `utils/run_manager.py:390-394` and `:534-545`, `routes/chat_routes.py:96-100` and `:134`, and `orchestrator.py:377-378` and `:431`.

## What I ran (all offline)

| Check | Result |
|---|---|
| `pytest tests/test_m3_live_scripts.py` (`review-pytest-t20.log`) | 38 passed, 1 warning (Starlette/httpx) |
| Full backend suite (`review-pytest-full.log`) | 2454 passed, 1 warning, 0 failures. Same count as the coder's `pytest-full-3.log` |
| The scripts as processes (`review_fake_runs.py`, `review-fake-runs.log`). Placeholder keys, `RUNS_DB_PATH` on a temp path, `--fake` runs under a socket and DNS guard | `--help` exits 0 for all three scripts. With no flag, each script exits 1 and prints the `--yes`/`--fake` message and "No result or summary file was written.". `--yes --fake` exits 2. `run_m3_live --fake` exits 0: 3 of 3 runs complete, each with 7 LLM calls, 0 Groq calls, 0 searches and 0 violations. `run_m3_retro_live --fake` (default saved run, the M2 agritech result) exits 0: complete, 3 LLM calls, 0 searches, seconds compared with the L-1 fake run. `check_advisor_live --fake` exits 0: statuses ok ×5, out_of_scope ×2, no_evidence; 1 LLM call for each of questions 1-7 and 0 for question 8 |
| Output files | The four result files validate as `PipelineResult`. `scripts/check_m3_contracts.py` on them exits 0 ("All 4 file(s) pass"). Every Markdown file starts with the fake-run line. The summaries record `"fake": true` and model `fake` |
| Secrets | No placeholder key value appears in any output file or console line. The configured model name is never printed. Key patterns (AIza, gsk_, tvly-, sk-, Bearer, PRIVATE KEY) have 0 hits in the outputs and in the six new files |
| No keys (`review_nokeys.py`) | With all four keys blank, the three `--fake` runs still pass, so the README's "no key is needed" is true. `--yes` stops at the key check, names the three variables and writes nothing |
| Failure paths (`review_spot_failed.py`, `--fake` with `strategy_pipeline` stubbed) | Three L-1 cases: extraction failed, every strategy stage skipped, and every strategy stage failed. In each, the script exits 0 and writes the result files and the summary. Counts are null and errors are kept; nothing crashes. L-2 with every strategy stage failed records the 3 errors and the job's seconds. L-3 refuses a `failed` saved run and answers on a partial one |
| Store | No run created a store file at `RUNS_DB_PATH`. `docs/test_runs_m3/` still holds only `README.md` |

## Hashes and fingerprint

- `review_check.py` (`review-hashes.log`) compares current hashes with `baseline_hashes.json` (138 entries, written at 13:30:49, before the first new file at 13:51:47).
  - Only the six new files differ. No existing file changed, so there is no existing-test edit and no undo proof to check.
  - The 144 non-`.agents` git status entries are the 138 baseline entries plus the 6 new files.
- The six files match `tested-hashes.txt`. Their newest write time is 14:17:04, before the coder's final runs (`pytest-full-3.log` at 14:19:42, `pytest-t20-4.log` at 14:19:54). The scripts and the README were last written before `cli-smoke.log` (14:09:53).
- All 54 entries of T19's `resume-final-hashes.txt` match both the T20 baseline and the current files.
- Neither T20 nor this review wrote to the ignored folders (`__pycache__`, `.pytest_cache`, `web/dist`, `web/test-results`).
- `data/runs.db` was the same before and after: SHA-256 00A4F859…8337D, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17Z. No -wal or -shm file. Branch main, HEAD a098aef.

## Coverage against the T20 entry and 20.7

- **L-1, `run_m3_live.py`**
  - Runs the three M2 ideas from `data/test_ideas`.
  - The pipeline call (`strategy_pipeline(..., prior=None)` with `run_time_limit_s()` and `strategy_time_limit_s()`, l.401) is the same call `RunManager._call_pipeline` makes (run_manager.py:540).
  - Records per-stage seconds, warnings and errors.
  - Counts LLM, Groq and search calls per stage. Every agent looks up these functions on its module at call time (`call_structured(..., caller=generate_json)`, `llm_client` calling `groq_client.generate_json`, `run_queries` calling `search`), so the counts hold for live runs too.
  - Records SWOT items per quadrant, risks by category and the gaps, MVP features in and out of scope, the channels, the start-here channel and its first experiment, and the `check_result` violations.
  - Writes `<idea>.json`, `<idea>.md` and `run_summary.json` to `docs/test_runs_m3/` by default.
- **L-2, `run_m3_retro_live.py`**
  - The default saved run is the M2 agritech result; the L-1 result would have nothing missing.
  - Refuses the same cases as the route, with the `StrategyNotReadyError` and `StrategyAlreadyCompleteError` messages.
  - Runs only the missing stages with `time_limit_s=strategy_time_limit_s(), strategy_time_limit_s=None` (l.115), as run_manager.py:534 does.
  - Counts searches and reports the number, then compares the job's seconds with the strategy seconds of the L-1 run.
- **L-3, `check_advisor_live.py`**
  - Asks the eight question kinds of 20.7 (l.47) through `advisor_agent.answer`, the function the chat route calls.
  - Refuses saved runs whose status the route refuses (l.175).
  - Question 8 is asked on the run with its strategy removed and is answered without a model call (10.4).
  - A failed question is recorded and the remaining questions are still asked.
- **Checklist:** the eight 20.7 items, unticked, are printed after each output and written into each Markdown file, with measured values next to the items they concern.
- **No key output:** keys are only checked for presence. Every printed line and every written file goes through `redact` (l.152).
- **Settings loader:** the scripts read settings through `config.get_settings()` and print none of them. The summary files record the model name, as `run_live_m2.py` does (report point 6).
- **"Not executed" marker:** `docs/test_runs_m3/README.md` opens with **Status: not executed.**, and every fake output says it is not evidence.
- **Tests:** 38 tests. Each script runs end to end with `--fake` and its files are validated; further tests cover the guards, missing keys, failures and call counting.
  - Tests pass `--yes` only where the pipeline is replaced by a spy or a guard stops the run first, always under conftest's socket block. No test runs a script live.
- **Conventions:** the new files have no comments or docstrings. The only comment is `# noqa: E402`, as in the approved `check_m3_contracts.py`.
  - `tests/m3_live_fakes.py` and the test file are new test files, which the entry's test requirement needs.
  - The live path imports nothing from `tests/`.
- **Report:** plan-vs-code points 1-10 match the code. None of them changes behaviour or an API.

## Observations (not blocking)

- **Retro strategy seconds on a partly strategised run.** `strategy_seconds` (run_m3_live.py:246) adds up every strategy timing in the result. When the saved run already holds part of the strategy, `run_pipeline` keeps those saved timings (orchestrator.py:377). The retro summary's `strategy_seconds` and the printed "strategy=" value then include seconds the job did not spend, although the README says the retro seconds are the job's alone. The default L-2 input (the M2 run, which has no strategy) is not affected. This only matters with `--saved` on a run that already has part of its strategy.
- **Rule check on a run without strategy.** If a run has no strategy section (extraction failed, or every strategy stage was skipped or failed), the Markdown "Strategy rule check" still says "No strategy rule is broken" (l.373), and `contract_violations` is `[]`. Neither says that nothing was checked. The status, the stage table and the null counts next to it do show the gap. T21 should not count such a run as "zero rule violations" in docs/12.
- **Raw stage keys in the report.** Report point 9 is confirmed in every fake Markdown file: T9's `stage_label` leaves the three strategy keys raw in the "Time taken" line. This is outside T20's files and belongs in the final report.

## Housekeeping

- I wrote files only in this folder: `review_check.py`, `review_t19_cross.py`, `review_guard_launch.py`, `review_fake_runs.py`, `review_spot_failed.py`, `review_nokeys.py`, their logs, `review-fake-output/`, `review-spot-output/`, `review-nokeys-output/`, `review.md` and `review.json`.
- Every script run used `--fake`, with one exception: one `--yes` call with all keys blank. It stops at the key check before anything runs (the same path as the unit tests' missing-key cases), and it ran inside the socket guard.
- No provider or network call was made and no server was started. No `.env` file was opened, and `runs.db` was only fingerprinted. Nothing was committed, pushed, reset, reverted or stashed.

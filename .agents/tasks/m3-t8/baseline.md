# M3 T8 baseline (pre-T8)

- HEAD: a098aef (branch main), working tree carries uncommitted T1-T7 work.
- Nothing in the project tree was changed. Python ran with `-B`; `git status --porcelain` after capture equals `baseline-git-status.txt`.

## Files

| File | Contents |
|---|---|
| `baseline-git-status.txt` | `git status --porcelain` at start (14 modified, 18 untracked project files plus `.agents/`). |
| `baseline-hashes.json` | SHA-256 of all 32 files git status lists (excluding `.agents/`) plus pinned `routes/run_routes.py`, `routes/meta_routes.py`, `app.py`, `tests/test_runs_api.py`, `tests/test_meta_route.py` (`models/api.py`, `utils/run_manager.py`, `orchestrator.py` are already in the list): 37 files, none missing. Also HEAD, branch and the runs.db fingerprint. |
| `baseline-api.json` | Captured responses: `post_runs`, `run_detail`, `run_list`, `meta`, plus `checks`. |
| `baseline-openapi.json` | Full `/openapi.json` (keys sorted). |
| `capture_api.py` | Capture script. |
| `hashes.ps1` | Hash/fingerprint script. |

## data/runs.db fingerprint (Get-FileHash / Get-Item only, never opened)

- SHA-256 `00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D`, size 311296, LastWriteTimeUtc 2026-11-08T15:31:17Z.
- Matches expected: **True** (all three values).

## How the capture works

`capture_api.py` sets the conftest fake env (`TAVILY_API_KEY`, `LLM_API_KEY`, `LLM_MODEL=test-model`) and `RUNS_DB_PATH=<tmp>/env-runs.db` before importing `app`, removes `BACKEND_URL`, `LLM_TIMEOUT_S`, `SEARCH_TIMEOUT_S`, `GROQ_API_KEY` after import (as `tests/conftest.py` does), and blocks non-local sockets. It builds `create_app()`, sets `app.state.run_manager = manager_with(store_in(<tmp>/store), FakePipeline())` from `tests/run_fakes.py`, then with `TestClient`: `POST /api/runs` with `{"submission": SUBMISSION}` (no include_strategy/constraints), waits for the run, then `GET /api/runs/{id}`, `GET /api/runs`, `GET /api/meta`, `GET /openapi.json`.

Normalisation: the run id is replaced by `<RUN_ID>` wherever it occurs (including inside strings); any string matching ISO-8601 date-time (`YYYY-MM-DD[T ]HH:MM:SS[.fff][Z|±HH:MM]`) becomes `<TIMESTAMP>`. Durations are deterministic (the fake reports 1.0 s per stage, 3.0 s total), so they are kept. `/api/meta` and OpenAPI need no normalisation.

`checks` records: whether importing/creating the app created the `RUNS_DB_PATH` file (baseline: false), whether real `data/runs.db` mtime is unchanged across the capture (baseline: true), and OpenAPI path and schema name lists.

## Rerun against post-T8 code

From the repo root:

```
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe -B .agents\tasks\m3-t8\capture_api.py post
powershell -NoProfile -ExecutionPolicy Bypass -File .agents\tasks\m3-t8\hashes.ps1 post
```

This writes `post-api.json`, `post-openapi.json`, `post-hashes.json` next to the baseline files. Compare `post_runs`, `run_detail`, `run_list` field by field (they must be identical for a default request); `meta` should differ only by what T8 adds; the OpenAPI diff should show only T8 additions (e.g. new request fields / meta fields). Caveat: `FakePipeline.__call__` accepts only `idea`, `on_event`, `should_stop`, `time_limit_s` keyword arguments (baseline call kwargs: `idea`, `submission`, `time_limit_s`); if T8 makes the run manager pass extra kwargs to the pipeline on a default run, the capture will fail there, which is itself a contract signal.

## Captured pre-T8 values

- `POST /api/runs` default: 202, body `{"run_id": "<RUN_ID>", "state": "queued"}` (keys `run_id`, `state`).
- Run detail: state `done`, result.status `complete`; top-level keys `cancel_requested, created_at, duration_s, elapsed_s, finished_at, id, idea_override, industry, message, result, stages, started_at, state, submission, title`.
- Stages (key / label / status), each entry has keys `duration_s, elapsed_s, key, label, message, started_at, status`:
  - extraction / Understanding your idea / done
  - search / Searching the web / done
  - market_opportunity / Analysing the market / done
  - competitor_analysis / Comparing competitors / done
- Result keys: `competitor_candidates, competitor_search, competitors, constraints, errors, evidence_strength, executive_summary, gtm, idea, market, market_search, mvp, notices, search, status, swot, timings, verify_next, warnings`.
- Run list row keys: `created_at, duration_s, id, industry, state, status, title` (status `complete`, state `done`).
- `/api/meta` top-level keys: `app_name, examples, industries, limits, providers, run_limits, stages, version` (version `0.1.0`; stages = the four above; run_limits `time_limit_s 162.0, max_concurrent_runs 2, competitor_max_extra_queries 5, competitor_results_per_query 3, evidence_max_items 12`).
- OpenAPI paths: `/api/ideas/extract, /api/meta, /api/runs, /api/runs/{run_id}, /api/runs/{run_id}/cancel, /api/runs/{run_id}/report.md, /api/search, /api/validate, /health`.

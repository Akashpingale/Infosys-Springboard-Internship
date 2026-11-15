# T12 report: Backend consolidation checkpoint

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T12 (line ~1231). Rules checked come from Sections 6.1 to 6.4, 7.4, 7.5, 8.4, 8.5, 9.4, 9.5, 12.5 (none), 15.1 and acceptance X-6, X-8, X-9. Nothing from T13 or later was built. No UI file was edited.

## Files

| File | Status | Size | Purpose |
|---|---|---|---|
| `scripts/check_m3_contracts.py` | new | 461 lines | Offline check of saved `PipelineResult` JSON against the strategy rules. Usage: `python scripts/check_m3_contracts.py <file.json> [...]`; exit 0 when every file passes, 1 when any file breaks a rule or cannot be read |
| `tests/test_m3_no_secrets.py` | new | 401 lines, 52 tests | Planted fake keys never leave the process; the contract script passes on the synthetic result and flags planted violations |
| `web/src/api/types.gen.ts` | regenerated (git-ignored, untracked) | 64,455 → 73,150 bytes | Regenerated from the dumped OpenAPI file; it now also has the three chat routes added in T11 |

`hashes.py check` against the start-of-task baseline (47 uncommitted files) lists only `new scripts/check_m3_contracts.py` and `new tests/test_m3_no_secrets.py`. No existing file was edited and no existing test changed. New files have no comments or docstrings (plan 0.5).

Helper files (only in this folder): `hashes.py` (copied from m3-t11), `synthetic.py` (builds the synthetic result and runs the script on it), `synthetic_result.json` and `planted_result.json` (its outputs), `dump_openapi.py` (dumps the schema with `RUNS_DB_PATH` on a temp path and fake keys; it creates no database), `openapi-temp.json`, `secret_scan.py`, `baseline_hashes.json`.

## Requirement mapping

| T12 requirement | Where / result |
|---|---|
| Full backend suite | **2416 passed, 1 warning** (the existing Starlette/httpx deprecation warning). After T11: 2364, plus 52 new |
| `scripts/check_m3_contracts.py` checks saved JSON against the rules, offline | The script loads the file as `PipelineResult`, rebuilds each stage's digest from the saved result (SWOT: idea, constraints, market, competitors; MVP adds SWOT; GTM adds SWOT and MVP; untrimmed), and checks every rule below. It makes no API call and opens no database |
| OpenAPI regenerates | `create_app().openapi()` dumped to a temp file: 11 paths, 16 operations, 79 schema components |
| `npm run api:types` succeeds and the frontend still type-checks | Equivalent command on the dumped file (as T1 and T8 did, per the brief): `npx openapi-typescript <temp file> -o src/api/types.gen.ts` succeeded; `npm run typecheck` clean |
| Secret scan | 506 tracked and untracked non-ignored files listed, 411 text files scanned, 95 binary skipped: **0 hits** |
| Route table and settings | Below |
| Test: planted fake keys never leave the process | 11 tests in `tests/test_m3_no_secrets.py` |
| Test: contract script passes on a synthetic result and flags planted violations | 41 tests in `tests/test_m3_no_secrets.py` |

### Rules the contract script checks

Each violation is printed as `where: rule: detail`. The detail never repeats item text; a ref that is not ref-shaped is printed as "a malformed ref", and a secret is printed only by its label.

| Rule code | Plan source | Check |
|---|---|---|
| `schema` | 6.1 to 6.4, X-8 | The file validates as `PipelineResult` (this enforces enums, length limits, list maxima, and that no strategy basis is `sourced`). Only the field path and error type are printed |
| `unreadable` | n/a | The file is not JSON |
| `ref_unknown` | 7.5 #1, X-8 | Every `based_on` ref is a fact of the digest the stage could see |
| `basis_inconsistent` | 7.5 #2, #3; 8.5 #6 | Basis equals `adjusted_basis(basis, valid refs)`: no refs means `assumption`; `user_provided` needs an `IDEA.*` or `CON.*` ref; success metrics are assumptions |
| `sources_mismatch` | 5.3, X-8 | `sources` equal the sources inherited from the cited facts |
| `figure_unsupported` | 7.5 #4, 8.5 #6, 9.7 #5, X-9 | No currency, percentage or million/billion figure that the cited facts (items) or the stage's facts (summaries, limitations, metrics, phases, messages) do not contain |
| `overclaim` | 7.5 #5, X-9 | No phrase from `OVERCLAIM_PHRASES` |
| `duplicate` | 7.5 #6, 9.5 #5 | No near-duplicate (token overlap 0.8) inside a quadrant, the risks, features, metrics, channels (by name), tactics or key messages |
| `secret` | 7.5 #10, X-6 | `secret_findings` over `swot`, `mvp`, `gtm` and `constraints` (configured key values and key-shaped text) |
| `id_repeated` | 6.2 to 6.4 | SWOT, risk, feature and channel ids are unique |
| `count` | 7.5 #9, 8.5 #5, 9.4, 9.5 #5 | At least 4 SWOT items and 1 risk; at least 3 features; at least 3 channels; at least 2 launch phases |
| `shortfall_unexplained` | 7.7 #1, 9.4 | Fewer items than the target (quadrant 3, risks 6, features 4, metrics 2, tactics 3, actions 2, messages 2, all three phases) only with the agent's warning |
| `severity`, `risk_order` | 7.4 | Severity is `likelihood × impact` per the matrix; risks sorted by severity, impact, likelihood |
| `coverage` | 6.2, 7.4 | `risk_category_coverage` and `coverage_gaps` match the risks |
| `score`, `rank` | 8.4, 8.7 #1 | Score recomputed from the stored ratings; features ranked essential first, then score, then lower effort |
| `capacity`, `tier`, `deferred_reasons` | 8.4 | Capacity from `constraints_used`; tiers, planned person-months and `over_capacity` recomputed with `assign_tiers`; one deferred reason per later feature |
| `founder_feature_missing`, `origin` | 8.5 #1, #2 | Every founder key feature appears; `founder_listed` matches a founder feature |
| `risk_link`, `feature_link` | 8.5 #3, 9.5 #2 | `mitigates_risk_ids` and `addresses_risk_ids` are SWOT risk ids; `uses_feature_ids` are MVP feature ids |
| `statement`, `segment`, `differentiator_status` | 9.4, 9.5 #3, 9.6, 9.7 #1, #4 | The statement is assembled from its parts; the target segment is the priority segment (or a segment, or a founder customer) and the audience names it; positioning on founder customers is an assumption; a gap-based differentiator is a hypothesis |
| `channel_rank`, `budget_conflict` | 9.4, 9.5 #4 | Channels sorted by audience fit, cost, speed; priorities 1..n; only the first is `start_here`; `budget_conflict` set exactly for high cost on a bootstrapped budget |
| `launch_phases` | 9.4 | Phases unique and in order |

### Contract script output on the synthetic result

The synthetic result is the existing fake pipeline result (`tests.m3_fakes.full_result`) with the three real agents fed the existing fake drafts (`tests.test_m3_*_agent.draft`) and `tests.m3_fakes.CONSTRAINTS`. It is built by `synthetic.py` and saved as `synthetic_result.json`.

```
.agents\tasks\m3-t12\synthetic_result.json: checked swot, mvp, gtm; no violations
All 1 file(s) pass.
exit code 0
```

The same result with four planted problems (`planted_result.json`: an unknown ref, a wrong severity, a wrong score, an overclaim in the GTM summary):

```
.agents\tasks\m3-t12\planted_result.json: checked swot, mvp, gtm; 6 violation(s)
  - swot.strengths[0] SW1: ref_unknown: cites MKT.999, which is not a finding of this result
  - swot.risks[0] R1: severity: severity low should be high
  - swot.risks: risk_order: not sorted by severity, then impact, then likelihood
  - mvp.features[0] F1: score: score 1 should be 3.8
  - mvp.features: rank: not ranked essential first, then by score, then by lower effort
  - gtm.summary: overclaim: promises an outcome (guaranteed)
1 of 1 file(s) break a rule.
exit 1
```

On the saved Milestone 2 live results (`docs/test_runs_m2/agritech.json`, `fintech_cashflow.json`, `foodtech_surplus.json`) each line reads `checked nothing; not present swot, mvp, gtm; no violations`, exit 0.

## Final route table (from the regenerated OpenAPI schema)

| Method | Path | Body | Success | Documented error codes | Since |
|---|---|---|---|---|---|
| GET | `/health` | none | 200 object | none | M1 |
| GET | `/api/meta` | none | 200 `MetaResponse` (now with `strategy` and `chat` blocks) | 503 | M1/UI, extended T8 |
| POST | `/api/ideas/extract` | `IdeaSubmission` | 200 `ExtractedIdea` | 422 | M1 |
| POST | `/api/search` | `ExtractedIdea` | 200 `SearchBundle` | 422 | M1 |
| POST | `/api/validate` (`include_analysis` query) | `IdeaSubmission` | 200 `PipelineResult` | 422 | M1/M2 |
| GET | `/api/runs` | none | 200 `RunList` (rows gain `has_strategy`) | 503 | UI, extended T8 |
| POST | `/api/runs` | `RunRequest` (optional `include_strategy`, default false, and `constraints`) | 202 `RunStarted` | 409, 422, 503 | UI, extended T8 |
| GET | `/api/runs/{run_id}` | none | 200 `RunDetail` (gains `constraints`; result gains `swot`, `mvp`, `gtm`) | 404, 422, 503 | UI, extended T8 |
| PATCH | `/api/runs/{run_id}` | `RunRename` | 200 `RunSummary` | 404, 422, 503 | UI |
| DELETE | `/api/runs/{run_id}` | none | 204 (also deletes the chat thread) | 404, 409, 422, 503 | UI, extended T2 |
| POST | `/api/runs/{run_id}/cancel` | none | 200 `RunDetail` | 404, 422, 503 | UI |
| GET | `/api/runs/{run_id}/report.md` | none | 200 text (strategy sections on the `full=True` path) | 404, 409, 422, 503 | UI, extended T9 |
| POST | `/api/runs/{run_id}/strategy` | `StrategyRequest` (`mode` missing/all, `constraints`) | 202 `RunStarted` | 404, 409, 422, 503 | T8 |
| GET | `/api/runs/{run_id}/chat` | none | 200 `ChatThread` | 404, 409, 422, 503 | T11 |
| POST | `/api/runs/{run_id}/chat` | `ChatRequest` | 200 `ChatReply` | 404, 409, 422, 429, 502, 503 | T11 |
| DELETE | `/api/runs/{run_id}/chat` | none | 204 | 404, 409, 422, 503 | T11 |

This matches Section 12.1 and 12.2. FastAPI lists a default 422 on routes with a path parameter even when there is no body (recorded in T11).

## Settings (config.py; `.env.example` carries the names and defaults)

| Setting | Default | Bounds | Added |
|---|---|---|---|
| `TAVILY_API_KEY`, `LLM_API_KEY`, `LLM_MODEL`, `GROQ_API_KEY` | none | n/a | M1/M2 (secrets, never printed) |
| `BACKEND_URL` | `http://localhost:8000` | n/a | M1 |
| `LLM_TIMEOUT_S`, `SEARCH_TIMEOUT_S` | 30 | existing | M1 |
| `COMPETITOR_MAX_EXTRA_QUERIES` | 5 | existing | M2 |
| `COMPETITOR_RESULTS_PER_QUERY` | 3 | existing | M2 |
| `EVIDENCE_MAX_ITEMS` | 12 | existing | M2 |
| `PIPELINE_TIMEOUT_S` | 180 | existing | M2 |
| `CORS_ORIGINS` | `http://localhost:5173`, `http://127.0.0.1:5173` | n/a | UI |
| `PIPELINE_TIME_LIMIT_S` | none (optional) | existing | UI |
| `RUNS_DB_PATH` | `data/runs.db` | n/a | UI |
| `STRATEGY_TIME_LIMIT_S` | 150 | 30 to 900 | M3 |
| `STRATEGY_DIGEST_MAX_CHARS` | 24000 | 4000 to 100000 | M3 |
| `CHAT_MAX_USER_TURNS` | 25 | 1 to 100 | M3 |
| `CHAT_MAX_MESSAGE_CHARS` | 1000 | 100 to 4000 | M3 |
| `CHAT_HISTORY_TURNS` | 6 | 1 to 20 | M3 |
| `CHAT_CONTEXT_MAX_CHARS` | 30000 | 4000 to 120000 | M3 |
| `CHAT_MAX_CONCURRENT` | 2 | 1 to 8 | M3 |
| `CHAT_COOLDOWN_S` | 2 | 0 to 60 | M3 |

The eight M3 settings match Section 12.6.

## Tests (`tests/test_m3_no_secrets.py`, 52 tests)

Planted keys (11). The three configured keys are set to fake values joined from parts; a key-shaped Groq value is also joined from parts. The app uses the real `default_manager()` wiring with `RUNS_DB_PATH` on a temp file (the test asserts the store path before any run starts). "Nowhere" means: the run detail, the run list, `report.md`, `/api/meta`, every response the test received, every file `runs.db*` in the temp folder, and the captured logs at DEBUG.

- `test_the_store_redacts_every_configured_key`: the store built by `default_manager()` holds all three configured values.
- `test_configured_keys_never_reach_a_prompt_a_response_a_row_or_a_log`: a seven-stage run, one Advisor question, the thread read and a `mode=all` strategy job. No configured key in any prompt sent to the (fake) extraction, market, competitor, SWOT, MVP, GTM or Advisor model, nor anywhere listed above.
- `test_a_key_in_a_strategy_reply_fails_only_that_stage_and_goes_nowhere` (6: SWOT, MVP, GTM × configured value, key-shaped text): the stage fails with `internal_error`, the run is `partial`, the other two strategy results exist, and the key is nowhere.
- `test_a_key_in_a_strategy_reply_for_a_saved_run_goes_nowhere`: the same through `POST /api/runs/{id}/strategy` (`mode=missing`).
- `test_a_provider_error_that_quotes_the_keys_is_neither_logged_nor_returned`: the real `llm_client` path with a fake Gemini 400 whose message contains all three keys; the "LLM call failed" line is logged, and no key is anywhere.
- `test_a_key_typed_into_a_question_stays_out_of_the_rows_the_logs_and_the_saved_thread`: the saved thread shows `[redacted]`.

Contract script (41):

- `test_the_contract_script_passes_on_the_synthetic_result`: `check_result(...) == []`, exit 0, exact output.
- `test_saved_milestone_2_results_have_no_strategy_to_break`: the three saved M2 live results, exit 0, exact output.
- `test_the_contract_script_flags_a_planted_violation` (36 cases): every rule code above except `schema`, `unreadable` and `secret` has at least one planted case. Some rules have more than one: `basis_inconsistent` 3, `coverage` 2, `count` 2, `shortfall_unexplained` 2, `capacity` 2, `channel_rank` 2, `overclaim` 2, `figure_unsupported` 2. Each case asserts the rule is reported, the exit code is 1 and the summary line.
- `test_the_contract_script_flags_secrets_without_printing_them`: a configured key and key-shaped text are flagged by label; a malformed ref is shown as "a malformed ref"; no planted value appears in the output.
- `test_a_strategy_item_labelled_sourced_fails_the_schema` (X-8).
- `test_a_file_that_is_not_json_is_reported`.

All tests use fakes. The network block and fake environment from `tests/conftest.py` apply. No provider credits were used.

## Plan-vs-code points and open items (recorded, not changed)

1. **Test file for the contract script.** T12 names only two new files, so the contract-script tests are in `tests/test_m3_no_secrets.py` together with the planted-key tests. No separate test file was added.
2. **`npm run api:types`.** The script fetches `http://127.0.0.1:8000/openapi.json` from a running server. The brief says not to start the backend against `data/runs.db`, so the same generator (`openapi-typescript`, the version the script uses) was run on a file dumped by `create_app().openapi()`. The command itself was not run against a live server.
3. **The Advisor reply has no secret scan.** Section 10.5 lists no secret check for replies; 7.5 #10 covers only the strategy stages. If the model echoed a key (for example one the founder typed into a question), the row would be redacted by the store, but the immediate `POST /api/runs/{id}/chat` response would return it as written. Closing this would change T10/T11 behaviour and is outside T12's files. The tests above do not assert that case.
4. **Founder text goes to the model as typed.** A key typed into a question or into `launch_region` is in the prompt the model receives. This is the same as for the idea text in M1/M2 (privacy note 15.5). It is redacted in rows and in responses read back from the store. A key in `launch_region` also makes the MVP stage fail its secret scan, because `constraints_used` carries the region (7.5 #10). This is existing behaviour and not pinned by a new test.
5. **The script reads settings.** `check_m3_contracts.py` imports `config`, which loads the project `.env` as every entry point does. It uses the configured key values only to compare them, and it prints only labels. The run on the saved M2 results above used that path. The synthetic and planted runs used fake key values set in the process environment.

## Commands run and results

| Command | Result |
|---|---|
| `python .agents\tasks\m3-t12\hashes.py save` | 47 uncommitted files hashed |
| `Get-FileHash data\runs.db`; `Get-Item data\runs.db` (start) | 00A4F859…8337D, 311296 bytes, 2026-11-08T15:31:17Z |
| `python .agents\tasks\m3-t12\synthetic.py` (first run) | Synthetic result `complete`; script: no violations, exit 0 |
| `pytest tests/test_m3_no_secrets.py` | 52 passed, 1 warning |
| `python .agents\tasks\m3-t12\dump_openapi.py` | 11 paths, 79 schemas; no database file or folder created |
| `npx openapi-typescript ..\.agents\tasks\m3-t12\openapi-temp.json -o src/api/types.gen.ts` (in web/) | openapi-typescript 7.13.0, written; SHA-256 CA3902DF…A04F6 → A03D7C42…CF7C9 |
| `npm run typecheck` (in web/) | Clean (both `tsc --noEmit` passes) |
| `python -B -m pytest -q -p no:cacheprovider -rfE` (full backend) | 2416 passed, 1 warning |
| `python .agents\tasks\m3-t12\secret_scan.py` | 506 listed, 411 scanned, 95 binary skipped, 0 excluded by name (`.env` and `*.db` are git-ignored so not listed), **total hits 0** |
| `python scripts\check_m3_contracts.py docs\test_runs_m2\{agritech,fintech_cashflow,foodtech_surplus}.json` | 3 files pass, exit 0 |
| `python scripts\check_m3_contracts.py .agents\tasks\m3-t12\planted_result.json` (fake keys in env) | 6 violations, exit 1 (output above). An earlier attempt lost the apostrophe in "can't" to shell quoting, so its summary was not an overclaim; the rerun used "guaranteed" |
| Line-wrap edits to two long lines in the script, then: full backend suite again | **2416 passed, 1 warning** (57.5 s) |
| `pytest tests/test_m3_no_secrets.py` again | **52 passed**, 1 warning |
| `python .agents\tasks\m3-t12\synthetic.py` again | no violations, exit 0 |
| `python .agents\tasks\m3-t12\hashes.py check` (end) | `new scripts/check_m3_contracts.py`, `new tests/test_m3_no_secrets.py` only |
| `Get-FileHash data\runs.db`; `Get-Item data\runs.db` (end) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes, 2026-11-08T15:31:17Z (unchanged) |
| `git branch --show-current`; `git rev-parse --short HEAD`; `git status --porcelain` | `main`, `a098aef`, 50 entries: the 47 files hashed at the start, the two new files, and the untracked `.agents/` folder |

No backend was started. Nothing was committed, pushed, reset, reverted or stashed. No branch was created or switched. No `.env` file and no `data/runs.db` content was opened by me.

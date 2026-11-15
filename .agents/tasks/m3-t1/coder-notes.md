# M3 T1 coder notes

## data/runs.db baseline (recorded before first edit, read-only)
- SHA-256: 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D
- Size: 311296 bytes
- LastWriteTimeUtc: 2026-11-08T15:31:17.0443165Z

## Iteration 1 (no review.json existed; first implementation)

### Files changed / created
| File | Purpose |
|---|---|
| `config.py` (modified) | 8 new `Settings` fields with plan defaults; `DEFAULT_*` and `*_RANGE` constants; `_bounded_int_env` / `_bounded_float_env` readers (same warn-and-fall-back pattern as `_int_env` / `_float_env`, plus inclusive upper/lower bounds) |
| `.env.example` (modified) | The 8 new names, commented out with their defaults and ranges, no secrets (same style as the UI-upgrade block) |
| `utils/errors.py` (modified) | 8 `AppError` subclasses for the 12.4 codes; `ChatMessageInvalidError(max_chars)` formats "{n}" |
| `models/schemas.py` (modified) | Section 6 stored models appended after `PipelineResult`; `PipelineResult` gains optional `swot`, `mvp`, `gtm`, `constraints` (default None, forward refs + `PipelineResult.model_rebuild()`) |
| `models/api.py` (modified) | `RunRequest` gains `include_strategy: bool = False` and `constraints: StrategyConstraints | None = None` (extra="forbid" kept); new `StrategyRequest` (`mode` missing/all, default missing; `constraints`) |
| `models/strategy_drafts.py` (new) | LLM-facing drafts `SwotRiskDraft`, `MvpDraft`, `GtmDraft`, `AdvisorDraft` and their item drafts; `STRATEGY_DRAFT_MODELS` |
| `models/chat.py` (new) | `ChatParagraph`, `ChatMessage`, `ChatRequest`, `ChatLimits`, `ChatThread`, `ChatReply` |
| `tests/test_m3_schemas.py` (new) | 124 tests: settings defaults/bounds, `.env.example`, errors, constraints, request models, stored-model limits, drafts vs Groq strict filter, chat models, fixture and stored-run compatibility, OpenAPI, import cycle |
| `.agents/tasks/m3-t1/coder-notes.md` (new, workflow bookkeeping) | This file. `.agents/` is not git-ignored, so it shows as `?? .agents/` |

No other file changed. `web/src/api/types.gen.ts` was regenerated (git-ignored, does not show in status).

### How each T1 requirement was met
- **Settings and bounds (12.6):** `STRATEGY_TIME_LIMIT_S`=150 (30-900), `STRATEGY_DIGEST_MAX_CHARS`=24000 (4000-100000), `CHAT_MAX_USER_TURNS`=25 (1-100), `CHAT_MAX_MESSAGE_CHARS`=1000 (100-4000), `CHAT_HISTORY_TURNS`=6 (1-20), `CHAT_CONTEXT_MAX_CHARS`=30000 (4000-120000), `CHAT_MAX_CONCURRENT`=2 (1-8), `CHAT_COOLDOWN_S`=2 (0-60). Non-numeric, NaN or out-of-range values log a warning naming the setting and fall back to the default. No code reads these settings yet.
- **Error classes (12.4):** `RunNotFinishedError`, `StrategyNotReadyError`, `StrategyAlreadyCompleteError`, `ChatUnavailableError`, `ChatLimitError` (`chat_limit_reached`), `ChatBusyError`, `ChatCooldownError` (429), `ChatMessageInvalidError` (422). Codes, statuses and messages exactly as in the plan table. Nothing raises them yet.
- **Stored models (Section 6):** `StrategySourceKey`, `StrategyConstraints`, `StrategyQuality`, `SwotItem`, `RiskItem`, `SwotRiskResult`, `MvpFeature`, `MvpMetric`, `MvpResult`, `Positioning`, `Channel`, `EarlyCustomerTactic`, `LaunchPhase`, `KeyMessage`, `GtmResult`. Strategy item basis is restricted to `ai_interpretation`/`assumption`/`user_provided` (D-04, never `sourced`). Length limits and maximum counts from Section 6 / Appendix C are enforced; minimum counts are not (Sections 7.6 and 9.4 say a shortfall is a warning, not a failure).
- **Draft models:** strict-Groq compatible: `Literal` enums, explicit nullable `suggested_target`, no `dict`, no `ge`/`le`, no `pattern`. Ratings are unbounded ints (8.5 check 4 clamps in code), risk confidence accepts `high` (capped in code, same as `GAP_CONFIDENCES_DRAFT`). All four pass `groq_client.strict_schema` and `response_format` gives `json_schema`.
- **Chat models:** per 10.5 / 12.2. `ChatRequest` strips control characters (keeps newline and tab), trims, rejects empty, and enforces `CHAT_MAX_MESSAGE_CHARS` read from settings at validation time; unknown fields rejected.
- **Request-model additions:** `RunRequest.include_strategy` / `constraints` and `StrategyRequest`. `routes/run_routes.py` still passes only `submission` and `idea_override`, so the new fields have no effect (no behaviour change). Response models (`RunSummary.has_strategy`, `RunDetail.constraints`, meta blocks) are not changed: those are T8.
- **All new `PipelineResult` fields optional:** default None; tested.
- **Integration:** import graph is `config` <- `utils.errors`; `models.schemas` <- `models.strategy_drafts` <- `models.chat` (which also imports `config`); `models.api` <- `models.schemas`. No cycle (tested by importing each module first in a fresh interpreter). OpenAPI generates.

### Verification (iteration 1)
1. Backend: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE` -> **1760 passed, 1 warning** (baseline 1636 + 124 new; the warning is the existing Starlette/httpx deprecation). New file alone: 124 passed.
2. OpenAPI: `.\.venv\Scripts\python.exe -B -c "from app import app; s=app.openapi(); ..."` -> ok, 9 paths; `RunRequest` properties `constraints, idea_override, include_strategy, submission`, required `['submission']`.
3. Frontend: OpenAPI dumped to a temp file (deleted afterwards) and `npx openapi-typescript <file> -o src/api/types.gen.ts` (same tool as the `api:types` script, file input instead of a running server) -> generated. `npm run typecheck` -> clean (exit 0). `npm test` -> **20 files, 295 passed**. Playwright not run.
4. Import cycle: `.\.venv\Scripts\python.exe -B -c "import models.schemas, models.api, models.chat, models.strategy_drafts, config, utils.errors"` -> `imports ok`.
5. data/runs.db after all checks: SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17.0443165Z (identical to baseline); read-only count `rows 9`; no -wal/-shm files created. `git status --porcelain`: `M .env.example`, `M config.py`, `M models/api.py`, `M models/schemas.py`, `M utils/errors.py`, `?? .agents/` (bookkeeping), `?? models/chat.py`, `?? models/strategy_drafts.py`, `?? tests/test_m3_schemas.py`.
6. Secret scan (grep over the 8 changed/new files) for `AIza[0-9A-Za-z_-]{10,}|gsk_[A-Za-z0-9]{10,}|tvly-[A-Za-z0-9]{6,}|sk-[A-Za-z0-9]{10,}|Bearer [A-Za-z0-9._-]{8,}|PRIVATE KEY` -> **0 hits**. A bare-prefix scan only matches the regex source of `SECRET_PATTERN` in `tests/test_m3_schemas.py` (same pattern style as `tests/test_m2_config.py`).

### Stored-runs test
`test_every_result_in_a_copy_of_the_stored_runs_validates_unchanged` opens `data/runs.db` with `file:...?mode=ro` (uri=True), copies it into `tmp_path` with the sqlite3 backup API, validates every non-null `result_json` (8 of the 9 rows have one) against `PipelineResult`, checks the dump equals the stored JSON on every stored key and the four new fields are null, and asserts the source file's SHA-256, size and mtime are unchanged. It skips when the file is absent.

### Plan <-> code conflicts and decisions
- **Comments/docstrings:** plan Section 0.5 says new code has no comments or docstrings. New files (`models/chat.py`, `models/strategy_drafts.py`, `tests/test_m3_schemas.py`) have none. In the existing files I followed their convention (section-divider comments, short field comments, one docstring on `StrategyRequest`).
- **"Appended to schemas.py":** done literally; `PipelineResult` uses string forward references and `PipelineResult.model_rebuild()` at the end of the file.
- **`.env.example` style:** the new names are commented out (`# NAME=default`) like the UI-upgrade block, not uncommented like the M2 block, so copying the file never changes behaviour.
- **`budget_conflict` on `Channel`:** not in the 6.4 field table but required by 9.5 check 4; added as `bool = False`.
- **Draft `effort`:** kept as `Literal["S","M","L"]` (Section 6.6.2 asks for Literal enums); 8.5 check 4's "effort outside S, M, L" default therefore cannot be reached through the draft. Ratings stay unbounded so their clamp can.
- **`ChatRequest` validation errors:** a too-long or empty message fails Pydantic validation, which the app maps to the generic `invalid_input` 422. Mapping it to `chat_message_invalid` belongs to the chat route (T11).
- **`utils/errors.py` now imports `DEFAULT_CHAT_MAX_MESSAGE_CHARS` from `config`** to format the default message; `config` has no project imports, so no cycle.
- Response-model additions (`has_strategy`, `RunDetail.constraints`, meta `strategy`/`chat`) were deliberately left to T8, so that T1 changes no response. Known T0 conflicts (Gemini max_output_tokens, Groq 4096 tokens, store migration, stage labels) are untouched: none of them has a 12.6 setting.

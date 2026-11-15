# M3 T1 review (pass 1)

Verdict: APPROVED. No blockers.

## Evidence checked
- `git status --porcelain`: modified `.env.example`, `config.py`, `models/api.py`, `models/schemas.py`, `utils/errors.py`; untracked `models/chat.py`, `models/strategy_drafts.py`, `tests/test_m3_schemas.py`, plus `.agents/` (bookkeeping). No other file is touched. The plan file, KIRO_*.md and docs/assets/ui_v2 are not in the status. `web/src/api/types.gen.ts` is git-ignored (`.gitignore:31`), so its regeneration does not show.
- Read the full diff and all three new files against plan sections 4, 6.1-6.6, 10.5, 11.1, 12.1-12.4, 12.6, 15.2, 17.2, 20.1-20.4, Appendices A.1-A.5, B and C, and the T1 entry (lines 1105-1115).
- Settings (12.6): the 8 names have the plan defaults. `_bounded_int_env` / `_bounded_float_env` (config.py) follow the `_int_env` / `_float_env` warn-and-fall-back pattern with inclusive bounds. NaN and inf fall back because the range comparison fails. The new `Settings` fields have defaults and come after the existing ones, so existing constructors are unaffected. Nothing reads them yet.
- Errors (12.4): the 8 codes, statuses and messages match the table word for word. `ChatMessageInvalidError` formats `{n}`. The new `utils.errors -> config` import adds no cycle, because `config` has no project imports.
- Stored models (Section 6): field names, enums, length limits and maximum counts match 6.1-6.4 and Appendix C. Strategy basis excludes `sourced` (D-04). `StrategyConstraints` forbids extra fields and strips control characters from `launch_region` (12.3, 15.2). The four new `PipelineResult` fields are optional with a `None` default (4.2, 6.5), and `model_rebuild()` resolves the forward references.
- Drafts: field names follow Appendix A.1-A.4 and B.1/B.3 (`mitigates`, `uses_features`, `addresses_risks`, `refs`). They use no `ge`/`le`/pattern/dict, so they satisfy 6.6.2/6.6.3. A test runs each draft through `groq_client.strict_schema` against `STRICT_KEYWORDS`.
- Chat models: these match 10.5 and 12.2/12.3. `ChatRequest` trims, strips control characters, rejects empty input, applies the `CHAT_MAX_MESSAGE_CHARS` limit at validation time and forbids extra fields.
- Requests: `RunRequest` gains `include_strategy=False` and `constraints=None`, and `extra="forbid"` is kept. `routes/run_routes.py` is unchanged, so nothing acts on the new fields. `StrategyRequest` defaults `mode` to `missing`. Response-model additions (`has_strategy`, meta blocks) are left to T8, which the brief allows ("no behaviour change").
- Callers checked: `agents/derived.labeled_bases` walks only the market and competitor results, not `PipelineResult`, so the new null fields do not change any derived value. The pinned shape tests in `test_runs_api.py` (lines 71, 81 and 85) assert run-start keys, stage keys/labels and `PipelineResult` validation, and they are unchanged.
- Tests: `tests/test_m3_schemas.py` covers model limits, default-null fields, every fixture (`docs/test_runs*/*.json`, `liveAgritech.json`, `liveFintech.json`), the OpenAPI schema, settings bounds and import cycles. The stored-runs test opens `file:...?mode=ro` with `uri=True`, copies the database with `backup()` into `tmp_path`, skips when the file is absent, and asserts the source fingerprint is unchanged. No existing test was edited.
- Coder verification record: backend 1760 passed (1636 + 124 new), 0 failures. `app.openapi()` succeeds and shows the new `RunRequest` properties. Types were regenerated, `npm run typecheck` is clean, and `npm test` reports 295 passed in 20 files. The import one-liner succeeds. The runs.db hash, size and mtime are unchanged and the table has 9 rows. The secret scan found 0 hits. All required checks are recorded.
- Spot-check (read-only): data/runs.db SHA-256 `00A4F859...8337D`, 311296 bytes, LastWriteTimeUtc `2026-11-08T15:31:17.0443165Z`. These match the baseline, and no -wal/-shm file exists.

## Recorded decisions accepted (not blockers)
- Minimum counts are not enforced on the stored models, because 7.6/9.4 treat a shortfall as a warning.
- `Channel.budget_conflict` was added for 9.5 check 4.
- `.env.example` entries are commented out, matching the UI-upgrade block.
- Mapping `chat_message_invalid` to the route belongs to T11.

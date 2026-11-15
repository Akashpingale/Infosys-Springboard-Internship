# M3 T5 review (SWOT and risk agent, R1)

Verdict: APPROVED. No blockers.

## Evidence checked
- `orchestrator.py` vs `.agents/tasks/m3-t5/baseline/orchestrator.py` (baseline copy hash matches baseline.md 7695…1061): +1 import of `SwotRiskAgent`, `STRATEGY_ONLY_STAGES[0]` now `StrategyStage(SwotRiskAgent(), STRATEGY_TITLES[STAGE_SWOT])`, `PendingStrategyAgent` docstring "T5 to T7" -> "T6 and T7". MVP and GTM keep `PendingStrategyAgent`. Registration only.
- `agents/swot_risk_agent.py` against plan 7.2-7.6, A.0, A.1, A.5, Appendix C:
  - `build_prompt(digest) -> (system, user)`; system = A.0 rules verbatim + A.1 role; user carries `digest.text` (inside `<facts>`/`</facts>`) then the A.1 task text, length hints and a JSON shape (Gemini gets no schema, as in M2).
  - One LLM call via `call_structured(..., SwotRiskDraft, caller=generate_json)`, same pattern as the M2 agents. No searches.
  - Severity: low 1/medium 2/high 3, score >= 6 high, >= 3 medium, else low (matches 7.4 and Appendix C). Sort by severity, impact, likelihood descending, then cut to 10, then ids `R1..` so `RSK.n` == `R{n}` (A.5).
  - Checks 1-8 reuse T3 `check_items`, `cut_to_limit`, `shorten_fields`; check 9 raises `LLMInvalidResponseError` (`llm_invalid_response`; plan names an `llm_invalid_output`-class code, conflict recorded); check 10 `ensure_no_secrets` on the final result (warnings included, so model-supplied ref strings are scanned too).
  - Confidence `high` capped to `medium` with one warning; items with an empty required field dropped with one warning (prevents a `NonEmptyStr` validation error failing the stage); shortfall below 3/quadrant or 6 risks succeeds with a warning (7.6).
  - Coverage map lists all five categories; `coverage_gaps` are the zero ones. Quality inputs over idea/market/competitors; constraints via `apply_constraint_defaults`.
  - Agent-level guard: `StrategyNotReadyError` before any digest or LLM call when idea or both analyses are missing; the stage's `skip_reason` skips first in a pipeline. Decision recorded.
  - Warnings go into `context.warnings` with the stage label prefix, so `_seeded` drops them on a strategy-only re-run and notices map them to `STAGE_SWOT`.
  - Schema fit verified: `SwotItem.text`, `RiskItem` title/description/mitigation/early_warning_signal are `NonEmptyStr` with max lengths; `_complete` + `shorten` keep values within them. `SwotRiskResult.summary` defaults to "" so a blanked summary validates.
- `tests/test_m3_swot_agent.py` covers every T5 test item: fake reply -> expected result; nine-pair severity matrix plus stored/sorted order; coverage and gaps; planted offenders for checks 1-10; minimum-content failure (direct and after checks); shortfall warning; sufficiency (direct guard, no model call; pipeline skip); provider failure, invalid-after-retry and too-little content each leave idea/search/market/competitors, run `partial`, MVP/GTM still run without SWOT; prompt rules, digest and delimiters (incl. a `</facts>` injection attempt); seven-stage run stores `swot`, JSON round-trip, and digest with that swot yields `RSK.1..RSK.6` matching `R1..R6` with inherited sources. Section-divider comments match existing M2/T4 test files.
- Existing test edit: `tests/test_m3_orchestrator.py::test_without_a_registered_agent_a_strategy_stage_fails_plainly` gained one `monkeypatch.setattr(STRATEGY_ONLY_STAGES[0], "agent", orchestrator.PendingStrategyAgent(STAGE_SWOT))` line. Coder stopped and asked; coder-notes record parent approval (option A). Verified exactly one line: removing it reproduces the baseline hash F95BE5A2…AB1C. Assertions unchanged; the test still proves the pending mechanism for all three stages.

## Coder's verification record (not re-run)
1. T5 tests: 48 passed. 2. T3/T4 regression: 160 passed. 3. Full suite: 1980 passed (1932 + 48), 0 failed, 1 warning. 4. Seven-stage run test present and passing. 5. FULL_STAGES-equivalence and M2 pin test inside 2/3.

## Spot-checks run (read-only)
- Hashes vs baseline.md: only `orchestrator.py` and `tests/test_m3_orchestrator.py` differ (both justified above).
- `data/runs.db`: SHA-256 00A4F859…337D, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17Z, unchanged.
- `git status --porcelain`: baseline set plus `?? agents/swot_risk_agent.py`, `?? tests/test_m3_swot_agent.py`. Nothing in routes/, frontend/, web/, docs/, plan.
- Secret-pattern grep over the four touched files: 0 hits (planted test keys built from parts).

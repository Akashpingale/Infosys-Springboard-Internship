# M3 T5 coder notes

## Iteration 1 (no review.json existed; first implementation)

### Files
- `agents/swot_risk_agent.py` (new): prompt (`SHARED_RULES` = A.0, `ROLE`, `build_prompt(digest) -> (system, user)`),
  `severity`, `build_result` (draft to `SwotRiskResult`), `analyse_swot`, `SwotRiskAgent` (name `swot_risk`).
- `tests/test_m3_swot_agent.py` (new): 48 tests.
- `orchestrator.py` (modified): import `SwotRiskAgent`; `STRATEGY_ONLY_STAGES[0]` now
  `StrategyStage(SwotRiskAgent(), STRATEGY_TITLES[STAGE_SWOT])`; `PendingStrategyAgent` docstring "T5 to T7" -> "T6 and T7".
  MVP and GTM keep `PendingStrategyAgent`.
- Helper (bookkeeping only): `.agents/tasks/m3-t5/probe_digest.py` printed the digest of the fake pipeline result to pick refs.

### Blocker found: existing T4 test conflicts with registration
`tests/test_m3_orchestrator.py::test_without_a_registered_agent_a_strategy_stage_fails_plainly` runs the real
`STRATEGY_STAGES` without fakes and asserts all three strategy stages fail with `MSG_STRATEGY_PENDING`. With the real
SWOT agent registered, stage 5 now calls the LLM (the conftest network block makes it fail with `llm_api_error`), so the
test fails. Full suite at this point: 1979 passed, 1 failed (exactly this test), 1 warning. Per the brief I stopped
and asked before editing it.

### Decisions
- Agent-level sufficiency guard: `analyse_swot` raises `StrategyNotReadyError` (existing 12.4 class, plain message
  "There is no market or competitor analysis to build a strategy on.") before building the digest or calling the model
  when the idea is missing or both analyses are missing. In a pipeline the stage's `skip_reason` skips first, so this
  only matters for direct calls; it never spends an LLM call.
- Severity: low 1, medium 2, high 3; score >= 6 high, >= 3 medium, else low. Sort by severity, impact, likelihood (all
  descending, stable). Ids `R1..` assigned after sort and cut so `RSK.n` == `R{n}` (A.5).
- SWOT ids `SW1..` numbered across the four quadrants in order (A.5 gives one `SW{n}` series).
- Checks: SWOT quadrants via `check_items(maximum=5, lengths=...)`; risks via `check_items` (1-6), then sort, then
  `cut_to_limit(10)`, then `shorten_fields` (check 7 note in T3). Check 9: fewer than 4 SWOT items or 0 risks after
  checks -> `LLMInvalidResponseError` with a plain message (code `llm_invalid_response`). Check 10: `ensure_no_secrets`
  on the final result (base `AppError`, as T3 decided).
- Extra repairs, each one aggregated warning: confidence `high` capped to `medium` (as M2 gap confidence);
  items with an empty required field dropped (would otherwise fail `NonEmptyStr` and the whole stage);
  shortfall below 3 per quadrant or 6 risks (7.6: succeed with a warning).
- Summary and limitations: overclaim and unsupported figure (checked against all digest facts, since they cite none)
  blank the summary / drop the limitation; limitations cut to 4 (A.1) and shortened to 200 characters (no limit in
  the plan or schema; chosen to match the other short-text limits). Summary shortened to 400.
- Coverage map lists all five categories with counts, including 0; `coverage_gaps` are the 0 ones, in category order.
- Quality: inputs_used/missing over idea, market, competitors (stage 5 reads no strategy stage); constraints via
  `apply_constraint_defaults`; basis_counts omit zero counts; grounded_share rounded to 3 places.
- Warnings: `SwotRiskResult.warnings` hold the plain strings; `context.warnings` gets them prefixed with the stage label
  "Assessing strengths and risks: " so `notices.WARNING_LABELS` maps them and `_seeded` drops them on a re-run.
- Digest over its cap (only if protected facts alone exceed it): logged and used as is (T3 note 8 left this to T5).
- Gemini receives no response schema, so the user prompt ends with a JSON shape and length hints, as the M2 prompts do.

### Plan-vs-code conflicts
- 7.3 step 1 "return a skipped outcome": skipping is the stage's job (`StrategyStage.skip_reason`, T4); the agent raises
  `StrategyNotReadyError` when called directly.
- 7.5 check 9 names an "`llm_invalid_output`-class code"; the existing code is `llm_invalid_response`.

### Resolution of the blocker (parent answer: option A, monkeypatch variant)
`tests/test_m3_orchestrator.py::test_without_a_registered_agent_a_strategy_stage_fails_plainly` got one added line;
every assertion is unchanged. Approved exception to the T1-T4 hash check.

Before:
```python
def test_without_a_registered_agent_a_strategy_stage_fails_plainly(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    result, _ = strategy_run()
```
After:
```python
def test_without_a_registered_agent_a_strategy_stage_fails_plainly(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[0], "agent", orchestrator.PendingStrategyAgent(STAGE_SWOT))
    result, _ = strategy_run()
```
Why: stage 5 now holds the real agent, which calls the LLM; for this test only the SWOT stage gets the placeholder
back (monkeypatch restores the real agent afterwards), so the test still proves all three unregistered stages fail
with MSG_STRATEGY_PENDING. No other existing test depended on the SWOT placeholder (full suite green).

### Verification (iteration 1, final)
1. `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_swot_agent.py` -> 48 passed, 1 warning.
2. `... tests/test_m3_orchestrator.py tests/test_m3_digest.py tests/test_m3_checks.py tests/test_m3_strict_schema.py`
   -> 160 passed, 1 warning.
3. Full suite `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE` -> 1980 passed, 0 failed,
   1 warning (Starlette/httpx deprecation). 1932 baseline + 48 new.
4. `test_a_seven_stage_run_stores_the_swot_and_its_risks_join_the_digest`: fake SWOT reply, T4 placeholders for
   MVP/GTM; run partial with the two placeholder errors; `PipelineResult.swot` stored and round-trips through JSON;
   digest with that swot has RSK.1..RSK.6 matching R1..R6 with inherited sources; digest without it has none.
5. T4 FULL_STAGES-equivalence tests and the M2 provider-request pin test (`test_an_existing_call_sends_the_same_requests_as_before`)
   pass inside items 2 and 3.
6. `final_checks.ps1`: data/runs.db SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D,
   311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17Z (unchanged). Hash mismatches vs baseline.md: exactly
   `orchestrator.py` (registration) and `tests/test_m3_orchestrator.py` (approved one-line edit).
7. `git status --porcelain`: the baseline set plus `?? agents/swot_risk_agent.py`, `?? tests/test_m3_swot_agent.py`
   (orchestrator.py and tests/test_m3_orchestrator.py were already listed). Branch main; nothing committed.
8. Secret scan of the four changed/new files (AIza, gsk_, tvly-, sk-, Bearer token, PRIVATE KEY): 0 hits. Planted test
   keys are built from string parts.

orchestrator.py diff vs baseline: +1 import of SwotRiskAgent; STRATEGY_ONLY_STAGES[0] uses SwotRiskAgent();
PendingStrategyAgent docstring "T5 to T7" -> "T6 and T7".

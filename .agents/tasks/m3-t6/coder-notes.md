# M3-T6 coder notes

## Iteration 1

No `review.json` existed, so this iteration implements the task.

### Files

| File | State | Purpose |
|---|---|---|
| `agents/mvp_agent.py` | new | Stage 6: A.0 + A.2 prompt, one structured call (`MvpDraft`), shared checks, 8.5 checks, scoring, ranking, capacity fit, `MvpResult`, `MvpAgent` (name `mvp_recommendation`) |
| `tests/test_m3_mvp_agent.py` | new | 60 T6 tests, fake replies only |
| `orchestrator.py` | modified | Registration only: `from agents.mvp_agent import MvpAgent`; stage 6 holds `MvpAgent()`; `PendingStrategyAgent` docstring "plan Tasks T6 and T7" -> "plan Task T7" |
| `tests/test_m3_orchestrator.py` | pre-approved edit | +1 line at line 139 |
| `tests/test_m3_swot_agent.py` | pre-approved edit | +1 line at line 533 (the test already took `monkeypatch`, so no fixture change was needed) |

Registration diff (orchestrator.py, against its T5 state):

```diff
+from agents.mvp_agent import MvpAgent
 from agents.notices import STAGE_GTM, STAGE_MVP, STAGE_SWOT, STRATEGY_TITLES
 from agents.swot_risk_agent import SwotRiskAgent
@@
-    """Stands in for a strategy agent until it is built (plan Tasks T6 and T7). Its stage fails with
+    """Stands in for a strategy agent until it is built (plan Task T7). Its stage fails with
@@
     StrategyStage(SwotRiskAgent(), STRATEGY_TITLES[STAGE_SWOT]),
-    StrategyStage(PendingStrategyAgent(STAGE_MVP), STRATEGY_TITLES[STAGE_MVP]),
+    StrategyStage(MvpAgent(), STRATEGY_TITLES[STAGE_MVP]),
     StrategyStage(PendingStrategyAgent(STAGE_GTM), STRATEGY_TITLES[STAGE_GTM]),
```

### Pre-approved test edits

`tests/test_m3_orchestrator.py::test_without_a_registered_agent_a_strategy_stage_fails_plainly`

Before (lines 138-139):
```python
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[0], "agent", orchestrator.PendingStrategyAgent(STAGE_SWOT))
    result, _ = strategy_run()
```
After (lines 138-140):
```python
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[0], "agent", orchestrator.PendingStrategyAgent(STAGE_SWOT))
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[1], "agent", orchestrator.PendingStrategyAgent(STAGE_MVP))
    result, _ = strategy_run()
```

`tests/test_m3_swot_agent.py::test_a_seven_stage_run_stores_the_swot_and_its_risks_join_the_digest`

Before:
```python
def test_a_seven_stage_run_stores_the_swot_and_its_risks_join_the_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    use_reply(monkeypatch, as_reply(draft()))
```
After:
```python
def test_a_seven_stage_run_stores_the_swot_and_its_risks_join_the_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[1], "agent", orchestrator.PendingStrategyAgent(STAGE_MVP))
    use_reply(monkeypatch, as_reply(draft()))
```

No assertion changed. Hash-restoration proof: `.\.venv\Scripts\python.exe -B .agents\tasks\m3-t6\check_test_edits.py`

```
tests/test_m3_orchestrator.py occurrences of added line: 1
tests/test_m3_orchestrator.py added at line 139
tests/test_m3_orchestrator.py current: 9B9747559EADDBC2629AD132D1A26B7FD389032BF8ACF98DF5A58A45F842A81A
tests/test_m3_orchestrator.py with the added line(s) removed: BEB81D6811E40C0A4D0091230249B27F1796A20CED75D1FD974BF01B8E684A4E
tests/test_m3_orchestrator.py matches baseline: True
tests/test_m3_swot_agent.py occurrences of added line: 1
tests/test_m3_swot_agent.py added at line 533
tests/test_m3_swot_agent.py current: 91EA6C166D3A478F93E55D111743E60AED42B6B93E95A1CD825ED81DC958EBA0
tests/test_m3_swot_agent.py with the added line(s) removed: 32F5F5E91EF0C29AF2B95C4E146C4BD6A4E607D2BA613C866DFFB274F5190058
tests/test_m3_swot_agent.py matches baseline: True
```

### Commands run and results

1. `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_mvp_agent.py`
   - first run: 59 passed, 1 failed (a fixture bug in my own new test: extra features had no refs, so a basis warning appeared; fixed by giving them basis `assumption`)
   - second run: **60 passed**, 0 failed, 1 warning
2. Full suite `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE`:
   **2039 passed, 1 failed**, 1 warning (Starlette/httpx deprecation).
   Failure: `tests/test_m3_swot_agent.py::test_the_real_agent_is_registered_for_stage_five`, line 528
   `assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["PendingStrategyAgent"] * 2`.
   This T5 test is NOT one of the two pre-approved edits, so I stopped and asked the parent (warning notification)
   before touching it. Nothing else failed.

### Blocker raised (waiting for an answer)

Options sent to the parent:
- A: change that one assertion to `== ["MvpAgent", "PendingStrategyAgent"]` (the test then states the real registration; changes an assertion).
- B (recommended, same pattern as the pre-approved edits): add `monkeypatch` to the test's parameters and one line
  `monkeypatch.setattr(STRATEGY_ONLY_STAGES[1], "agent", orchestrator.PendingStrategyAgent(STAGE_MVP))`; no assertion
  changes. The real stage-6 registration is asserted by the new `test_the_real_agent_is_registered_for_stage_six`.
- C: delete the line (weakens the test; not recommended).

### Parent answer: option A (assertion update)

The parent chose A: this test checks what is really registered, so the expected list is updated rather than patching
the registry back. The two approved monkeypatch lines stay, because those tests exercise the placeholder code path.

`tests/test_m3_swot_agent.py::test_the_real_agent_is_registered_for_stage_five`, line 528:

Before:
```python
    assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["PendingStrategyAgent"] * 2
```
After:
```python
    assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["MvpAgent", "PendingStrategyAgent"]
```
Nothing else in that test changed. It is still an exact comparison against the real registry. T7 will change it to
`["MvpAgent", "GtmAgent"]`.

Hash-restoration proof covering all three edits (`.\.venv\Scripts\python.exe -B .agents\tasks\m3-t6\check_test_edits.py`):
removing the added line and putting back the old assertion restores the baseline hashes.

```
tests/test_m3_orchestrator.py edited line at 139
tests/test_m3_orchestrator.py current: 9B9747559EADDBC2629AD132D1A26B7FD389032BF8ACF98DF5A58A45F842A81A
tests/test_m3_orchestrator.py with the edits undone: BEB81D6811E40C0A4D0091230249B27F1796A20CED75D1FD974BF01B8E684A4E
tests/test_m3_orchestrator.py matches baseline: True
tests/test_m3_swot_agent.py edited line at 533
tests/test_m3_swot_agent.py edited line at 528
tests/test_m3_swot_agent.py current: DCFFC7893966913F7B9D488B42658CDE76EA380E0A524AA87D9842DD80EAB8FE
tests/test_m3_swot_agent.py with the edits undone: 32F5F5E91EF0C29AF2B95C4E146C4BD6A4E607D2BA613C866DFFB274F5190058
tests/test_m3_swot_agent.py matches baseline: True
```

### Verification after the answer (all run with `$env:PYTHONIOENCODING="utf-8"`)

| # | Command | Result |
|---|---|---|
| 1 | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_mvp_agent.py` | 60 passed (run before the answer; the test file has not changed since) |
| 2 | `... tests/test_m3_mvp_agent.py tests/test_m3_swot_agent.py tests/test_m3_orchestrator.py tests/test_m3_digest.py tests/test_m3_checks.py tests/test_m3_strict_schema.py` | **268 passed**, 0 failed, 1 warning |
| 3 | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE` | **2040 passed** (1980 + 60), 0 failed, 1 warning (Starlette/httpx deprecation) |
| 6 | `... tests/test_m3_orchestrator.py -k "existing_stage_sets_are_unchanged or full_stages_run_is_identical or default_background_run_is_identical or sends_the_same_requests_as_before or registered_agent_a_strategy_stage_fails"` | 5 passed |
| 7 | `.\.venv\Scripts\python.exe -B .agents\tasks\m3-t6\verify.py` plus `Get-FileHash`/`Get-Item` on `data\runs.db` | runs.db 00A4F859...8337D, 311296 bytes, 2026-11-08T15:31:17Z: identical. 28 baseline files: 25 unchanged; changed only `orchestrator.py` (0B14E8D2 -> A87005B4, registration), `tests/test_m3_orchestrator.py` (approved line), `tests/test_m3_swot_agent.py` (approved line + approved assertion) |
| 8 | `git -C ... status --porcelain` | the baseline 29 lines plus `?? agents/mvp_agent.py` and `?? tests/test_m3_mvp_agent.py` |
| 9 | secret scan (in `verify.py`) of `agents/mvp_agent.py`, `tests/test_m3_mvp_agent.py`, `orchestrator.py`, `tests/test_m3_orchestrator.py`, `tests/test_m3_swot_agent.py` | 0 hits (planted test keys are built from string parts) |

New files: `agents/mvp_agent.py` 544 lines, SHA-256 8778190F7A89A159B9B5568BF7CB6DD0E3B1EF385B055BD8A8D9BF112FC8583E;
`tests/test_m3_mvp_agent.py` 918 lines, SHA-256 FD9CF11821C773B8AD87B64BB2A9796FB9FB17267EC254DA7F39B88FB45459B7.

Items 4 and 5 of the brief are covered by `test_a_seven_stage_run_stores_the_mvp_built_on_the_swot_risks`,
`test_a_run_whose_swot_failed_still_recommends_features`, `test_without_a_swot_the_stage_runs_with_a_notice_and_no_risk_refs`
and `test_scores_and_ranks_recompute_from_the_stored_ratings[expected|ties_and_clamps]`, all passing.

### Design decisions and plan-vs-code conflicts

1. **Score** `round(0.4*customer_need + 0.3*differentiation + 0.3*feasibility, 2)` (`SCORE_WEIGHTS`), ratings clamped to 1..5 first.
2. **Effort** `EFFORT_MONTHS = {S: 0.5, M: 1, L: 2}`; **capacity** `round(team_size * months_to_mvp * 0.6, 2)` on `apply_constraint_defaults` (team 2, months 3).
3. **Rank** = position after sorting by (not essential, score desc, effort months asc, draft order). The plan gives no final tie-breaker; draft order (the F number) makes ranks reproducible.
4. **Tier walk**: essentials always `mvp`; non-essentials in rank order are `mvp` while the cumulative effort stays within capacity, and the walk stops at the first one that does not fit ("the rest are later"). If the essentials alone exceed capacity, `over_capacity = true` and every non-essential is `later`. Founder features appended by code are always `later` and do not stop the walk.
5. **Ids**: `F{n}` in the order returned, after the checks and the cut (so ids are contiguous); appended founder features take the next numbers. Stored list is in rank order; `MVP.n` = `F{n}` (T3).
6. **Founder match (8.5 check 1/2)**: `token_overlap(name, key_feature) >= FOUNDER_MATCH_MIN`, set to `DUPLICATE_THRESHOLD` (0.8), the only "high overlap" figure in the plan. The plan gives no value for this; recorded as a gap.
7. **Appended founder feature**: origin `founder_listed`, ratings 3/3/3 and effort `M` (the 8.5 check 4 defaults), tier `later`, `based_on` = its `IDEA.n` key_feature fact, basis `user_provided`, deferred reason `REASON_ADDED`.
8. **Cut (8.5 check 5)**: over 12, remove the lowest scores (ties: later in draft order) among features that are not the first match of a founder feature; room is reduced by the number of appended features so the result never exceeds 12.
9. **Minimum (8.5 check 5)**: fewer than 3 model features surviving the checks fails with `LLMInvalidResponseError` (`llm_invalid_response`), counted before founder features are appended (code-made features with default ratings do not count). 3 succeeds with a shortfall warning (fewer than 4).
10. **8.3 step 4 lists 7.5 checks 1-3, 5, 6, 8**, but T3's `check_item` also runs check 4 (unsupported figure). I use `check_items` unchanged, so features with an unsupported currency/percent figure are removed too (stricter than the list; consistent with A.0 and A-R2 item 5).
11. **Effort default `M` (8.5 check 4)** is unreachable from the draft (`Literal["S","M","L"]`, T1 note); only rating clamping is reachable. `DEFAULT_EFFORT` is used for appended founder features.
12. **Metrics (8.5 check 6)**: empty name/how_to_measure dropped; overclaim or unsupported figure in name/how_to_measure removes the metric; duplicates removed; cut to 5; fewer than 2 is a shortfall warning, not a failure. `suggested_target` with an overclaim or a figure no digest fact states (checked with `figure_supported` against all digest refs, as T5 does for summary/limitations, because metrics cite no refs) loses the target, not the metric. Metrics carry no refs, so check 2 makes every metric basis `assumption` (this also labels each target as an assumption).
13. **Risk links (8.5 check 3)**: `mitigates` entries must be `RSK.n` refs present in the digest; they become `R{n}`; anything else (including bare `R3`) is removed with one warning. Without SWOT all are removed.
14. **Quality**: inputs over idea, market, competitors, swot; `basis_counts` and `grounded_share` over features only (metrics have no refs).
15. **Warnings** (one per code, in this order): `Repairs.warnings()`, empty parts, clamped ratings, origin changed, risk links removed, founder features added, targets removed, shortfall, over capacity, constraints assumed (whenever team size or months was missing), and `NO_SWOT` = "Risks were not considered when choosing features." exactly as in 8.6.
16. Summary/limitations helpers are duplicated from `swot_risk_agent.py` (private there) rather than imported across agents.

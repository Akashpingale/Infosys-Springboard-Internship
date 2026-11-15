# M3-T6 review (iteration 1)

Verdict: APPROVED, no blockers.

## Evidence checked

- Fingerprints (Get-FileHash against `baseline.json`): 25 of 28 protected files unchanged. The only changes are `orchestrator.py`, `tests/test_m3_orchestrator.py` and `tests/test_m3_swot_agent.py`. `data/runs.db` is unchanged: 00A4F859...8337D, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17Z.
- `orchestrator.py`: I wrote `review_check_orch.py` in this task folder. It removes the `MvpAgent` import, restores "(plan Tasks T6 and T7)" and restores `PendingStrategyAgent(STAGE_MVP)`, and the result has the baseline hash. So the only changes are the import (line 28), the docstring word and the stage-6 registration (line 215). GTM is still `PendingStrategyAgent(STAGE_GTM)`.
- Test edits: `check_test_edits.py` restores both baseline hashes. The edits are:
  - `test_m3_orchestrator.py:139`, a pre-approved monkeypatch line.
  - `test_m3_swot_agent.py:533`, a pre-approved monkeypatch line. The test already took `monkeypatch`.
  - `test_m3_swot_agent.py:528`, an assertion change from `["PendingStrategyAgent"] * 2` to `["MvpAgent", "PendingStrategyAgent"]`.
- The edit at line 528 is not one of the two pre-approved edits. The coder followed the brief's stop-and-ask rule and the parent chose option A (coder-notes.md). The test is not weaker: it still compares exactly against the real registry. The final report must list this third edit and its approval.
- `git status --porcelain` matches the baseline plus `?? agents/mvp_agent.py` and `?? tests/test_m3_mvp_agent.py`. Nothing changed in routes/, web/, frontend/, docs/, models/ or the plan.
- Secret-pattern grep over `mvp_agent.py`, `test_m3_mvp_agent.py` and `orchestrator.py`: 0 hits.
- Recorded results (not re-run): T6 tests 60 passed. T3-T6 regression 268 passed. Full suite 2040 passed (1980 + 60), 0 failed, 1 known warning. M1/M2 pin tests 5 passed.

## Spec conformance (agents/mvp_agent.py)

### 8.4 scoring, capacity, tiers and rank

- **Score:** `SCORE_WEIGHTS` 0.4/0.3/0.3 on ratings clamped to 1..5, rounded to 2 places.
- **Effort and capacity:** `EFFORT_MONTHS` S 0.5, M 1, L 2. `FOCUS_FACTOR` 0.6. Capacity is `team x months x 0.6` on `apply_constraint_defaults` (defaults: team 2, months 3).
- **Sort order:** essential first, then score descending, then lower effort, then draft order as the final tie-break. The plan gives no final tie-break; the coder recorded this choice.
- **Tier walk:** mvp while the cumulative effort fits capacity, and the walk stops at the first misfit. Essential features are always mvp.
- **Over capacity:** when the essential features alone need more than capacity, `over_capacity` is true, every non-essential feature is `later`, and a plain-language notice is added.
- **Rank:** the sorted position.
- **Constants:** all in one block, as Appendix C requires.

### 8.5 checks

1. A feature marked founder_listed that matches no founder feature (token overlap 0.8 or more) becomes `suggested`, with a warning.
2. A missing founder feature is appended as `later` with origin founder_listed, ratings 3/3/3, effort M, its IDEA ref and a warning. The cut keeps features that match a founder feature.
3. `mitigates` keeps only `RSK.n` refs present in the digest and stores them as `R{n}`. Invalid ones are removed with a warning.
4. Ratings are clamped with a warning. The effort default is unreachable because the draft uses a Literal (T1 note).
5. Features above 12 are cut by lowest score. Fewer than 3 raises `LLMInvalidResponseError`. Fewer than 4 succeeds with a shortfall warning.
6. Metrics are kept to 2-5. A target with an overclaim or an unsupported figure loses the target and keeps the metric. Every metric basis is `assumption`.

### 7.5 shared checks

`check_items` (checks 1-6 and 8), `shorten_fields`, `Repairs.warnings()` and `ensure_no_secrets` are used the same way as in T5.

### 8.6 failure and partial cases

- No SWOT: the exact "Risks were not considered when choosing features." warning, and the prompt has no RSK facts.
- Missing constraints: the "assumed ..." warning and `quality.constraints_assumed`.
- Over capacity: the stage succeeds and the run completes.
- Provider failure, invalid output after retry and too little content: stage error, run partial, earlier results kept.
- No finished analysis: the stage is skipped (T4 logic). A direct call raises `StrategyNotReadyError` before any model call.

### Integration

- The prompt carries RSK.* facts when SWOT exists.
- `PipelineResult.mvp` is stored.
- `MVP.n` digest facts equal `F{n}`, which is tested in a seven-stage run.

### A.2 and A.0 prompt

The system prompt is A.0 verbatim (tested equal to T5's) plus the A.2 role. The user prompt has the A.2 rules and the digest inside `<facts>` delimiters.

## T6 test bullets

| Bullet | Tests |
|---|---|
| Score and rank recomputation (A-R2 item 1) | `test_scores_and_ranks_recompute_from_the_stored_ratings[expected, ties_and_clamps]` |
| Capacity arithmetic for several constraint sets | `test_capacity_is_team_times_months_times_the_focus_factor`, 6 sets |
| Defaults flagged as assumed | `test_missing_constraints_run_on_defaults_marked_as_assumed`, `test_one_missing_constraint_is_assumed...` |
| Over-capacity case | `test_essential_features_over_capacity...`, `test_over_capacity_is_a_result_not_an_error`, `test_essential_features_that_just_fit...` |
| Missing founder feature appended as later | `test_a_missing_founder_feature_is_appended_as_later`, `test_every_founder_feature_appears...` |
| Invalid risk ids removed | `test_risk_links_that_are_not_in_the_risk_analysis_are_removed` |
| Clamped ratings | `test_ratings_outside_the_scale_are_clamped` |
| Run without SWOT | `test_without_a_swot...`, `test_a_run_whose_swot_failed...` |
| Failure paths | `test_too_few_features_fail_the_stage`, `test_a_failed_stage_keeps_the_earlier_results...`, secret tests, skip test |

No T7+ scope was found: no GTM agent, Advisor, routes, notice templates or frontend work.

## Non-blocking notes

- The founder-feature match threshold of 0.8 is not specified by the plan, and the coder recorded it as a gap. A founder feature that the model renames heavily is appended again as `later` rather than lost, so check 2 still holds.

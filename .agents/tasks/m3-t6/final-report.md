# M3-T6 final report: MVP recommendation agent (R2)

Branch `main`, HEAD `a098aef0408fcef8ec8bd497ee42dbedebc334f7`, worked in place. Nothing was committed, pushed, reset, reverted or stashed. The loop ran for one iteration and the review is APPROVED with no findings (`review.json`, `review.md`). Every check below was re-run in this final step.

## 1. Files changed and created

| File | State | Purpose | Diff size |
|---|---|---|---|
| `agents/mvp_agent.py` | new | Stage 6. It builds the A.0 + A.2 prompt, makes one structured call (`MvpDraft`), runs the shared checks and the 8.5 checks, then scores, ranks and fits features to capacity in code and builds `MvpResult`. The agent is `MvpAgent` (name `mvp_recommendation`). The file has no comments or docstrings (§0.5). | +544 lines. SHA-256 `8778190F7A89A159B9B5568BF7CB6DD0E3B1EF385B055BD8A8D9BF112FC8583E` |
| `tests/test_m3_mvp_agent.py` | new | 60 T6 tests, using fake replies only | +918 lines. SHA-256 `FD9CF11821C773B8AD87B64BB2A9796FB9FB17267EC254DA7F39B88FB45459B7` |
| `orchestrator.py` | modified | Registration only | +1 line, 2 lines changed. `0B14E8D2…` -> `A87005B4…` |
| `tests/test_m3_orchestrator.py` | pre-approved edit | Restores the MVP placeholder for one placeholder-path test | +1 line. `BEB81D68…` -> `9B974755…` |
| `tests/test_m3_swot_agent.py` | pre-approved edit plus one parent-approved assertion edit | Restores the MVP placeholder for one test, and updates the expected registry list in another | +1 line, 1 line changed. `32F5F5E9…` -> `DCFFC789…` |

Nothing changed in `routes/`, `frontend/`, `web/`, `docs/`, `models/`, the plan or `KIRO_*.md`.

## 2. Registration diff (`orchestrator.py`, against its T5 state)

```diff
+from agents.mvp_agent import MvpAgent
 from agents.notices import STAGE_GTM, STAGE_MVP, STAGE_SWOT, STRATEGY_TITLES
 from agents.swot_risk_agent import SwotRiskAgent
@@ class PendingStrategyAgent:
-    """Stands in for a strategy agent until it is built (plan Tasks T6 and T7). Its stage fails with
+    """Stands in for a strategy agent until it is built (plan Task T7). Its stage fails with
@@ STRATEGY_ONLY_STAGES
     StrategyStage(SwotRiskAgent(), STRATEGY_TITLES[STAGE_SWOT]),
-    StrategyStage(PendingStrategyAgent(STAGE_MVP), STRATEGY_TITLES[STAGE_MVP]),
+    StrategyStage(MvpAgent(), STRATEGY_TITLES[STAGE_MVP]),
     StrategyStage(PendingStrategyAgent(STAGE_GTM), STRATEGY_TITLES[STAGE_GTM]),
```

The changed lines are 28 (import), 163 (docstring) and 215 (stage 6). The GTM stage is still `PendingStrategyAgent(STAGE_GTM)`, and line 216 is unchanged. Proof: `review_check_orch.py` reverses these three edits, and the result matches the baseline hash: `orchestrator restored matches baseline: True`.

## 3. Test edits to existing files

**(a) Pre-approved.** `tests/test_m3_orchestrator.py::test_without_a_registered_agent_a_strategy_stage_fails_plainly`. One line was added at line 139. No assertion changed.

```python
# before (lines 138-139)
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[0], "agent", orchestrator.PendingStrategyAgent(STAGE_SWOT))
    result, _ = strategy_run()
# after (lines 138-140)
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[0], "agent", orchestrator.PendingStrategyAgent(STAGE_SWOT))
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[1], "agent", orchestrator.PendingStrategyAgent(STAGE_MVP))
    result, _ = strategy_run()
```

**(b) Pre-approved.** `tests/test_m3_swot_agent.py::test_a_seven_stage_run_stores_the_swot_and_its_risks_join_the_digest`. One line was added at line 533. The test already took the `monkeypatch` fixture, so its signature did not change. No assertion changed.

```python
# before
    use_full_pipeline(monkeypatch)
    use_reply(monkeypatch, as_reply(draft()))
# after
    use_full_pipeline(monkeypatch)
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[1], "agent", orchestrator.PendingStrategyAgent(STAGE_MVP))
    use_reply(monkeypatch, as_reply(draft()))
```

**(c) Not pre-approved. The coder stopped and asked, and the parent chose option A.** `tests/test_m3_swot_agent.py::test_the_real_agent_is_registered_for_stage_five`, line 528. This T5 test asserts the real registry. It was the only other test that failed after registration (full suite: 2039 passed, 1 failed).

```python
# before
    assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["PendingStrategyAgent"] * 2
# after
    assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["MvpAgent", "PendingStrategyAgent"]
```

The test is not weaker: it is still an exact comparison against the real registry. T7 will need the same edit (`["MvpAgent", "GtmAgent"]`).

**Hash-restoration proof** (`check_test_edits.py`, re-run in this step). It removes the added lines and restores the old assertion:

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

## 4. Requirement mapping

### 8.3 execution flow (`recommend_mvp`, `build_result`)

1. **Sufficiency and digest.** If the idea is missing, or market and competitors are both missing, the agent raises `StrategyNotReadyError` before any model call. Otherwise it calls `build_digest(idea, constraints, market, competitors, swot=swot)`, which adds `RSK.n` facts when a SWOT exists. When the stage runs inside a pipeline, T4's stage-level skip rule applies first.
2. **Constraint defaults.** The digest adds `CON.*` facts and marks each default as "an assumed default because the founder did not give one". `apply_constraint_defaults` gives `used`, `provided` and `assumed`.
3. **Prompt.** `build_prompt(digest)` returns `(SYSTEM_PROMPT, user)`, where the system prompt is SHARED_RULES (A.0) plus ROLE (A.2). The model is called once: `call_structured(system, user, MvpDraft, caller=generate_json)`.
4. **Checks.** The shared checks run through `check_items`, followed by the 8.5 checks (below).
5. **Code-side ranking.** `feature_score`, `_rank_key` and `assign_tiers` score, rank and fit the features.
6. **Result.** `MvpResult` is built with `StrategyQuality`. Then `ensure_no_secrets(result)` runs, and `MvpAgent.run` writes `context.mvp` and adds warnings prefixed "Recommending MVP features: …".

### 8.4 scoring, capacity, tiers and rank

All constants sit in one block (Appendix C):

| Constant | Value |
|---|---|
| `SCORE_WEIGHTS` | `customer_need` 0.4, `differentiation` 0.3, `feasibility` 0.3 |
| `SCORE_PLACES` | 2 |
| `EFFORT_MONTHS` | S 0.5, M 1.0, L 2.0 |
| `FOCUS_FACTOR` | 0.6 |
| `DEFAULT_RATING` | 3 |
| `DEFAULT_EFFORT` | `M` |
| Rating range | `RATING_RANGE` from the models |
| `FEATURES_RANGE` | (4, 12) |
| `MIN_FEATURES` | 3 |
| `METRICS_RANGE` | (2, 5) |

The formulas are:

- **Score:** `round(0.4*need + 0.3*diff + 0.3*feas, 2)`. Ratings are clamped to 1..5 first.
- **Capacity:** `round(team_size * months_to_mvp * 0.6, 2)`, computed on the constraints after defaults (team 2, months 3).
- **Sort key:** `(not essential, -score, effort months, draft order)`.
- **Rank:** the sorted position, starting at 1.
- **Tier walk:** essential features are always `mvp`. Non-essential features in rank order are `mvp` while the cumulative effort stays within capacity, and the walk stops at the first feature that does not fit.
- **Over capacity:** if the essential effort alone exceeds capacity, then `over_capacity = true`, every non-essential feature is `later`, and a plain-language warning is added.

**Worked example.** This is the test fixture `draft()` with default constraints, so capacity is 2 × 3 × 0.6 = 3.6.

| Id | Ratings (need, diff, feas) | Score | Essential | Effort | Rank | Cumulative effort | Tier |
|---|---|---|---|---|---|---|---|
| F1 | 5, 2, 4 | 2.0 + 0.6 + 1.2 = 3.8 | yes | M (1) | 1 | 1.0 | mvp |
| F2 | 4, 4, 3 | 3.7 | yes | M (1) | 2 | 2.0 | mvp |
| F3 | 4, 3, 3 | 3.4 | no | S (0.5) | 3 | 2.5 | mvp |
| F6 | 3, 2, 5 | 3.3 | no | S (0.5) | 4 | 3.0 | mvp |
| F4 | 3, 4, 3 | 3.3 | no | M (1) | 5 | 4.0 > 3.6 | later (the walk stops here) |
| F8 | 2, 3, 4 | 2.9 | no | S | 6 | | later |
| F5 | 3, 3, 2 | 2.7 | no | L | 7 | | later |
| F7 | 2, 2, 2 | 2.0 | no | L | 8 | | later |

F6 ranks before F4 because the scores tie and F6 has lower effort. The result is `planned_person_months = 3.0`, `over_capacity = false`, and every later feature gets `REASON_CAPACITY` with "3.6". This is asserted in `test_a_fake_reply_becomes_the_expected_result`. The fixture's values are synthetic test data, not Appendix B values.

**Capacity arithmetic for each tested constraint set.** The essential effort is 2.0 unless noted.

| Constraints given (team, months) | Used | Capacity | Planned | over_capacity | Test |
|---|---|---|---|---|---|
| none, none | 2, 3 (both assumed) | 3.6 | 3.0 | false | `test_capacity_…[None-None-…]`, `test_missing_constraints_run_on_defaults_marked_as_assumed` |
| 1, 1 | 1, 1 | 0.6 | 2.0 (essential only) | true | `test_capacity_…`, `test_over_capacity_is_a_result_not_an_error` (run level) |
| 3, none | 3, 3 (months assumed) | 5.4 | 4.5 | false | `test_capacity_…`, `test_one_missing_constraint_is_assumed_and_the_rest_are_kept` |
| none, 6 | 2, 6 (team assumed) | 7.2 | 6.5 | false | `test_capacity_…` |
| 4, 6 | 4, 6 | 14.4 | 8.5 (all mvp) | false | `test_capacity_…`, `test_features_fill_the_capacity_in_rank_order…` |
| 10, 12 | 10, 12 | 72.0 | 8.5 (all mvp) | false | `test_capacity_…` |
| 1, 3, with 4 essential features | 1, 3 | 1.8 | 5.0 (essential effort 5.0) | true | `test_essential_features_over_capacity_all_stay_in_the_first_release` |
| 1, 4 | 1, 4 | 2.4 | 2.0 (essentials just fit) | false | `test_essential_features_that_just_fit_are_not_over_capacity` |

The planned values come from applying the walk to the fixture. Each test also recomputes the tiers with an independent helper (`recomputed_tiers`) and checks `planned == sum(mvp efforts)`.

### 8.5 MVP checks

| # | Check | Implementation |
|---|---|---|
| 1 | `origin = founder_listed` must match a founder key feature | `_matches` uses `token_overlap(name, key_feature) >= FOUNDER_MATCH_MIN`, which is `DUPLICATE_THRESHOLD` (0.8). Normalised names match because the comparison uses normalised tokens. A feature with no match becomes `suggested`, with the `ORIGIN_CHANGED` warning. |
| 2 | Every founder key feature appears in the output | A missing founder feature is appended by `_founder_feature` with origin `founder_listed`, ratings 3/3/3, effort M, `based_on` its `IDEA.n` key_feature fact, basis `user_provided`, tier `later`, `REASON_ADDED`, and the `FOUNDER_ADDED` warning. `_cut` never removes the first match of a founder feature. |
| 3 | `mitigates_risk_ids` refer to real risks | `_risk_ids` keeps only `RSK.n` refs present in the digest, stored as `R{n}` with duplicates removed. Anything else (`RSK.99`, bare `R3`, `MKT.5`) is removed with `RISK_LINKS_REMOVED`. Without a SWOT, all are removed. |
| 4 | Ratings and effort in range | `_clamped` moves ratings to the nearest end of 1..5, with `RATINGS_CLAMPED`. The effort default is unreachable because `MvpDraft` effort is `Literal["S","M","L"]` (T1 note), so `DEFAULT_EFFORT` is used only for appended founder features. |
| 5 | 4 to 12 features | `_cut` removes the lowest scores above 12, with `cut_to_limit` and its warning. Fewer than 3 raises `LLMInvalidResponseError(MSG_TOO_LITTLE)` (`llm_invalid_response`). Exactly 3 succeeds with the `FEWER_THAN_ASKED` shortfall warning. |
| 6 | 2 to 5 success metrics, target only as an assumption, figure-checked | `_metrics` handles this (details after the table). |

Details of check 6 (`_metrics`):

- Metrics with an empty name or how_to_measure are dropped.
- A metric whose name or how_to_measure contains an overclaim or an unsupported figure is removed.
- Duplicates are removed (`remove_duplicates`), and the list is cut to 5.
- A `suggested_target` with an overclaim, or a figure that no digest fact states (`figure_supported` against all digest refs), loses the target but keeps the metric. The `TARGETS_REMOVED` warning is added.
- Metrics cite no refs, so `adjusted_basis` makes every metric basis `assumption`. This is what labels each target as an assumption.
- Fewer than 2 metrics produces a shortfall warning.

### 7.5 shared checks used, with the T3 function for each

| 7.5 check | T3 function |
|---|---|
| 1. Ref exists | `check_items` (via `check_item`), which removes invalid refs |
| 2 and 3. Basis consistency and `user_provided` refs | `check_items`, plus `adjusted_basis` for metrics and appended features |
| 4. Unsupported figure | `check_items` for features. `figure_supported` for metric texts and targets, the summary and limitations. |
| 5. Overclaim | `check_items` and `overclaims` |
| 6. Near-duplicate | `check_items` for features, `remove_duplicates` for metrics |
| 7. List limits | `cut_to_limit` (features over 12, metrics over 5, limitations over 4) |
| 8. Length limits | `shorten_fields` (inside `check_items` with `FEATURE_LENGTHS`, and `METRIC_LENGTHS`) and `shorten` (summary, limitations, appended names) |
| 9. Minimum content | MVP version: fewer than 3 features raises `LLMInvalidResponseError` |
| 10. Secrets | `ensure_no_secrets(result)` |

Other T3 functions used: `inherited_sources` (feature `sources` come from `based_on`), and `Repairs` / `Repairs.warnings()`, which give one warning per code.

### Founder features preserved

- Founder features come from `idea.key_features` (digest `IDEA.n` facts of kind `key_feature`).
- Tests: `test_a_missing_founder_feature_is_appended_as_later` (F8 is appended as later with 3/3/3, M, score 3.0, `IDEA.9`) and `test_every_founder_feature_appears_even_when_the_reply_has_none`.
- Normalised-name match: `test_a_founder_feature_is_matched_by_its_normalised_name`.
- Mislabelled origin: `test_a_feature_wrongly_marked_as_founder_listed_becomes_suggested`.
- Cut protection: `test_features_beyond_twelve_are_cut_by_lowest_score_and_founder_ones_stay`.

### 8.6 failure and partial cases

| Case | Behaviour | Test |
|---|---|---|
| No SWOT | Warning "Risks were not considered when choosing features." (`NO_SWOT`), no `[RSK.` in the prompt, all risk links removed, `inputs_missing == ["swot"]` | `test_without_a_swot_the_stage_runs_with_a_notice_and_no_risk_refs`, `test_a_run_whose_swot_failed_still_recommends_features` |
| All constraints missing | Runs on team 2 and months 3. Warning "assumed a team of 2 people and 3 months to the first release because they were not given". `constraints_assumed` has both. | `test_missing_constraints_run_on_defaults_marked_as_assumed` |
| Over capacity | Stage succeeds and the run is `complete` | `test_over_capacity_is_a_result_not_an_error` |
| Provider failure, invalid output after retry, too little content | Stage error (`llm_api_error` or `llm_invalid_response`). The run is `partial`, earlier results are kept, and GTM still runs. | `test_a_failed_stage_keeps_the_earlier_results_and_the_run_partial[provider_failure, invalid_after_retry, too_little_content]` |
| No finished analysis | Stage skipped (T4 rule), no model call | `test_a_run_without_any_finished_analysis_skips_the_stage`, `test_without_enough_input_the_model_is_not_called[analyses, idea]` |
| Secret in the reply | Stage fails and nothing is stored | `test_a_secret_in_the_reply_fails_the_stage`, `test_a_secret_never_reaches_the_stored_result` |

Cancel is honoured between stages by the existing T4 orchestrator logic.

### A.2 and A.0 prompt

- The system prompt is SHARED_RULES (A.0 verbatim, asserted equal to T5's `SHARED_RULES`) plus `ROLE = "Role: product advisor choosing the smallest useful first release."`.
- The user prompt has the facts line (IDEA, CON with assumed marks, MKT, CMP, RSK when available), then the digest inside `<facts>` … `</facts>` (`DIGEST_OPEN` and `DIGEST_CLOSE`, each appearing once), then "Produce:".
- The task rules are: 6 to 10 candidates; every founder feature as `founder_listed`; `gap_opportunity` and `suggested` origins; the essential rule; ratings 1 to 5; effort S/M/L; `mitigates` as RSK refs; the rating guide; 2 to 5 metrics, where a target is an assumption with no number unless a cited fact has it; a two-sentence summary; up to 4 limitations; and "Do not rank the features and do not decide what fits the time. The system does that."
- The prompt ends with the length limits and the JSON schema text.
- Text that tries to close the data block stays inside it (`test_text_that_tries_to_close_the_data_block_stays_inside_it`).
- No raw `S\d+` source ids appear inside the facts.

### RSK.* consumption and MVP.* digest integration

- **RSK.* in the prompt:** `test_the_prompt_carries_the_digest_with_the_risks` checks that the prompt has `RSK.1`..`RSK.6` with each risk title, and that it equals `build_prompt(build_digest(..., swot=swot))`.
- **Stored result built on the SWOT:** `test_a_seven_stage_run_stores_the_mvp_built_on_the_swot_risks` checks a seven-stage fake run with a fake SWOT reply, a fake MVP reply and the GTM placeholder.
  - The run is `partial`, and its only error is the GTM placeholder.
  - `PipelineResult.mvp` is stored and survives a JSON round trip.
  - The MVP prompt has every `RSK.n` line with the SWOT risk title, and F2 mitigates `["R2"]`.
  - A digest built with `mvp=stored.mvp` has `MVP.n` facts exactly equal to the `F{n}` ids, with name, "tier, rank" text, sources and basis matching. Without `mvp` there are no feature facts.
- **Saved result:** `test_a_strategy_only_job_runs_the_real_stage_on_a_saved_result` checks that a strategy-only job on a saved result runs the real stage with `[RSK.1]` in the prompt.

## 5. T6 tests grouped by the plan's test bullets

| Plan bullet | Tests |
|---|---|
| Score and rank recomputation (A-R2 item 1) | `test_scores_and_ranks_recompute_from_the_stored_ratings[expected]`, `[ties_and_clamps]`, `test_the_score_follows_the_weights` (6 cases), `test_ties_break_on_lower_effort_then_on_the_order_returned`, `test_a_fake_reply_becomes_the_expected_result` |
| Capacity arithmetic for several constraint sets | `test_capacity_is_team_times_months_times_the_focus_factor` (6 sets), `test_features_fill_the_capacity_in_rank_order_and_the_walk_stops_at_the_first_misfit` |
| Defaults flagged as assumed | `test_missing_constraints_run_on_defaults_marked_as_assumed`, `test_one_missing_constraint_is_assumed_and_the_rest_are_kept` |
| Over-capacity case | `test_essential_features_over_capacity_all_stay_in_the_first_release`, `test_essential_features_that_just_fit_are_not_over_capacity`, `test_over_capacity_is_a_result_not_an_error` |
| Missing founder feature appended as `later` | `test_a_missing_founder_feature_is_appended_as_later`, `test_every_founder_feature_appears_even_when_the_reply_has_none`, `test_a_founder_feature_is_matched_by_its_normalised_name`, `test_a_feature_wrongly_marked_as_founder_listed_becomes_suggested`, `test_features_beyond_twelve_are_cut_by_lowest_score_and_founder_ones_stay` |
| Invalid risk ids removed | `test_risk_links_that_are_not_in_the_risk_analysis_are_removed` |
| Clamped ratings | `test_ratings_outside_the_scale_are_clamped` |
| Run without SWOT | `test_without_a_swot_the_stage_runs_with_a_notice_and_no_risk_refs`, `test_a_run_whose_swot_failed_still_recommends_features` |
| Failure paths | `test_too_few_features_fail_the_stage` (parametrised), `test_a_failed_stage_keeps_the_earlier_results_and_the_run_partial[provider_failure, invalid_after_retry, too_little_content]`, `test_a_secret_in_the_reply_fails_the_stage`, `test_a_secret_never_reaches_the_stored_result`, `test_a_run_without_any_finished_analysis_skips_the_stage`, `test_without_enough_input_the_model_is_not_called[analyses, idea]` |
| Shared checks (7.5) | `test_a_ref_that_is_not_in_the_digest_is_removed_and_basis_adjusted`, `test_features_with_an_unsupported_figure_an_overclaim_or_a_repeat_are_removed`, `test_text_over_its_limit_is_shortened_and_empty_names_are_dropped`, `test_the_summary_and_limitations_are_checked_too`, `test_fewer_than_four_features_succeed_with_a_warning` |
| Success metrics (8.5 check 6) | `test_success_metric_targets_with_an_unsupported_figure_lose_the_target_not_the_metric`, `test_a_target_whose_figure_a_finding_states_is_kept`, `test_success_metrics_are_checked_cut_and_counted` |
| Integration and stage 6 live in fake-backed runs | `test_the_real_agent_is_registered_for_stage_six`, `test_a_seven_stage_run_stores_the_mvp_built_on_the_swot_risks`, `test_a_strategy_only_job_runs_the_real_stage_on_a_saved_result`, `test_the_stage_reports_its_repairs_under_its_label`, `test_the_agent_writes_the_result_and_its_warnings_to_the_context`, `test_one_finished_analysis_is_enough` |
| Prompt (A.0 and A.2) | `test_the_prompt_carries_the_digest_with_the_risks`, `test_the_prompt_has_a_system_part_with_the_shared_rules_and_the_role`, `test_the_prompt_has_a_user_part_with_the_digest_inside_its_delimiters`, `test_text_that_tries_to_close_the_data_block_stays_inside_it` |

## 6. Verification (re-run in this step)

All commands ran with `$env:PYTHONIOENCODING="utf-8"` and `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE`.

| # | Check | Result |
|---|---|---|
| 1 | `tests/test_m3_mvp_agent.py` | **60 passed**, 0 failed, 1 warning, 3.67 s |
| 2 | `tests/test_m3_swot_agent.py tests/test_m3_orchestrator.py tests/test_m3_digest.py tests/test_m3_checks.py tests/test_m3_strict_schema.py` | **208 passed**, 0 failed, 1 warning, 8.69 s. Together with item 1 that is 268, which matches the coder's combined run. |
| 3 | Full suite | **2040 passed** (1980 baseline + 60 new), 0 failed, 1 warning (StarletteDeprecationWarning, httpx with starlette.testclient), 61.02 s |
| 4 | Seven-stage fake run, RSK in the prompt, no-SWOT warning, MVP.n = F{n} | `-k` selection: **7 passed**. The tests are `test_the_prompt_carries_the_digest_with_the_risks`, `test_scores_and_ranks_recompute_from_the_stored_ratings[expected]`, `[ties_and_clamps]`, `test_without_a_swot_the_stage_runs_with_a_notice_and_no_risk_refs`, `test_a_seven_stage_run_stores_the_mvp_built_on_the_swot_risks`, `test_a_run_whose_swot_failed_still_recommends_features` and `test_a_strategy_only_job_runs_the_real_stage_on_a_saved_result`. |
| 5 | A.7-1 recomputation | `test_scores_and_ranks_recompute_from_the_stored_ratings[expected]` and `[ties_and_clamps]` passed (included in item 4). They recompute score, rank order, tiers and planned effort from the stored ratings after a JSON round trip, with independent formula code in the test. |
| 6 | M1/M2 unchanged | **5 passed**: `test_the_existing_stage_sets_are_unchanged`, `test_a_full_stages_run_is_identical_to_before`, `test_a_default_background_run_is_identical_to_before`, `test_an_existing_call_sends_the_same_requests_as_before` (M2 provider-request pin) and `test_without_a_registered_agent_a_strategy_stage_fails_plainly` |
| 7 | Fingerprints | See section 7 |
| 8 | `git status --porcelain` | 31 lines: the 29 baseline lines (the T1-T5 set and `?? .agents/`) plus `?? agents/mvp_agent.py` and `?? tests/test_m3_mvp_agent.py`. Branch `main`, HEAD unchanged at `a098aef0`. |
| 9 | Secret scan | `verify.py` scanned `agents/mvp_agent.py`, `tests/test_m3_mvp_agent.py`, `orchestrator.py`, `tests/test_m3_orchestrator.py` and `tests/test_m3_swot_agent.py` for AIza…, gsk_…, tvly-…, sk-…, Bearer tokens and PRIVATE KEY. Result: **0 hits**. The planted test keys are built from string parts. |

## 7. Fingerprint evidence

`data/runs.db` was checked with `Get-FileHash` and `Get-Item` only, and was never opened:

- SHA-256 `00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D`
- Size 311296
- LastWriteTimeUtc `2026-11-08T15:31:17Z`

This is identical to the expected values and to the baseline.

All 28 protected files were checked by `verify.py` against `baseline.json`: **25 unchanged, 3 changed, all expected.**

| Changed file | Before -> after | Reason |
|---|---|---|
| `orchestrator.py` | `0B14E8D2` -> `A87005B4` | Registration only. Reversing the edits restores the baseline hash. |
| `tests/test_m3_orchestrator.py` | `BEB81D68` -> `9B974755` | The approved added line. Removing it restores the baseline hash. |
| `tests/test_m3_swot_agent.py` | `32F5F5E9` -> `DCFFC789` | The approved added line and the parent-approved assertion. Undoing both restores the baseline hash. |

The 25 unchanged files are: `.env.example`, `config.py`, `models/api.py`, `models/schemas.py`, `utils/errors.py`, `models/chat.py`, `models/strategy_drafts.py`, `tests/test_m3_schemas.py`, `utils/run_store.py`, `utils/chat_store.py`, `tests/test_m3_store_migration.py`, `tests/test_run_store.py`, `agents/strategy_context.py`, `agents/strategy_checks.py`, `tests/test_m3_digest.py`, `tests/test_m3_checks.py`, `tests/test_m3_strict_schema.py`, `agents/base.py`, `agents/notices.py`, `utils/deadline.py`, `utils/groq_client.py`, `utils/llm_client.py`, `utils/run_manager.py`, `tests/m3_fakes.py` and `agents/swot_risk_agent.py`.

No `.env` file was opened or printed, `app.py` was not started, and no network or provider call was made.

## 8. Plan-vs-code conflicts and decisions

1. **Third test edit.** The assertion at `tests/test_m3_swot_agent.py:528` is not in the brief's two pre-approved edits, and plan §20.4 says existing tests change "only by adding the new expected value". The coder stopped and asked, and the parent chose option A: replace the expected list with the real registry. This is recorded here as required. T7 will need the same kind of edit.
2. **8.3 step 4 lists 7.5 checks 1-3, 5, 6 and 8.** T3's `check_items` also runs check 4 (unsupported figure), so features with an unsupported figure are removed too. This is stricter than the list but consistent with A.0 and A-R2 item 5.
3. **8.5 check 4 effort default is unreachable** because the draft effort is a `Literal` (T1). Only rating clamping is reachable and tested.
4. **Founder-match threshold.** 8.5 check 1 says "high token overlap" with no number. The code uses `DUPLICATE_THRESHOLD` (0.8), the only overlap figure in the plan. If the model renames a founder feature heavily, it is appended again as `later` rather than lost.
5. **Rank tie-break.** The plan's sort is essential, then score, then lower effort. The code adds draft order (the F number) as a final tie-break so that ranks are reproducible.
6. **Tier walk.** "Mark `mvp` while cumulative effort stays within capacity; the rest are `later`" is read as stopping at the first misfit, so a smaller later feature does not jump ahead. Founder features appended by code are always `later` and do not stop the walk.
7. **The minimum of 3 features** is counted before founder features are appended, so code-made features do not count toward it.
8. **Metrics carry no refs.** Their basis is therefore always `assumption`, which labels every target as an assumption. Targets are figure-checked against all digest refs, the same way T5 checks its summary and limitations.
9. **Duplicated helpers.** The summary and limitations helpers are copied from `swot_risk_agent.py`, where they are private, rather than imported across agents.
10. **Warning wording.** The agent's warnings are plain internal strings, such as "the essential features need … person-months …" and "assumed a team of 2 people …". The plan's notice templates (`mvp_constraints_assumed`, `mvp_over_capacity`) belong to T9 and were not built here.

## 9. Unresolved issues and what remains for T7+

- **Unresolved:** none blocking. The founder-match threshold (0.8) is a recorded gap in the plan, not a defect.
- **T7:**
  - Build the GTM agent. Stage 7 is still `PendingStrategyAgent(STAGE_GTM)`.
  - It consumes `MVP.*` facts, which `build_digest(..., mvp=...)` already provides.
  - Update `test_the_real_agent_is_registered_for_stage_five` and `test_the_real_agent_is_registered_for_stage_six` (its last line asserts the GTM placeholder).
  - Revisit the placeholder-restoring monkeypatch lines.
- **Later tasks:**
  - Advisor and chat.
  - Routes.
  - Notice templates and codes (T9).
  - React UI: MVP section, capacity bar, "AI estimate" labels.
  - Markdown export.
  - Live verification (§20.7). This was not run and is not claimed.

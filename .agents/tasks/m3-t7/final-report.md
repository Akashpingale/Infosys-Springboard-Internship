# M3-T7 final report: go-to-market agent (R3)

Work was done in place on branch `main` at HEAD `a098aef0408fcef8ec8bd497ee42dbedebc334f7`. Nothing was committed, pushed, reset, reverted or stashed. The implement-and-review loop ran one iteration. The review verdict is APPROVED with no findings (`review.json`, `review.md`). I re-ran every verification item below in this final step, and all nine pass.

## 1. Files changed and created

| File | State | Purpose | Diff size |
|---|---|---|---|
| `agents/gtm_agent.py` | new | Stage 7, `GtmAgent` (name `go_to_market`). It holds one constants block and `build_prompt(digest) -> (system, user)` (A.0 + A.3). It makes one `call_structured(system, user, GtmDraft, caller=generate_json)` call. `build_result` runs the shared and GTM checks, then assembles the positioning, ranks the channels and validates the cross-references. `plan_go_to_market(idea, constraints, market, competitors, swot=None, mvp=None)` is the entry point. The file has 0 comments and 0 docstrings (§0.5). | +648 lines. SHA-256 `427DD016EBA9F660A3359C70162FEE36D70242ADEC27363796A2324C89D9EE4F` |
| `tests/test_m3_gtm_agent.py` | new | 72 T7 tests, using fake replies only | +1065 lines. SHA-256 `9F734D47C7DD9599E0CB5E151FFB803B01FC58D39B025C2431597CF5AC64B336` |
| `orchestrator.py` | modified, registration only | Imports `GtmAgent` and registers it for stage 7. The `PendingStrategyAgent` docstring was updated. | +1 line, 2 lines changed. `A87005B4…` -> `3A2F41C4…` |
| `tests/test_m3_orchestrator.py` | allowed edit 2 | Restores the GTM placeholder for the placeholder-path test | +1 line. `9B974755…` -> `F4F7F3AE…` |
| `tests/test_m3_swot_agent.py` | allowed edits 1 and 3 | Registry assertion, and the GTM placeholder for one seven-stage test | +1 line, 1 line changed. `DCFFC789…` -> `A4801EAF…` |
| `tests/test_m3_mvp_agent.py` | allowed edits 1 and 3 | Registry assertion, and the GTM placeholder for one seven-stage test | +1 line, 1 line changed. `FD9CF118…` -> `514F3A3A…` |

Nothing changed in `routes/`, `frontend/`, `web/`, `docs/`, `models/`, the plan or `KIRO_*.md`. No model was changed. `GtmDraft` and `GtmResult` already had every field needed, including `Channel.budget_conflict`. Helper scripts are kept only under `.agents/tasks/m3-t7/`: `baseline.ps1`, `probe_digest.py`, `check_test_edits.py` and `verify.py`.

## 2. Registration diff (`orchestrator.py`, against its T6 state)

```diff
+from agents.gtm_agent import GtmAgent                                                         (line 25)
@@ class PendingStrategyAgent:
-    """Stands in for a strategy agent until it is built (plan Task T7). Its stage fails with
+    """Stands in for a strategy agent that is not registered (tests use it). Its stage fails with   (line 164)
@@ STRATEGY_ONLY_STAGES
     StrategyStage(SwotRiskAgent(), STRATEGY_TITLES[STAGE_SWOT]),
     StrategyStage(MvpAgent(), STRATEGY_TITLES[STAGE_MVP]),
-    StrategyStage(PendingStrategyAgent(STAGE_GTM), STRATEGY_TITLES[STAGE_GTM]),
+    StrategyStage(GtmAgent(), STRATEGY_TITLES[STAGE_GTM]),                                      (line 217)
```

The `PendingStrategyAgent` class is kept, because tests use it. Running `check_test_edits.py` reverses the three edits, and the result hashes to the baseline `A87005B4E3AA6ED7793299B4A583ECA3F34541FEBC247DF587C138F92612D7FC` (`matches baseline True`).

## 3. Edits to existing tests

Every edit is within the brief's allowed list, and no assertion was weakened. Both registry assertions remain exact comparisons against the real registry. No other existing test failed or needed a change.

1. **Allowed edit 1.** `tests/test_m3_swot_agent.py::test_the_real_agent_is_registered_for_stage_five`, line 528:
   ```python
   # before
       assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["MvpAgent", "PendingStrategyAgent"]
   # after
       assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["MvpAgent", "GtmAgent"]
   ```
2. **Allowed edit 1.** `tests/test_m3_mvp_agent.py::test_the_real_agent_is_registered_for_stage_six`, line 712:
   ```python
   # before
       assert type(STRATEGY_ONLY_STAGES[2].agent).__name__ == "PendingStrategyAgent"
   # after
       assert type(STRATEGY_ONLY_STAGES[2].agent).__name__ == "GtmAgent"
   ```
3. **Allowed edit 2.** `tests/test_m3_orchestrator.py::test_without_a_registered_agent_a_strategy_stage_fails_plainly`. One line was added at line 140, after the existing `[0]` and `[1]` lines:
   ```python
       monkeypatch.setattr(STRATEGY_ONLY_STAGES[2], "agent", orchestrator.PendingStrategyAgent(STAGE_GTM))
   ```
4. **Allowed edit 3.** `tests/test_m3_swot_agent.py::test_a_seven_stage_run_stores_the_swot_and_its_risks_join_the_digest`. The same line was added at line 534, after the existing `[1]` placeholder line.
5. **Allowed edit 3.** `tests/test_m3_mvp_agent.py::test_a_seven_stage_run_stores_the_mvp_built_on_the_swot_risks`. The same line was added at line 717, after `use_full_pipeline(monkeypatch)`.

**Hash-restoration proof.** I re-ran `check_test_edits.py` in this step. It removes the added lines and restores the old assertions:

```
orchestrator.py:               with the edits undone A87005B4E3AA6ED7793299B4A583ECA3F34541FEBC247DF587C138F92612D7FC  matches baseline True
tests/test_m3_orchestrator.py: with the edits undone 9B9747559EADDBC2629AD132D1A26B7FD389032BF8ACF98DF5A58A45F842A81A  matches baseline True
tests/test_m3_swot_agent.py:   with the edits undone DCFFC7893966913F7B9D488B42658CDE76EA380E0A524AA87D9842DD80EAB8FE  matches baseline True
tests/test_m3_mvp_agent.py:    with the edits undone FD9CF11821C773B8AD87B64BB2A9796FB9FB17267EC254DA7F39B88FB45459B7  matches baseline True
```

Each edited line occurs exactly once in its file.

## 4. Requirement mapping

### 9.3 execution flow

1. **Sufficiency.** `plan_go_to_market` raises `StrategyNotReadyError` before any model call when the idea is missing, or when both market and competitors are missing. The test `test_without_enough_input_the_model_is_not_called[analyses|idea]` asserts `fake.calls == []`.
2. **Digest.** The agent calls `build_digest(idea, constraints, market, competitors, swot=swot, mvp=mvp)` (T3, unmodified). This adds `RSK.n` facts from SWOT risk `R{n}` and `MVP.n` facts from MVP feature `F{n}`.
3. **One structured call.** `call_structured(system, user, GtmDraft, caller=generate_json)`.
4. **Checks in code** (`build_result`): `_positioning`, then `_channels`, `_tactics`, `_phases`, `_messages`, `_limitations` and `_summary`.
5. **Result.** The agent builds `GtmResult` with `StrategyQuality` (constraints come from `apply_constraint_defaults`), then calls `ensure_no_secrets(result)`. `GtmAgent.run` writes `context.gtm`, and each warning is added as `"Planning go-to-market: <warning>"`.

### MVP.* and RSK.* consumption

- When MVP and SWOT results exist, the prompt carries every stored `[MVP.n]` and `[RSK.n]` line. `test_a_seven_stage_run_completes_with_every_strategy_result` checks this per feature (name, tier and rank) and per risk (title). `test_the_prompt_carries_the_digest_with_the_risks_and_features` also covers it.
- Channel drafts link to features through `uses_features` (MVP refs) and to risks through `addresses_risks` (RSK refs). These are stored as `uses_feature_ids` (`F{n}`) and `addresses_risk_ids` (`R{n}`).

### 9.4 content rules

| Rule | Implementation |
|---|---|
| Positioning statement | Code assembles `STATEMENT = "For {for_whom} who {problem}, {product} is a {category} that {key_benefit}. Unlike {alternative}, {differentiator}."` from the stored, shortened parts. `{product}` is `idea.idea_title`. Each part has its whitespace collapsed and trailing ` .;,` stripped, so the stored parts reassemble to the identical stored statement. |
| Differentiator | `differentiator_status = hypothesis` if any cited fact has kind `gap`, or if no cited fact is a `competitor_feature` or `pricing` fact. Otherwise it is `supported`. |
| Channels | Kind, role, cost and speed are enums. Named organisations are handled by the A.0 rule and the shared ref and figure checks. Currency amounts are removed unless a cited fact states them. |
| Ranking | Code sorts by `audience_fit` descending, then `cost_level` (low < medium < high), then speed (days < weeks < months), then the order returned. `priority` is the rank. Only priority 1 gets `start_here = True`. |
| Early customers | `check_items` with duplicates by `tactic`, cut at 5. Fewer than 3 gives a shortfall warning. |
| Launch phases | Phases are sorted in the fixed order `Before launch`, `Launch`, `First 90 days`. A missing phase is never invented, and a warning names it. A repeated phase name keeps the first. Actions are cut at 4. Fewer than 2 actions gives a shortfall warning. Fewer than 2 valid phases raises `LLMInvalidResponseError(MSG_TOO_FEW_PHASES)` (`llm_invalid_response`). |
| Key messages | Overclaim and figure checks, duplicates by message text, cut at 4. Fewer than 2 gives a shortfall warning. |
| Pricing excluded | No code builds a price. The prompt ends with "Do not recommend prices. Do not give budgets in money." A money figure survives only when a cited fact contains it (`test_a_money_figure_stays_only_when_a_cited_finding_states_it[refs0-True / refs1-False]`). |

**Worked example of the positioning statement.** This is the fake reply in `draft()` with idea title "CropScan: AI crop disease detection" and priority segment "Smallholder farmers". It is asserted in `test_a_fake_reply_becomes_the_expected_result`.

| Part | Value |
|---|---|
| target_segment | Smallholder farmers |
| for_whom | smallholder farmers on rain-fed plots |
| problem | spot crop diseases too late to save the harvest |
| category | photo diagnosis app |
| key_benefit | names the disease and a treatment from one photo |
| alternative | free diagnosis apps and phone helplines |
| differentiator | it pairs each diagnosis with treatment advice in the farmer's language |

The assembled statement is: "For smallholder farmers on rain-fed plots who spot crop diseases too late to save the harvest, CropScan: AI crop disease detection is a photo diagnosis app that names the disease and a treatment from one photo. Unlike free diagnosis apps and phone helplines, it pairs each diagnosis with treatment advice in the farmer's language."

This differentiator cites `MKT.12, MKT.16, CMP.25, CMP.27`, which include a gap fact, so its status is `hypothesis`.

### Hypothesis labels

`_differentiator_status` sets the label. It is tested by `test_a_differentiator_resting_on_a_gap_is_a_hypothesis` with six cases: `gap`, `competitor_feature`, `pricing`, `feature_and_gap`, `differentiation_opportunity` and `no_refs`. Only `competitor_feature` and `pricing` alone give `supported`.

### budget_conflict rule (9.5 check 4)

`budget_conflict = (constraints.budget_level == "bootstrapped") and (cost_level == "high")`. The channel is kept, and the plain warning "N channel(s) may be above a bootstrapped budget (names)" is added. It is tested across `bootstrapped`, `small`, `funded` and no constraints.

### Cross-reference removal for F and R ids (9.5 check 2)

`_linked` keeps a ref only if it normalises to `MVP.n` (for features) or `RSK.n` (for risks) and that fact is in the digest. A kept ref is stored as `F{n}` or `R{n}`. The digest numbers come from the stored ids, so every kept id exists in the stored MVP or SWOT result. Anything else is removed with a warning, including bare `F2` or `R1`, an unknown number, or a ref with the wrong prefix. Examples are "removed N link(s) to features that are not in the MVP recommendation (…)" and "… to risks that are not in the risk analysis (…)".

Tests: `test_feature_and_risk_links_that_do_not_resolve_are_removed`, plus the missing-MVP and missing-SWOT tests (all links removed). The seven-stage run asserts that `uses_feature_ids ⊆ mvp ids` and `addresses_risk_ids ⊆ swot risk ids`.

### 9.5 GTM-specific checks

| # | Check | Code |
|---|---|---|
| 1 | Shared checks 1-6 and 8 from 7.5 | See the 7.5 table below |
| 2 | Feature and risk ids are real | `_linked`, described above |
| 3 | Positioning parts are not empty, and the target segment is a market segment name, or the founder's customer without a market | If a required part is empty, or the positioning is removed by the figure or overclaim check, the stage fails with `llm_invalid_response` (`test_an_unusable_positioning_fails_the_stage[empty_part, overclaim, unsupported_figure]`). A non-matching `target_segment` is replaced with the priority segment, or with the founder's first customer when there is no segment data, and the warning `SEGMENT_REPLACED` is added. Matching ignores case and whitespace, and the stored name is kept. |
| 4 | High cost on a bootstrapped budget | `budget_conflict`, described above |
| 5 | Channel count 3-6, duplicates by name removed | `check_items(..., text_of=channel name)` removes duplicates. Fewer than 3 raises `LLMInvalidResponseError(MSG_TOO_FEW_CHANNELS)`. Above 6, `cut_to_limit` removes channels from the bottom of the ranking. |

### 7.5 checks used, with T3 functions

| 7.5 # | Check | T3 function used |
|---|---|---|
| 1 | Refs exist in the digest | `check_item` / `check_items` |
| 2 | Basis consistency | `check_item` / `check_items` |
| 3 | `user_provided` needs IDEA or CON | `check_item` / `check_items` |
| 4 | Unsupported figure | `check_items`, `figure_supported` (phases, key messages, summary and limitations are checked against the whole digest) |
| 5 | Overclaims | `check_items`, `overclaims` |
| 6 | Duplicates | `check_items` (channels by name, tactics by tactic), `remove_duplicates` (key messages) |
| 7 | List limits | `cut_to_limit` (channels 6, tactics 5, actions 4, messages 4, limitations 4) |
| 8 | Length limits | `shorten_fields`, `shorten` |
| 9 | Minimum content | `LLMInvalidResponseError` (`llm_invalid_response`): no usable positioning, fewer than 3 channels, or fewer than 2 phases |
| 10 | Secrets | `ensure_no_secrets(result)` (`test_a_secret_in_the_reply_fails_the_stage`, `test_a_secret_never_reaches_the_stored_result`) |

All repair counts go through `Repairs.warnings()`. Sources come from `inherited_sources(based_on, digest)`. Items with an empty required field are dropped with "removed N point(s) that left a required part empty".

### 9.6 failure and partial cases

| Case | Behaviour | Test |
|---|---|---|
| MVP missing | The stage runs. Warning: "The plan is not tied to a feature set because no MVP recommendation was available." `inputs_missing == ["mvp"]`. | `test_without_an_mvp_the_stage_runs_with_a_notice_and_no_feature_links` and `test_a_run_whose_mvp_failed_still_plans_go_to_market` (seven stages, MVP fails) |
| SWOT missing | The stage runs. Warning: "Risks were not considered when planning go-to-market." | `test_without_a_swot_the_stage_runs_with_a_notice_and_no_risk_links` and `test_a_run_whose_swot_failed_still_plans_go_to_market` |
| Market missing, or a market with no segments | The positioning uses the founder's `target_customers` and its basis is set to `assumption`. Warning: "No customer segments were available, so the positioning is built on the founder's stated customers and is marked as an assumption." | `test_without_the_market_the_positioning_rests_on_the_founders_customers_as_an_assumption` and `test_a_market_without_segments_also_uses_the_founders_customers` |
| Only one analysis finished | The stage runs | `test_one_finished_analysis_is_enough` |
| No analysis finished | The stage is skipped and the run is `partial` | `test_a_run_without_any_finished_analysis_skips_the_stage` |
| Provider failure, invalid after retry, too few channels or too few phases | The stage fails, earlier results are kept and the run is `partial` | `test_a_failed_stage_keeps_the_earlier_results_and_the_run_partial[4 cases]` |

### A.3 prompt rules and delimiters

- `SYSTEM_PROMPT = SHARED_RULES + ROLE`. `SHARED_RULES` is A.0 verbatim, and `ROLE` is "Role: go-to-market advisor for an early-stage product."
- The user part has the A.3 facts line, the digest text inside `<facts>…</facts>` (from T3), the task list, the length limits from the model constants, the JSON schema, and the no-pricing sentence.
- Tests: `test_the_prompt_has_a_system_part_with_the_shared_rules_and_the_role`, `test_the_prompt_carries_the_digest_with_the_risks_and_features`, `test_text_that_tries_to_close_the_data_block_stays_inside_it`.

## 5. T7 tests grouped by the plan's test bullets (72 total)

- **Statement assembly (4):**
  - `test_a_fake_reply_becomes_the_expected_result`
  - `test_the_statement_is_assembled_from_the_stored_parts_and_names_the_priority_segment`
  - `test_positioning_parts_are_trimmed_to_phrases_before_assembly`
  - `test_text_over_its_limit_is_shortened_at_a_word_boundary`
- **Priority segment named (5):**
  - `test_a_target_segment_that_is_not_a_market_segment_becomes_the_priority_segment`
  - `test_another_market_segment_is_kept_with_its_stored_name`
  - `test_an_audience_that_does_not_name_the_segment_becomes_the_segment` (3 cases)
- **Ranking order and single `start_here` (11):**
  - `test_channels_rank_by_fit_then_cost_then_speed_with_a_single_start_here` (2 cases)
  - `test_ties_break_on_cost_then_speed_then_the_order_returned`
  - `test_channels_repeated_by_name_are_removed_and_extra_ones_cut_from_the_bottom`
  - `test_fewer_than_three_channels_fail_the_stage` (5 cases)
  - `test_exactly_three_channels_succeed`
  - `test_a_channel_with_an_empty_required_part_is_dropped`
- **Hypothesis label for gap-based differentiators (6):** `test_a_differentiator_resting_on_a_gap_is_a_hypothesis` (6 cases)
- **Budget conflict flag (4):** `test_a_high_cost_channel_on_a_bootstrapped_budget_is_kept_and_flagged` (4 cases)
- **Invalid feature and risk ids removed (2):**
  - `test_feature_and_risk_links_that_do_not_resolve_are_removed`
  - `test_refs_that_are_not_in_the_digest_are_removed_and_offending_channels_dropped`
- **Fewer than two phases fails (8):**
  - `test_fewer_than_two_launch_phases_fail_the_stage` (5 cases)
  - `test_launch_phases_come_in_their_fixed_order_and_a_repeat_is_removed`
  - `test_two_launch_phases_succeed_and_the_missing_one_is_not_invented`
  - `test_launch_actions_are_cut_to_four_and_a_short_phase_is_reported`
- **Missing MVP, SWOT and market cases (10):**
  - `test_without_an_mvp_…`
  - `test_without_a_swot_…`
  - `test_without_the_market_…`
  - `test_a_market_without_segments_…`
  - `test_a_run_whose_mvp_failed_…`
  - `test_a_run_whose_swot_failed_…`
  - `test_one_finished_analysis_is_enough`
  - `test_without_enough_input_the_model_is_not_called` (2 cases)
  - `test_a_run_without_any_finished_analysis_skips_the_stage`
- **Shared checks, prompt and pipeline (22):**
  - `test_an_unusable_positioning_fails_the_stage` (3 cases)
  - `test_a_money_figure_stays_only_when_a_cited_finding_states_it` (2 cases)
  - `test_early_customer_tactics_are_checked_cut_and_counted`
  - `test_key_messages_are_checked_cut_and_counted`
  - `test_the_summary_and_limitations_are_checked_too`
  - `test_a_secret_in_the_reply_fails_the_stage`
  - `test_a_secret_never_reaches_the_stored_result`
  - `test_the_real_agents_are_registered_for_every_strategy_stage`
  - `test_a_seven_stage_run_completes_with_every_strategy_result`
  - `test_the_stage_reports_its_repairs_under_its_label`
  - `test_the_agent_writes_the_result_and_its_warnings_to_the_context`
  - `test_a_failed_stage_keeps_the_earlier_results_and_the_run_partial` (4 cases)
  - `test_a_strategy_only_job_runs_the_real_stages_on_a_saved_result`
  - `test_the_prompt_has_a_system_part_with_the_shared_rules_and_the_role`
  - `test_the_prompt_carries_the_digest_with_the_risks_and_features`
  - `test_text_that_tries_to_close_the_data_block_stays_inside_it`

The test fixtures are the repo's own synthetic CropScan data. They do not reuse Appendix B values as evidence.

## 6. Verification results (re-run in this step)

Every pytest run used `$env:PYTHONIOENCODING="utf-8"` and `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE`.

| # | Item | Result |
|---|---|---|
| 1 | `tests/test_m3_gtm_agent.py` | **72 passed**, 0 failed, 1 warning (9.35 s) |
| 2 | T3-T6 regression (`test_m3_mvp_agent`, `test_m3_swot_agent`, `test_m3_orchestrator`, `test_m3_digest`, `test_m3_checks`, `test_m3_strict_schema`) | **268 passed**, 0 failed, 1 warning |
| 3 | Full suite | **2112 passed** (2040 baseline + 72 new), 0 failed, 0 errors, 1 warning (StarletteDeprecationWarning: httpx with `starlette.testclient`, the known baseline warning) in 94.11 s |
| 4 | Seven-stage fake run | `test_a_seven_stage_run_completes_with_every_strategy_result` passes. The run is `complete` with no errors and stores swot, mvp and gtm, which survive a JSON round trip. The GTM prompt contains every MVP.n and RSK.n line. The missing-MVP, missing-SWOT and missing-market cases give their warnings and still run (section 4, 9.6). |
| 5 | A-R3 item 1 | `test_the_statement_is_assembled_from_the_stored_parts_and_names_the_priority_segment` rebuilds the statement from the stored parts with an independent test template, and it equals the stored statement. The test also checks that `target_segment == priority_segment.segment_name` and that the statement contains the priority segment. |
| 6 | M1/M2 unchanged | 5 passed: `test_the_existing_stage_sets_are_unchanged`, `test_a_full_stages_run_is_identical_to_before`, `test_a_default_background_run_is_identical_to_before`, `test_an_existing_call_sends_the_same_requests_as_before` (M2 provider-request pin) and `test_without_a_registered_agent_a_strategy_stage_fails_plainly` |
| 7 | Fingerprints | `data/runs.db` and the T1-T6 files match the baseline, apart from the 4 expected changes. Evidence is below. |
| 8 | `git status --porcelain` | The baseline 31 lines plus `?? agents/gtm_agent.py` and `?? tests/test_m3_gtm_agent.py`. No other entries. Branch `main`, HEAD `a098aef0` unchanged. |
| 9 | Secret scan of the 6 changed and new files (AIza, gsk_, tvly-, sk-, Bearer, PRIVATE KEY) | **0 hits** |

### Fingerprint evidence

- **`data/runs.db`** (read with `Get-FileHash` and `Get-Item` only, never opened): `00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D`, 311296 bytes, LastWriteTimeUtc `2026-11-08T15:31:17Z`. This is identical to the expected values and the baseline.
- **`verify.py`, protected T1-T6 files:** 26 unchanged and 4 changed, with no unexpected changes. The 4 changed files are all expected:
  - `orchestrator.py` `A87005B4` -> `3A2F41C4`
  - `tests/test_m3_orchestrator.py` `9B974755` -> `F4F7F3AE`
  - `tests/test_m3_swot_agent.py` `DCFFC789` -> `A4801EAF`
  - `tests/test_m3_mvp_agent.py` `FD9CF118` -> `514F3A3A`

  Each one returns to its baseline hash when its edits are undone (section 3).
- Unchanged files include `models/schemas.py`, `models/strategy_drafts.py`, `agents/strategy_context.py`, `agents/strategy_checks.py`, `agents/notices.py`, `agents/swot_risk_agent.py`, `agents/mvp_agent.py`, `tests/m3_fakes.py` and `.env.example`.
- No `.env` file was opened or printed. No network, live API call or provider credit was used. `app.py` was not started.

## 7. Plan-vs-code conflicts and judgment calls

1. **9.5 check 3 against A-R3 item 1.** Check 3 accepts any market segment name as `target_segment`. A-R3 item 1 says the statement names the priority segment. The code follows the more specific check 3: a reply naming another real segment keeps it (`test_another_market_segment_is_kept_with_its_stored_name`). The prompt asks for the priority segment. The fake run and the A-R3 test both name the priority segment.
2. **The audience must contain the segment.** The sentence form only carries `{for_whom}`. If `for_whom` does not contain every token of the target segment, code replaces it with the segment and adds a warning. This guarantees that the statement names the segment.
3. **Replacement without segment data.** Check 3 says "replaced with the priority segment". When there is no segment data, no priority segment exists, so the founder's first `target_customers` entry is used (9.6).
4. **An unusable positioning fails the stage.** The plan does not say what happens to an empty or removed positioning. `GtmResult.positioning` is required, so the stage fails with `llm_invalid_response` instead of dropping it.
5. **Minimum-content error code.** The code uses `llm_invalid_response`. The plan's wording is "`llm_invalid_output`-class", and this follows the accepted T5/T6 decision.
6. **Budget conflict.** The plan only describes the UI text. The code also adds a plain warning, because notice templates belong to T9.
7. **Channel ids.** `CH{n}` is numbered by the order returned among the kept channels (A.5), so the ids are always CH1..CHk. `priority` is the rank.
8. **`audience_fit` outside 1-5.** Ratings are clamped with a warning. This is not listed in 9.5, but the `Channel` model requires 1-5.
9. **Differentiator refs.** The draft has no separate differentiator refs, so the status uses the positioning's `based_on`.
10. **Phases and key messages carry no refs.** Their figure and overclaim checks run against the whole digest.
11. **Article in the statement.** The template is the plan's verbatim, so it always uses "a", even before a vowel.
12. **Copied helpers.** Private helpers were copied from `mvp_agent.py` instead of imported, following the accepted T5/T6 convention. Warnings are plain strings, because notice templates are T9.

## 8. Unresolved issues and what remains for T8 and later

- **Open issues:** none blocking. The single open point is the check 3 against A-R3 item 1 conflict in section 7, item 1, which needs a product decision if the priority segment must always be named.
- **Not verified here, by design:** A-R3 item 3 ("on every live idea") needs live runs, and no live verification was allowed. A-R3 item 8 (the Go-to-market section rendering at three widths with no axe violation) is frontend work.
- **T8 and later:**
  - routes, API and meta for strategy results
  - notice templates (T9), including the UI text "May be above a bootstrapped budget"
  - derived fields
  - the Advisor and chat
  - Markdown export
  - the React Go-to-market section

T8 was not started.

# Milestone 3, Task T5 (SWOT and Risk Agent, R1): final report

Branch `main`, HEAD `a098aef0408fcef8ec8bd497ee42dbedebc334f7`, nothing committed (as instructed). Review verdict:
APPROVED, no findings (`.agents/tasks/m3-t5/review.json`, `review.md`). This report was written after a fresh,
read-only verification run; no project file was changed in this step.

## 1. Files changed or created

| File | State | Purpose | Diff size |
|---|---|---|---|
| `agents/swot_risk_agent.py` | new | Real stage 5: A.0 + A.1 prompt, one structured LLM call, the 7.5 checks, severity, sort, coverage, quality, draft to `SwotRiskResult`, `SwotRiskAgent` (name `swot_risk`) | +376 lines |
| `tests/test_m3_swot_agent.py` | new | 48 T5 tests (fake provider replies only) | +704 lines |
| `orchestrator.py` | modified | Registration only: stage 5 holds `SwotRiskAgent()` | 3 insertions, 2 deletions vs the pre-T5 copy |
| `tests/test_m3_orchestrator.py` | modified (approved exception) | One added line in one T4 test so it keeps testing the placeholder path for all three stages | +1 line (line 138) |

Nothing changed in `routes/`, `frontend/`, `web/`, `docs/`, `models/schemas.py`, the plan, or `KIRO_*.md`.

### Registration diff (`orchestrator.py` vs `.agents/tasks/m3-t5/baseline/orchestrator.py`)

```diff
@@ -26,6 +26,7 @@ from agents.market_opportunity_agent import STAGE_MARKET
 from agents.notices import STAGE_GTM, STAGE_MVP, STAGE_SWOT, STRATEGY_TITLES
+from agents.swot_risk_agent import SwotRiskAgent
 from agents.web_search_agent import run_web_search
@@ -158,7 +159,7 @@ FULL_STAGES: list[Agent] = [
 class PendingStrategyAgent:
-    """Stands in for a strategy agent until it is built (plan Tasks T5 to T7). Its stage fails with
+    """Stands in for a strategy agent until it is built (plan Tasks T6 and T7). Its stage fails with
@@ -209,7 +210,7 @@ class StrategyStage:
 STRATEGY_ONLY_STAGES: list[Agent] = [
-    StrategyStage(PendingStrategyAgent(STAGE_SWOT), STRATEGY_TITLES[STAGE_SWOT]),
+    StrategyStage(SwotRiskAgent(), STRATEGY_TITLES[STAGE_SWOT]),
     StrategyStage(PendingStrategyAgent(STAGE_MVP), STRATEGY_TITLES[STAGE_MVP]),
     StrategyStage(PendingStrategyAgent(STAGE_GTM), STRATEGY_TITLES[STAGE_GTM]),
```

`FULL_STAGES`, `STAGES` and the M1/M2 stage code are untouched. MVP and GTM still use `PendingStrategyAgent`.

### The one-line edit to `tests/test_m3_orchestrator.py`

`test_without_a_registered_agent_a_strategy_stage_fails_plainly` runs the real `STRATEGY_STAGES` and asserts that all
three strategy stages fail with `MSG_STRATEGY_PENDING`. With the real agent registered, stage 5 would call the LLM, so the
test failed (1979 passed, 1 failed). The coder stopped and asked; the parent approved option A. Added line:

```python
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[0], "agent", orchestrator.PendingStrategyAgent(STAGE_SWOT))
```

Every assertion is unchanged. Checked in this step: the line occurs once, and removing it gives back the baseline
hash `F95BE5A2...AB1C` exactly (`.agents/tasks/m3-t5/check_orch_test_edit.py`).

## 2. Requirement mapping

### 7.3 Execution flow

| Step | Where |
|---|---|
| 1. Sufficiency check, skipped outcome with plain reason | In a run: `StrategyStage.skip_reason` (T4, `orchestrator.py`) skips when the idea is missing or both analyses are missing, with warning `SKIP_NO_ANALYSIS` ("...: skipped because it needs at least one finished analysis."). Direct call: `analyse_swot` raises `StrategyNotReadyError` (`strategy_not_ready`) before building the digest or calling the model. |
| 2. Build digest | `analyse_swot`: `build_digest(idea, constraints, market, competitors)` (T3). An over-cap digest is logged and used as is. |
| 3. Render prompt A.1 with delimiters | `build_prompt(digest) -> (system, user)`; `digest.text` carries `<facts>`/`</facts>` from T3. |
| 4. Structured call with `SwotRiskDraft` | `call_structured(system, user, SwotRiskDraft, caller=generate_json)`: one call plus the existing retry and Gemini-to-Groq path; no searches. |
| 5. Run 7.5 checks | `build_result` (see 7.5 table below). |
| 6. Severity, sort, coverage, gaps, quality | `severity()`, `_risk_order`, `coverage` dict, `coverage_gaps`, `_quality()` in `build_result`. |
| 7. Result and warnings; every repair warns | `Repairs.warnings()` (one aggregated warning per code) plus the agent's own repair warnings; `SwotRiskAgent.run` writes `context.swot` and adds each warning to `context.warnings` prefixed "Assessing strengths and risks: ". |

### 7.4 Content counts and ranges

| Part | Code |
|---|---|
| Strengths, weaknesses, opportunities, threats: 3 to 5 | `QUADRANT_RANGE = (3, SWOT_QUADRANT_MAX)`; the maximum of 5 is enforced by `check_items(maximum=SWOT_QUADRANT_MAX)`; fewer than 3 succeeds with the `FEWER_THAN_ASKED` warning (`_shortfall`). |
| Risks: 6 to 10 | `RISKS_RANGE = (6, RISKS_MAX)`; cut to 10 by `cut_to_limit` after sorting; fewer than 6 gives the same shortfall warning. |
| Internal/external and team rules | In the prompt (A.1 task text); not machine-checked beyond checks 1 to 5. |
| Confidence capped at medium | `CONFIDENCE_CAP = RISK_CONFIDENCES[-1]` (`medium`); a `high` from the model is lowered with one warning (`CONFIDENCE_LOWERED`). |
| Financial risks qualitative | Check 4 (unsupported figure) applies to every risk, financial included. |

### Severity matrix (code)

`LEVEL_SCORES = {"low": 1, "medium": 2, "high": 3}`; `score = likelihood x impact`; `score >= 6` high, `>= 3` medium,
otherwise low. Sort: severity, then impact, then likelihood, all descending (stable). Ids `R1..` are given after sort
and cut, so `RSK.n` equals `R{n}`.

| Likelihood | Impact | Score | Severity |
|---|---|---|---|
| low | low | 1 | low |
| low | medium | 2 | low |
| low | high | 3 | medium |
| medium | low | 2 | low |
| medium | medium | 4 | medium |
| medium | high | 6 | high |
| high | low | 3 | medium |
| high | medium | 6 | high |
| high | high | 9 | high |

All nine are tested (`test_severity_follows_the_matrix[...]`) and stored-and-sorted (`test_every_pair_is_stored_with_its_computed_severity_and_sorted`).

### Category coverage and gaps

`risk_category_coverage` lists all five categories from `RISK_CATEGORIES` (business, market, technical, financial,
operational) with counts, including 0. `coverage_gaps` lists the categories with count 0, in category order. The prompt
tells the model not to invent a risk for a category the facts do not support.

### Draft to result conversion (`build_result`)

1. Drop items with an empty required field (`SWOT_REQUIRED = text`; `RISK_REQUIRED = title, description, mitigation, early_warning_signal`), one warning.
2. Per quadrant: `check_items(..., maximum=5, lengths=SWOT_LENGTHS)`.
3. Risks: `check_items`, sort by `_risk_order`, `cut_to_limit(10)`, `shorten_fields(RISK_LENGTHS)`.
4. Minimum-content rule (below).
5. Limitations: overclaim/figure check, cut to 4, shortened to 200 characters. Summary: overclaim/figure check (blanked if it fails), shortened to 400.
6. `SwotItem` ids `SW1..` across the quadrants in order; `RiskItem` ids `R1..`; computed `severity`; confidence capped; `sources` from `inherited_sources(based_on, digest)`.
7. Coverage, gaps, warnings (repairs, empty parts, lowered confidence, shortfall), `StrategyQuality` (inputs used/missing over idea, market, competitors; constraints provided/assumed from `apply_constraint_defaults`; non-zero basis counts; `grounded_share` to 3 places; `warnings_count`).
8. `analyse_swot` then runs `ensure_no_secrets(result)`.

### 7.5 checks and their T3 functions (`agents/strategy_checks.py`)

| # | Check | T3 function used | Warning |
|---|---|---|---|
| 1 | Ref not in digest removed | `check_item` -> `split_refs` | `strategy_ref_removed` |
| 2 | No valid ref -> basis `assumption` | `check_item` -> `adjusted_basis` | `strategy_basis_adjusted` (counted, one per stage) |
| 3 | `user_provided` needs an `IDEA.*`/`CON.*` ref | `check_item` -> `adjusted_basis` (`FOUNDER_PREFIXES`) | `strategy_basis_adjusted` |
| 4 | Unsupported figure | `check_item` -> `has_unsupported_figure` (uses `check_claim` from `figures.py`); summary and limitations via `figure_supported` against all digest refs | `strategy_figure_removed` |
| 5 | Overclaim phrases (`OVERCLAIM_PHRASES`) | `check_item` -> `overclaims`; summary and limitations via `overclaims` | `strategy_overclaim_removed` |
| 6 | Near-duplicates (overlap >= 0.8) | `check_items` -> `remove_duplicates` (`DUPLICATE_THRESHOLD`) | `strategy_duplicate_removed` |
| 7 | List limits | `cut_to_limit` (quadrants 5, risks 10 after sort so the lowest severity goes, limitations 4) | `strategy_items_cut` |
| 8 | Length limits at a word boundary | `shorten_fields` / `shorten` | `strategy_text_shortened` |
| 9 | Fewer than 4 SWOT items or 0 risks after checks | agent code (`MIN_SWOT_ITEMS = 4`, `MIN_RISKS = 1`) | stage fails with `LLMInvalidResponseError` (`llm_invalid_response`) |
| 10 | Secrets in the result | `ensure_no_secrets` (`secret_findings`: configured key values and `KEY_SHAPES`) | stage fails (base `AppError`) |

### 7.6 failure and partial cases

| Situation | Behaviour | Evidence |
|---|---|---|
| Both analyses missing | Stage skipped by `skip_reason`, run `partial`, no model call, no stage error | `test_a_run_without_any_finished_analysis_skips_the_stage` |
| Provider failure | Stage fails `llm_api_error`, run `partial`, idea/search/market/competitors kept, MVP and GTM still run with `swot=None` | `test_a_failed_stage_keeps_the_earlier_results_and_the_run_partial[provider_failure]` |
| Invalid after structured retry | Stage fails `llm_invalid_response` after 2 calls, run `partial` | `...[invalid_after_retry]` |
| Fewer than target after checks | Succeeds with one shortfall warning; `quality.warnings_count` counts it | `test_fewer_points_than_asked_for_succeeds_with_a_warning` |
| Cancel requested | Honoured before the stage by the orchestrator loop (T4); no T5-specific test | T4: `test_a_cancel_between_strategy_stages_skips_the_rest_and_keeps_what_finished`, `test_a_cancel_between_strategy_stages_of_a_run` |

### Minimum-content failure rule

After all checks: fewer than 4 SWOT items in total, or 0 risks, raises `LLMInvalidResponseError(MSG_TOO_LITTLE)`
("The SWOT and risk analysis had too few usable points after checking, so it was not used."), code
`llm_invalid_response`. Earlier results stay; the run is `partial`. Exactly 4 items and 1 risk is enough (with a
shortfall warning). Items removed by the checks count against the minimum.

### A.1 prompt rules and delimiters

- System part: `SHARED_RULES` is the A.0 text line for line, then `ROLE` = "Role: business analyst producing a SWOT and a risk register."
- User part: "Startup idea and constraints are in the facts (refs starting IDEA and CON).", then `digest.text` (inside `<facts>` and `</facts>`), then the A.1 task text items 1 to 7 verbatim, then length hints and a JSON shape (Gemini gets no response schema, as in the M2 prompts).
- A `</facts>` written into the idea stays inside the single data block (T3 digest escaping), tested.

### RSK.* digest integration

`PipelineResult.swot` is stored by the orchestrator from `context.swot`. T3's `build_digest(..., swot=...)` turns each
risk into `RSK.n` facts ("Risk (category; likelihood, impact, severity): title ...") with the risk's basis and inherited
sources. Tested in `test_a_seven_stage_run_stores_the_swot_and_its_risks_join_the_digest`: `RSK.1..RSK.6` match
`R1..R6`, sources match, and a digest built without `swot` has no risk facts.

## 3. T5 tests grouped by the plan's test bullets (48 collected)

| Plan bullet | Tests |
|---|---|
| A fake model reply produces the expected result | `test_a_fake_reply_becomes_the_expected_result`, `test_the_prompt_carries_the_digest_of_the_same_inputs`, `test_one_finished_analysis_is_enough`, `test_the_agent_writes_the_result_and_its_warnings_to_the_context`, `test_a_strategy_only_job_runs_the_real_stage_on_a_saved_result`, `test_the_real_agent_is_registered_for_stage_five`, `test_a_seven_stage_run_stores_the_swot_and_its_risks_join_the_digest` |
| Severity matrix for all nine pairs | `test_severity_follows_the_matrix` x9 (`low-low-low` ... `high-high-high`), `test_every_pair_is_stored_with_its_computed_severity_and_sorted` |
| Category coverage and gaps | `test_category_coverage_counts_every_category_and_lists_the_gaps` |
| Each check with a planted offender | 1: `test_a_ref_that_is_not_in_the_digest_is_removed`; 2: `test_an_item_with_no_valid_ref_becomes_an_assumption`; 3: `test_a_founder_point_without_an_idea_or_constraint_ref_becomes_an_interpretation`; 4: `test_a_risk_with_a_figure_no_cited_finding_states_is_removed`; 5: `test_a_point_that_promises_an_outcome_is_removed`; 6: `test_a_repeated_point_is_removed`; 7: `test_points_beyond_the_limits_are_cut_lowest_severity_last`; 8: `test_text_over_its_limit_is_shortened_at_a_word_boundary`; 10: `test_a_secret_in_the_reply_fails_the_stage`, `test_a_configured_key_value_in_the_reply_fails_the_stage`, `test_a_secret_never_reaches_the_stored_result`; extra repairs: `test_a_high_confidence_is_capped_at_medium`, `test_a_point_with_an_empty_required_part_is_removed`, `test_the_summary_and_limitations_are_checked_too`, `test_warnings_are_aggregated_once_per_code`, `test_the_stage_reports_its_repairs_under_its_label` |
| Minimum-content failure | `test_too_little_content_fails_the_stage[three_swot_items]`, `[no_risks]`, `test_content_removed_by_the_checks_counts_against_the_minimum`, `test_four_swot_items_and_one_risk_are_enough`, `test_fewer_points_than_asked_for_succeeds_with_a_warning`, `test_a_failed_stage_keeps_the_earlier_results_and_the_run_partial[too_little_content]` |
| Sufficiency skip | `test_without_enough_input_the_model_is_not_called[analyses]`, `[idea]`, `test_a_run_without_any_finished_analysis_skips_the_stage` |
| Provider failure leaves earlier results and run partial | `test_a_failed_stage_keeps_the_earlier_results_and_the_run_partial[provider_failure]`, `[invalid_after_retry]` |
| Prompt contains the digest, rules and delimiters | `test_the_prompt_has_a_system_part_with_the_shared_rules_and_the_role`, `test_the_prompt_has_a_user_part_with_the_digest_inside_its_delimiters`, `test_text_that_tries_to_close_the_data_block_stays_inside_it` |

## 4. Verification run in this step

| # | Check | Command | Result |
|---|---|---|---|
| 1 | T5 tests | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_swot_agent.py` | **48 passed**, 0 failed, 1 warning |
| 2 | T3/T4 regression | `... tests/test_m3_orchestrator.py tests/test_m3_digest.py tests/test_m3_checks.py tests/test_m3_strict_schema.py` | **160 passed**, 0 failed, 1 warning. `test_m3_digest.py`, `test_m3_checks.py`, `test_m3_strict_schema.py` unedited; `test_m3_orchestrator.py` has the approved one-line edit (Section 1). |
| 3 | Full suite | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE` | **1980 passed** (1932 + 48), 0 failed, 1 warning |
| 4 | Fake-backed seven-stage run | `test_a_seven_stage_run_stores_the_swot_and_its_risks_join_the_digest` | passed: run `partial` with only the MVP and GTM placeholder errors; `swot` stored with 6 risks, survives a JSON round trip; digest with it has `RSK.1..RSK.6` |
| 5 | M1/M2 unchanged | `test_the_existing_stage_sets_are_unchanged`, `test_a_full_stages_run_is_identical_to_before`, `test_a_default_background_run_is_identical_to_before`, `test_an_existing_call_sends_the_same_requests_as_before` (M2 provider-request pin), plus the edited placeholder test and item 4's test | 6 passed |
| 6 | Fingerprints | `.agents/tasks/m3-t5/final_verify.ps1` | see Section 5 |
| 7 | `git status --porcelain` | | baseline 27 lines plus `?? agents/swot_risk_agent.py`, `?? tests/test_m3_swot_agent.py` (29 lines). `orchestrator.py` and `tests/test_m3_orchestrator.py` were already listed (` M` and `??`). |
| 8 | Secret scan of `orchestrator.py`, `agents/swot_risk_agent.py`, `tests/test_m3_swot_agent.py`, `tests/test_m3_orchestrator.py` | patterns `AIza...`, `gsk_...`, `tvly-...`, `sk-...`, `Bearer <token>`, `PRIVATE KEY` | **0 hits**. Planted test keys are built from string parts. |

The one warning in every run is the Starlette/httpx `StarletteDeprecationWarning` from `fastapi.testclient`, present
before T5.

## 5. Fingerprint evidence

`data/runs.db` (Get-FileHash / Get-Item only, never opened):

| | Expected | Now |
|---|---|---|
| SHA-256 | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D |
| Size | 311296 | 311296 |
| LastWriteTimeUtc | 2026-11-08T15:31:17Z | 2026-11-08T15:31:17Z |

T1 to T4 file hashes against `baseline.md`: 26 files checked, 24 unchanged, 2 changed:

| File | Baseline | Now | Reason |
|---|---|---|---|
| `orchestrator.py` | 7695055539318F35BC467C06A44CF9E1B0FED20B8C55481DE4868A7F364A1061 | 0B14E8D216EE43779F83F21AC88271D58D0F84AB6D76E312AE74FBD630159F2D | expected: registration |
| `tests/test_m3_orchestrator.py` | F95BE5A2D31B617370918BE342E36CD03C4AF895806930DD209357937C60AB1C | BEB81D6811E40C0A4D0091230249B27F1796A20CED75D1FD974BF01B8E684A4E | approved one-line edit; removing it restores the baseline hash |

Unchanged: `.env.example`, `config.py`, `models/api.py`, `models/schemas.py`, `utils/errors.py`, `models/chat.py`,
`models/strategy_drafts.py`, `tests/test_m3_schemas.py`, `utils/run_store.py`, `utils/chat_store.py`,
`tests/test_m3_store_migration.py`, `tests/test_run_store.py`, `agents/strategy_context.py`, `agents/strategy_checks.py`,
`tests/test_m3_digest.py`, `tests/test_m3_checks.py`, `tests/test_m3_strict_schema.py`, `agents/base.py`,
`agents/notices.py`, `utils/deadline.py`, `utils/groq_client.py`, `utils/llm_client.py`, `utils/run_manager.py`,
`tests/m3_fakes.py`.

The baseline copy `.agents/tasks/m3-t5/baseline/orchestrator.py` still hashes to 7695...1061. New files:
`agents/swot_risk_agent.py` 020BDAE6E618DBE7426AF73A55216E5DF8313F58B35F004696E776A84D4F5B49,
`tests/test_m3_swot_agent.py` 32F5F5E91EF0C29AF2B95C4E146C4BD6A4E607D2BA613C866DFFB274F5190058.

## 6. Plan-vs-code conflicts

1. **7.3 step 1 "return a skipped outcome".** Skipping belongs to the stage (`StrategyStage.skip_reason`, T4), which runs first in a pipeline. The agent, called directly, raises `StrategyNotReadyError` instead and never spends an LLM call.
2. **7.5 check 9 names an "`llm_invalid_output`-class code".** The existing code is `llm_invalid_response` (`LLMInvalidResponseError`); T5 uses it.
3. **T5 entry vs the brief's "only orchestrator.py changes among T1-T4 files".** Registering the real agent broke a T4 test that relied on the SWOT placeholder; resolved by the approved one-line monkeypatch (Section 1). The brief's items 2 ("unedited") and 6 ("unchanged except orchestrator.py") hold for every file except this one.
4. **Limits the plan does not state.** Limitation length 200 characters (chosen to match other short-text limits); summary 400 from `STRATEGY_SUMMARY_MAX`.
5. **Repairs beyond 7.5.** Confidence `high` capped to `medium` (7.4 rule), and items with an empty required field dropped (otherwise a `NonEmptyStr` validation error would fail the whole stage). Each emits one warning.

## 7. Unresolved issues and what remains

Open issues:
- The approved edit to `tests/test_m3_orchestrator.py` is the only change to a T1-T4 file besides `orchestrator.py`; flag it in your review.
- Over-cap digest (only when protected facts alone exceed `STRATEGY_DIGEST_MAX_CHARS`) is logged and sent as is; T3 left this to T5. No live sizing data yet.
- The 7.4 internal/external and team rules are enforced only through the prompt; live outputs need review (A-R1 items 1, 3, 5) in T14.
- Cancel during the SWOT call itself is not interrupted; cancel is honoured between stages, as for the other stages.
- No live run was made; all evidence is fake-backed.

Remaining for T6 and later: T6 MVP agent (consumes `RSK.*`, replaces `PendingStrategyAgent(STAGE_MVP)`), T7 GTM agent,
T8 summary, notices and Markdown export of strategy, T12 API freeze, UI tasks (Strategy tab, A-R1 item 8), and T14 live
verification of R1 on the three ideas.

## 8. Helper files (bookkeeping only, under `.agents/tasks/m3-t5/`)

`final_verify.ps1` (db fingerprint, hash comparison, secret scan) and `check_orch_test_edit.py` (one-line edit proof)
were added in this step. `probe_digest.py` and `final_checks.ps1` came from the coder step.

# 12. Milestone 3 Test Report

**Project:** Development of AI Based Startup Idea Validator with Market Analysis Assistance

**Scope:** Milestone 3 (`MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md`): the SWOT and risk, MVP and
go-to-market stages, the Advisor, and their integration. How they are built:
[docs/11](11_milestone3_strategy_and_advisor.md).

This report keeps **automated test evidence** and **live validation** apart. Every automated result
below was produced by running the suite with fakes. Live results are written here only from what a
real run leaves behind. None exists yet, so every live check reads **Not executed**.

---

## 1. Summary

| Area | Command | Result |
|:---|:---|:---|
| Backend | `python -m pytest` | **2454 passed**, 0 failed, 1 warning |
| Front-end unit and component tests | `npm test` (in `web/`) | **477 passed** in 35 files |
| TypeScript | `npm run typecheck` | Clean, for the application and for the browser tests |
| Production build | `npm run build` | Built. Entry chunk **268.79 kB**, 85.56 kB gzipped |
| Browser tests | Playwright, specs named on the command line in three runs (section 2.3) | **288 passed** in six specs. The ui_v2 screenshot spec (81 tests) was not run |
| Accessibility | `accessibility-m3.spec.ts`, `accessibility.spec.ts` | **0 serious or critical** axe violations: 14 new screens and the 27 earlier ones, each at three widths |
| Secret scan | Section 2.5 | **0 hits** |
| Live checks L-1 to L-5 | Section 4 | **Not executed** |

The backend figures are from 14 November 2026; the front-end, build and browser figures from
13 November 2026. No source, test or configuration file changed after those runs. That was checked
against the files' modification times before this report was written.

---

## 2. Automated tests

All tests use deterministic fakes. In the backend, `tests/conftest.py` blocks every non-local socket
and sets placeholder keys, so no test can reach a model or the search API. In the front end, MSW
answers every request and fails any test that reaches an unmocked address. In the browser tests,
`web/e2e/mockApi.ts` answers every call and throws if anything tries to start a run.

### 2.1 Backend

`python -m pytest`: **2454 passed**, 0 failed, 0 skipped, in 64 files. That is the 1,636 tests from
before Milestone 3, all still present and passing, plus 818 new tests in 18 files. The one warning is
Starlette's `httpx` deprecation notice, which predates Milestone 3.

| File | Tests | What it covers |
|:---|---:|:---|
| `tests/test_m3_schemas.py` | 124 | Settings and their bounds, the new error classes, the stored, draft and chat models and their limits; every saved fixture, every saved Milestone 2 result and a read-only copy of the stored runs still validate; the OpenAPI schema; no import cycle |
| `tests/test_m3_store_migration.py` | 12 | An old-schema file gains the columns and the chat table; a second open changes nothing; chat and a strategy job on an old row; deleting a run deletes its chat; a key in a question or in the constraints is not stored; the app import creates no database; the real database is not touched |
| `tests/test_m3_digest.py` | 31 | Refs are the same for the same input; source keys; trimming order; delimiters; the saved live fixtures fit under the cap |
| `tests/test_m3_checks.py` | 69 | Each shared check with a planted offender; warning builders; secret detection |
| `tests/test_m3_strict_schema.py` | 20 | Every draft model through the strict schema the Groq path uses |
| `tests/test_m3_orchestrator.py` | 40 | Stage order; `complete` versus `partial`; skips; cancel and time limit between strategy stages; strategy jobs on saved results; four-stage runs identical to before |
| `tests/test_m3_swot_agent.py` | 48 | Severity for all nine pairs; category coverage and gaps; each check; minimum content; failures; the prompt |
| `tests/test_m3_mvp_agent.py` | 60 | Scores and ranks recomputed; capacity; tiers; defaults marked as assumed; over capacity; founder features kept; risk links; failures |
| `tests/test_m3_gtm_agent.py` | 74 | The statement and the priority segment; channel order and a single "start here"; the hypothesis label; budget conflict; links; launch phases; missing MVP, SWOT or segments |
| `tests/test_m3_runs_api.py` | 39 | `include_strategy` and `constraints` on `POST /api/runs`; the default request answers exactly as before; `has_strategy`; the `/api/meta` blocks |
| `tests/test_m3_strategy_route.py` | 38 | Every rule of `POST /api/runs/{run_id}/strategy`; `missing` versus `all` |
| `tests/test_m3_no_search.py` | 4 | A spy proves that strategy stages and strategy jobs make no search |
| `tests/test_m3_derived_notices.py` | 42 | Summary and verify-next lines; one notice per code per stage; no field path in any message; `evidence_strength` unchanged |
| `tests/test_m3_report.py` | 12 | The default Markdown is byte-identical to a stored snapshot; strategy sections on `full=True`; no Advisor content in the export |
| `tests/test_m3_advisor.py` | 76 | Routing; context and its cap; the history window; each reply check with planted replies; the marker; out-of-scope and missing-section answers; suggestions; no search |
| `tests/test_m3_chat_api.py` | 39 | Every limit and error code; the thread survives a reload; clear; delete; nothing stored on a failure; availability |
| `tests/test_m3_no_secrets.py` | 52 | Planted fake keys never reach a prompt, a row, a response or a log; the contract script passes on a synthetic result and flags each of 36 planted violations |
| `tests/test_m3_live_scripts.py` | 38 | The three live scripts end to end with `--fake`; the `--yes` guard; missing keys; failures; call counting |
| **Milestone 3 total** | **818** | |

**Existing test changed.** One of the 1,636: `tests/test_run_store.py`, where the exact set of stored
columns gained `constraints_json` and `include_strategy`. It is one line and still an exact
comparison.

### 2.2 Front end

| Check | Command | Result |
|:---|:---|:---|
| Unit and component tests | `npm test` | **477 passed** in 35 files: the 295 from before Milestone 3 in 20 files, and 182 new in 15 files. No line of the output reports a request that MSW did not handle |
| TypeScript | `npm run typecheck` | Clean |
| Production build | `npm run build` | Entry chunk 268.79 kB, 85.56 kB gzipped (before Milestone 3: 268.78 kB, 85.54 kB). The two new tabs are imported by the run page, so they load with its chunk (141.46 kB, 35.31 kB gzipped) |

| New file | Tests | What it covers |
|:---|---:|:---|
| `src/features/new-validation/ConstraintsPanel.test.tsx` | 16 | The switch and the resources panel; limits from `/api/meta`; the exact request body; "Edit and re-run" |
| `src/features/run/strategyRun.test.tsx` | 11 | Four or seven tracker rows; seven tabs and the arrow keys; polling after a strategy request |
| `src/features/advisor/useChat.test.tsx` | 8 | Thread, send with abort, clear |
| `src/lib/strategy.test.ts` | 4 | Plain labels; the synthetic fixture's shape |
| `src/features/strategy/StrategyTab.test.tsx` | 19 | Header block; section list; generate, retry and regenerate requests; no ids or field names on screen |
| `src/features/strategy/RisksSection.test.tsx` | 9 | Severity counts; coverage chips; table or cards; sort; detail |
| `src/features/strategy/SwotSection.test.tsx` | 6 | Quadrants, basis chips, citations, summary |
| `src/lib/strategyClaims.test.ts` | 5 | Strategy claims in the source drawer; the default claim list unchanged |
| `src/features/strategy/MvpSection.test.tsx` | 21 | Capacity; tiers in backend order; cards; assumed chips; the ranking disclosure |
| `src/features/strategy/GtmSection.test.tsx` | 28 | Statement as returned; channels and "Start here"; meters; launch plan; messages; missing inputs |
| `src/features/results/OverviewStrategyTile.test.tsx` | 8 | The tile's three states; the strategy summary lines |
| `src/features/advisor/AdvisorTab.test.tsx` | 29 | Starter questions; thread; composer keys; pending and cancel; errors keep the draft; limits; clear; unavailable states |
| `src/features/advisor/advisorRun.test.tsx` | 8 | "Ask the advisor about this" from each section; the draft survives tab changes; the shared drawer |
| `src/lib/noRawHtml.test.ts` | 2 | No raw-HTML prop anywhere in `web/src` |
| `src/features/run/exportRun.test.tsx` | 8 | Print with Strategy and without Advisor; the Markdown request; JSON with the new fields; "Edit and re-run" end to end |
| **Total** | **182** | |

**Existing test changed.** `src/features/run/RunPage.test.tsx`: the expected tab list grew from five
to seven names and the arrow-key cycle gained Strategy and Advisor (plan Section 20.4). One of its
tests, `moves between tabs with the arrow keys`, gained two MSW handlers (`/api/meta` and the chat
thread), as setup only, for the requests the new tabs make.

### 2.3 Browser tests

Playwright in Chromium at 390, 820 and 1440 px, against the production build.

| Spec | Tests | Result | What it checks |
|:---|---:|:---|:---|
| `e2e/screens-m3.spec.ts` (new) | 42 | 42 passed | The 14 new screens at three widths: a screenshot into `docs/assets/ui_v3/`, no sideways scroll, 44 px targets on the new controls at 390 px, and no request that starts a run or a strategy job |
| `e2e/accessibility-m3.spec.ts` (new) | 42 | 42 passed | axe (WCAG 2.0 and 2.1, levels A and AA) on the 14 screens: 0 serious or critical, and no moderate or minor violation reported |
| `e2e/keyboard-m3.spec.ts` (new) | 60 | 60 passed | Seven tabs by arrow keys, the resources panel, the composer, a suggested question, the clear and regenerate confirmations (18); reduced motion on every new screen (42) |
| `e2e/focus-m3.spec.ts` (new) | 42 | 42 passed | A Tab walk through each screen's new controls: every stop shows a focus ring and every listed control is reached |
| `e2e/accessibility.spec.ts` | 81 | 81 passed | The 27 earlier screens, against the extended mock |
| `e2e/keyboard.spec.ts` | 21 | 21 passed | The earlier keyboard and reduced-motion tests |
| `e2e/screenshots.spec.ts` | 81 | **Not run** | It rewrites `docs/assets/ui_v2/`, so it was left alone and those 81 images still show the interface before Milestone 3 |
| **Total** | **369** | **288 passed, 81 not run** | |

`npm run test:e2e` runs all seven specs, including the screenshot spec. The results above therefore
come from three runs that named their specs on the command line, never from the whole suite:
`screens-m3.spec.ts` (42 tests); the four accessibility and keyboard specs, new and earlier,
together (204 tests); and `focus-m3.spec.ts` (42 tests). The ui_v2 screenshot spec was in none of
them. The new screens are listed in
[docs/10, section 11](10_ui_design_system.md#11-milestone-3-strategy-and-advisor-screens).

Text fields were not part of the 44 px measurement: the plan's list is buttons, radios, selects and
chips. The new "Launch region" field is 42 px tall, the same as every text field on the review step.

### 2.4 Offline contract check

`scripts/check_m3_contracts.py <file.json>` checks a saved result against the strategy rules: refs,
basis, inherited sources, figures, overclaims, duplicates, secrets, counts, severity and order,
coverage, scores and ranks, capacity and tiers, founder features, links, the statement and the
segment, channel order and budget conflicts. It makes no API call and opens no database. Its tests
are in `tests/test_m3_no_secrets.py`, and `tests/test_m3_live_scripts.py` runs it on the fake outputs
of the live scripts. The three saved Milestone 2 results have no strategy, so it has nothing to check
in them.

### 2.5 Secret scan

Every tracked and untracked file that Git does not ignore, including the workflow's own notes,
scanned on 14 November 2026 for Google, Gemini, Tavily, Groq and other secret-key prefixes, bearer
tokens and private-key blocks. `.env` files and `data/runs.db` are ignored by Git, so they were not
listed and not opened; the scanner would also skip them by name.

| Files listed | Text files scanned | Binary files skipped | Hits |
|---:|---:|---:|---:|
| 838 | 701 | 137 | **0** |

---

## 3. What the tests cover

The acceptance criteria of plan Sections 7.7, 8.7, 9.7, 10.8 and 21. "Live" marks the part of a
criterion that only a real run can show; section 4 has its status.

| Criterion | Covered by | Live |
|:---|:---|:---|
| A-R1.1 Quadrants within range, or a warning | `test_fewer_points_than_asked_for_succeeds_with_a_warning` | On each live idea |
| A-R1.2 Basis, refs and inherited sources | `test_a_ref_that_is_not_in_the_digest_is_removed`, `test_an_item_with_no_valid_ref_becomes_an_assumption`; contract rules `ref_unknown`, `sources_mismatch` | |
| A-R1.3 Risks across the categories, gaps stated | `test_category_coverage_counts_every_category_and_lists_the_gaps` | On each live idea |
| A-R1.4 Every risk has its parts and a computed severity | `test_severity_follows_the_matrix`, `test_every_pair_is_stored_with_its_computed_severity_and_sorted`, `test_a_point_with_an_empty_required_part_is_removed` | |
| A-R1.5 No unsupported figure or overclaim | `test_a_risk_with_a_figure_no_cited_finding_states_is_removed`, `test_a_point_that_promises_an_outcome_is_removed` | Review of live outputs |
| A-R1.6 No secret in the output | `test_a_secret_in_the_reply_fails_the_stage`, `test_a_secret_never_reaches_the_stored_result`, `tests/test_m3_no_secrets.py` | |
| A-R1.7 A failed or skipped stage keeps Milestone 2 results, run `partial` | `test_a_failed_stage_keeps_the_earlier_results_and_the_run_partial`, `test_a_run_without_any_finished_analysis_skips_the_stage` | |
| A-R1.8 Strategy tab at three widths | `strategy-swot-risks` in the browser specs | |
| A-R2.1 Ranked by the formula | `test_scores_and_ranks_recompute_from_the_stored_ratings` | |
| A-R2.2 In-scope and deferred sets, `over_capacity` correct | `test_features_fill_the_capacity_in_rank_order_and_the_walk_stops_at_the_first_misfit`, `test_essential_features_over_capacity_all_stay_in_the_first_release` | On each live idea |
| A-R2.3 Every founder feature appears | `test_every_founder_feature_appears_even_when_the_reply_has_none`, `test_a_missing_founder_feature_is_appended_as_later` | |
| A-R2.4 Ratings, effort, rationale; defaults shown as assumed | `test_missing_constraints_run_on_defaults_marked_as_assumed`; MvpSection test "shows a chip for each resource the plan assumed, with the value used" | |
| A-R2.5 Metrics without invented figures | `test_success_metrics_are_checked_cut_and_counted`, `test_success_metric_targets_with_an_unsupported_figure_lose_the_target_not_the_metric` | |
| A-R2.6 Linked risk titles in the UI | MvpSection test "names the risks a feature reduces, taken from the SWOT result" | |
| A-R2.7 Missing SWOT, missing constraints, over capacity | `test_without_a_swot_the_stage_runs_with_a_notice_and_no_risk_refs`, `test_over_capacity_is_a_result_not_an_error`, `test_each_strategy_warning_becomes_its_specified_notice` | |
| A-R2.8 MVP section at three widths | `strategy-mvp` in the browser specs | |
| A-R3.1 Statement assembled by code, names the priority segment | `test_the_statement_is_assembled_from_the_stored_parts_and_names_the_priority_segment`, `test_another_market_segment_is_replaced_by_the_priority_segment` | |
| A-R3.2 3 to 6 ranked channels, one "start here" | `test_channels_rank_by_fit_then_cost_then_speed_with_a_single_start_here`, `test_fewer_than_three_channels_fail_the_stage` | |
| A-R3.3 Tactics and three launch phases | `test_early_customer_tactics_are_checked_cut_and_counted`, `test_two_launch_phases_succeed_and_the_missing_one_is_not_invented` | On each live idea |
| A-R3.4 A gap-based differentiator is a hypothesis | `test_a_differentiator_resting_on_a_gap_is_a_hypothesis` | |
| A-R3.5 No currency amount unless a cited finding has it | `test_a_money_figure_stays_only_when_a_cited_finding_states_it` | |
| A-R3.6 Links valid or removed with a warning | `test_feature_and_risk_links_that_do_not_resolve_are_removed` | |
| A-R3.7 Missing MVP, SWOT or segments | `test_without_an_mvp_the_stage_runs_with_a_notice_and_no_feature_links`, `test_without_a_swot_the_stage_runs_with_a_notice_and_no_risk_links`, `test_a_market_without_segments_also_uses_the_founders_customers`; GtmSection test "says plainly when the plan was made without the risks or the MVP" | |
| A-R3.8 Go-to-market section at three widths | `strategy-gtm` in the browser specs | |
| A-R4.1 Each section answered with a citation, or "not in your results" | `test_a_matched_section_is_expanded_in_full`, `test_a_question_about_a_missing_section_says_so_without_a_model_call` | L-3 |
| A-R4.2 An unrelated question gets the out-of-scope message | `test_an_out_of_scope_question_gets_the_standard_message` | L-3 |
| A-R4.3 An injection attempt reveals no instructions | `test_a_reply_that_leaks_the_canary_or_the_instructions_is_replaced_by_the_refusal`, `test_each_question_gets_a_new_canary` | L-3 |
| A-R4.4 The thread survives a reload and goes with the run | `test_the_thread_survives_a_reload`, `test_deleting_the_run_deletes_its_thread` | |
| A-R4.5 Limits enforced | `test_the_twenty_sixth_question_is_refused_until_the_thread_is_cleared`, `test_an_invalid_message_is_refused_with_chat_message_invalid`, `test_one_question_in_flight_per_run` | |
| A-R4.6 A failure never stores half an exchange | `test_a_provider_failure_stores_nothing`, `test_an_unexpected_failure_stores_nothing_and_frees_the_run` | |
| A-R4.7 A basis chip on every paragraph; `sourced` only on sourced facts | `test_a_sourced_paragraph_must_rest_only_on_sourced_facts`; AdvisorTab test "gives every advisor paragraph a basis chip, its citation chips and where it came from" | |
| A-R4.8 Works on a run without strategy | `test_a_run_without_strategy_answers_about_the_market_and_says_strategy_is_missing` | |
| A-R4.9 Keyboard, announcements, axe | The composer test in `keyboard-m3.spec.ts`; AdvisorTab test "announces once that the advisor replied"; the five Advisor screens in the browser specs | |
| X-1 Existing routes and Streamlit unchanged | `test_a_default_run_answers_exactly_as_before`, `test_the_default_report_is_byte_identical_to_the_stored_snapshot`; the only change under `frontend/` is the `full=True` path | |
| X-2 A run without strategy behaves as before | `test_a_default_run_answers_exactly_as_before`, `test_a_full_stages_run_is_identical_to_before` | |
| X-3 Every saved result loads | `test_every_saved_pipeline_result_validates_unchanged`, `test_every_saved_run_fixture_validates_unchanged`, `test_every_result_in_a_copy_of_the_stored_runs_validates_unchanged` | |
| X-4 Honest status | `test_a_seven_stage_run_runs_in_order_and_is_complete`, `test_a_failed_strategy_stage_makes_the_run_partial_and_keeps_everything_else` | |
| X-5 No search in strategy or the Advisor | `tests/test_m3_no_search.py`, `test_the_advisor_makes_no_search_call` | |
| X-6 No secret anywhere | `tests/test_m3_no_secrets.py`; the scan in section 2.5 | |
| X-7 `evidence_strength` unchanged | `test_evidence_strength_is_equal_with_and_without_strategy` | |
| X-8 Every statement has a basis, none `sourced`, refs valid | `test_a_strategy_item_labelled_sourced_fails_the_schema`; the checks above | |
| X-9 No unsupported figure or overclaim stored | The check tests above | Review of live outputs |
| X-10 Accessibility and responsive rules, measured | Section 2.3 | |
| X-11 Strategy on a saved run, and questions about it | `tests/test_m3_strategy_route.py`, `tests/test_m3_chat_api.py`; StrategyTab test "explains what generating does and costs, and sends the request when asked" | L-2, L-4 |
| X-12 Counts in documents measured, or "Not executed" | This report | |

---

## 4. Live validation

Live runs spend real API credits and are run by hand, never by the assistant. Preconditions from the
plan: a new Tavily key in place, `.env` filled in, and the backend running for the walkthrough. The
scripts do nothing without `--yes`, never print a key, and write into `docs/test_runs_m3/`, whose
[README](test_runs_m3/README.md) explains every file. They were tested only with `--fake`.

| Check | Command | What to record | Credits | Status |
|:---|:---|:---|:---|:---|
| L-1 Strategy on three ideas: agritech, fintech cash flow, foodtech surplus | `python scripts/run_m3_live.py --yes` | Status; seconds per stage; points per quadrant; risks by category; MVP in and out of scope; channels; warnings; rule violations | 3 full runs, 7 LLM calls each plus the searches of stages 1 to 4 | **Not executed** |
| L-2 Strategy on a saved run | `python scripts/run_m3_retro_live.py --yes` (default: `docs/test_runs_m2/agritech.json`) | The same, with no search; seconds compared with L-1 | 3 LLM calls | **Not executed** |
| L-3 Advisor | `python scripts/check_advisor_live.py --yes` (default: the L-1 agritech result) | The eight fixed questions: market, competitor, a risk, MVP priority, first channel, out of scope, an injection attempt, a missing section | 7 LLM calls; the missing-section question is answered in code | **Not executed** |
| L-4 UI walkthrough | The React interface in a browser | Review step with resources; seven-stage tracker; Strategy tab; Advisor; Markdown export; print preview | 1 full run | **Not executed** |
| L-5 Provider fallback | Only if Gemini quota errors happen on their own | Whether Groq took over | none extra | **Not executed** |

### 4.1 Live results

**Not executed.** No live strategy run, retro run or Advisor check exists, so there is no result to
report. The table will hold, per idea: status, total and strategy seconds, LLM calls, points per
quadrant, risks and gaps, features in the first release, channels, warnings and rule violations.

### 4.2 Review checklist per live output

To be filled in from the real outputs (plan Section 20.7). None is ticked.

| # | Check | Outcome |
|---:|:---|:---|
| 1 | Every SWOT item and risk is understandable without outside knowledge and relates to the idea | **Not executed** |
| 2 | No competitor, organisation, price or statistic appears that is not in the market or competitor results | **Not executed** |
| 3 | Risks cover the categories; gaps are stated | **Not executed** |
| 4 | The MVP list contains the founder's own features; deferred reasons make sense; assumptions are visible | **Not executed** |
| 5 | The positioning sentence reads naturally and the differentiator label fits | **Not executed** |
| 6 | Channels are plausible for the segment and region; the first experiment is concrete | **Not executed** |
| 7 | Advisor answers cite results; the out-of-scope and injection questions are refused cleanly | **Not executed** |
| 8 | Timing: total and strategy seconds, against the plan's estimate | **Not executed** |

The plan's estimate for item 8 is 15 to 35 seconds per strategy stage, 45 to 105 seconds added per
run. It is an estimate and has not been measured.

### 4.3 What has run live so far

Nothing from Milestone 3. Before it began, the four-stage pipeline was run live from the command
line on 27 October 2026 ([docs/09](09_milestone2_test_report.md)), and five validations were run
from the React interface and saved in `data/runs.db`
([docs/10, section 9](10_ui_design_system.md#9-status-and-what-is-unverified)). None of these had
strategy stages, because Milestone 3 did not exist yet.

---

## 5. Not verified

- Every live check in section 4, and the parts of the acceptance criteria marked "Live" in section 3.
- A Groq takeover in a real event.
- A real time-limit cut-off of a strategy stage, cancelling a real strategy job, and the two-run
  limit with real runs.
- The in-place migration of the real `data/runs.db`, which will happen on the first backend start.
- `npm run api:types` against a running backend. The types were generated by the same generator from
  a schema written to a file, so that no backend had to open `data/runs.db`.
- Print output in a real browser. Printing is covered by unit tests in jsdom only.
- A refresh of the ui_v2 screenshots.
- Actual PDF output, the light theme and deployment, as before Milestone 3.

---

## 6. Bugs found and fixed during the milestone

First-hand only: each was found while building or reviewing Milestone 3, and each fix is pinned by
the test named. Failures that were faults in a new test, not in the code, are not listed.

| # | Found by | What was wrong | Fix | Pinned by |
|---:|:---|:---|:---|:---|
| 1 | Code review of the strategy plumbing | A strategy job on a saved run kept the saved warnings of the strategy stages it ran again, so stale notes sat beside the new result | The job drops saved warnings that start with the label of a stage it runs | `tests/test_m3_orchestrator.py::test_a_strategy_only_job_drops_the_old_warnings_of_the_stages_it_runs_again` |
| 2 | The founder's review of the go-to-market agent | The positioning could name another valid market segment instead of the priority segment | When the market analysis has a priority segment, it always becomes the target segment | `tests/test_m3_gtm_agent.py::test_another_market_segment_is_replaced_by_the_priority_segment` |
| 3 | First run of the new Advisor tests | The go-to-market routing keyword also matched the singular "customer" | It matches only "customers", the plan's word | `tests/test_m3_advisor.py::test_routing_assigns_each_question_to_its_sections` |
| 4 | First run of the new chat API tests (16 failures) | The thread reply was built with the `ChatLimits` class from `models/api.py`, but `ChatThread` takes the one in `models/chat.py` | The route copies the published limits into the chat model's class | `tests/test_m3_chat_api.py::test_the_thread_holds_suggestions_sections_turns_and_limits` |
| 5 | Type check of the MVP section | `months_to_mvp` is nullable in the generated API types, which the section did not handle | It falls back to the documented default | `npm run typecheck` |
| 6 | First fake run of the live scripts | The retro script's total included the seconds of the saved run it started from | The summary reports the job's own seconds | `tests/test_m3_live_scripts.py::test_the_fake_retro_run_adds_the_strategy_to_a_saved_run_without_a_search` |
| 7 | Writing the live scripts | On a Windows console using the ANSI code page, a feature or channel name with "₹" or Devanagari text would stop a run when printed | Console output replaces such characters; files stay UTF-8 | `tests/test_m3_live_scripts.py::test_printing_a_character_the_console_cannot_show_does_not_stop_a_run` |

### Found and not fixed

| What | Where | Effect |
|:---|:---|:---|
| The "Time taken" line of the full report names the strategy stages by their keys (`swot_risk`, `mvp_recommendation`, `go_to_market`) | `report_markdown(full=True)`, seen in the fake runs of the live scripts | Visible in `GET /api/runs/{run_id}/report.md` for a run with strategy |
| Advisor replies are not scanned for secrets, unlike strategy results | `agents/advisor_agent.py`, seen at the backend checkpoint | A key the model echoed would be redacted in the stored row but returned as written in the immediate answer |

Other limits of the design are listed in [docs/11, section 14](11_milestone3_strategy_and_advisor.md#14-known-limits).

---

## 7. Fixtures

- **Synthetic, for the interface.** `web/src/test/strategyFixture.synthetic.json` is a complete
  result with SWOT, MVP, go-to-market and constraints, made by running the real three agents over the
  fake drafts of the agent tests. `web/src/test/strategyHandlers.ts` and `web/e2e/mockApi.ts` serve
  it. It is named "synthetic" so that it cannot be taken for live output, and the `ui_v3` screenshots
  show it.
- **Fakes, for the backend.** `tests/m3_fakes.py` holds deterministic replies per stage, with invalid
  and failing variants; `tests/m3_live_fakes.py` holds the clients that `--fake` selects.
- **Saved live results, for compatibility.** `web/src/test/liveAgritech.json`, `liveFintech.json` and
  `docs/test_runs_m2/*.json` feed the digest and compatibility tests. One test opens `data/runs.db`
  read-only, copies it to a temporary file, validates every stored result, and checks that the
  original's hash, size and modification time did not change.
- **No live strategy fixture.** Fixtures derived from live strategy output (`liveStrategy*.json`) can
  only be made after L-1 has been run.

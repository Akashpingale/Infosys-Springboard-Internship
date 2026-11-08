# Milestone 2 Test Report

**Project:** Development of AI Based Startup Idea Validator with Market Analysis Assistance

**Scope:** Task 4, validation across domains (`KIRO_PROMPT_M2.md` Section 10). This report keeps
**automated test evidence** and **live validation** strictly apart. Automated results below were
produced by running the suite. Live results are only ever written here from artefacts a real run
left behind; until then they read **Not executed**.

---

## 1. The three Task 4 domains

| File | Industry | Idea |
|:---|:---|:---|
| `data/test_ideas/agritech.json` | Agriculture / AgriTech | Crop disease detection from a leaf photo, with treatment advice |
| `data/test_ideas/fintech_cashflow.json` | Finance / FinTech | Cash-flow and expense management for small businesses |
| `data/test_ideas/foodtech_surplus.json` | Food & Beverage | Surplus-food marketplace that cuts food waste |

`agritech.json` is reused unchanged from Milestone 1. The other two are new in Task 4. The two
Milestone 1 files `fintech.json` and `foodtech.json` are kept as they were, so the directory now
holds six ideas and two industries appear twice.

---

## 2. Automated tests

All tests use deterministic fakes. A fixture blocks every non-local socket and injects placeholder
keys, so no test can reach the LLM or the search API. Counts are from the runs below.

| What | Command | Tests | Result |
|:---|:---|---:|:---|
| **Task 4, three domains through the integrated pipeline** | `python -m pytest tests/test_m2_domains.py` | 92 | 92 passed, 0 failed, 0 skipped |
| **Task 4, live runner and report safeguards** | `python -m pytest tests/test_m2_live_runner.py` | 22 | 22 passed, 0 failed, 0 skipped |
| Task 1, Market Opportunity Agent | `python -m pytest tests/test_market_opportunity_agent.py tests/test_market_claims.py tests/test_figures.py tests/test_evidence.py tests/test_run_queries.py tests/test_structured.py` | 440 | 440 passed, 0 failed, 0 skipped |
| Task 2, Competitor Analysis Agent | `python -m pytest tests/test_competitor_analysis_agent.py tests/test_competitor_checks.py tests/test_integrity.py tests/test_m2_schemas.py tests/test_run_agent.py` | 286 | 286 passed, 0 failed, 0 skipped |
| Task 3, orchestration, API and UI | `python -m pytest tests/test_m2_orchestrator.py tests/test_m2_validate_route.py tests/test_m2_ui.py` | 85 | 85 passed, 0 failed, 0 skipped |
| Milestone 1 regression | `python -m pytest $(git ls-files tests/test_*.py)` | 299 | 299 passed, 0 failed, 0 skipped |
| Integration fix 1, Markdown report export | `python -m pytest tests/test_m2_report.py` | 24 | 24 passed, 0 failed, 0 skipped |
| Integration fix 2, audit fields in the API response | `python -m pytest tests/test_m2_audit_fields.py` | 15 | 15 passed, 0 failed, 0 skipped |
| Integration fix 3, backend time limit | `python -m pytest tests/test_m2_time_limit.py` | 25 | 25 passed, 0 failed, 0 skipped |
| **Whole project** | `python -m pytest` | **1301** | **1301 passed, 0 failed, 0 skipped**, 1 warning |

Task 4 added **114 tests**: 92 across the three domains and 22 for the runner and report
safeguards. The project total went from 1,117 to 1,237, the remaining six being Milestone 1 cases
parametrized over the two new idea files. The three integration fixes made after the live runs
added 64 more, for 1,301.

The one warning is Starlette's `httpx` deprecation notice, which predates Milestone 2.

### Milestone 1 count

Milestone 1 went from 293 to 299 tests. No Milestone 1 test logic changed. Three of its tests are
parametrized over the files in `data/test_ideas/`, so the two new ideas add six cases. The only
edit to a Milestone 1 test was in `tests/test_integration.py`, where the assertion that every idea
uses a different industry was relaxed to require three or more distinct industries, because
Section 10.1 adds a second FinTech and a second Food & Beverage idea. Section 10.1 directs that
such a test be adjusted rather than the data.

### What the Task 4 tests cover

Each row of the Section 10.2 table, and where it is covered. Rows whose behaviour does not depend
on the domain's data are covered once; the rest run for all three domains.

| Section 10.2 area | Covered by |
|:---|:---|
| Success: complete status, both outputs, integrity clean, URLs a subset of evidence | `test_m2_domains.py`, parametrized over all three domains, plus source traceability, timings, JSON round-trip, market-size scope, section completeness and competitor types |
| Missing or incomplete idea | `test_a_thin_idea_is_a_stage_error_without_any_analysis_call`, plus the Task 1 and 2 input checks |
| Search: empty, insufficient, total failure, timeout, one targeted query failing, all failing | `test_zero_usable_evidence_...`, `test_one_or_two_usable_results_force_a_limited_evidence_level`, `test_a_search_failure_skips_both_analyses_...`, `test_a_search_timeout_...`, `test_one_failed_targeted_competitor_search_...`, `test_all_targeted_competitor_searches_failing_...` |
| Competitor data: duplicates merged, irrelevant dropped, no-source dropped, hallucinated website, founder-named kept, no survivors | `test_a_competitor_without_a_valid_source_is_dropped_...` and `test_a_hallucinated_website_is_removed_...` for all three domains; the FinTech domain carries a founder-named competitor end to end. Merging, irrelevant entries and the no-survivor stage error are covered in depth by `tests/test_competitor_checks.py` and `tests/test_competitor_analysis_agent.py` |
| LLM: API error, config error, non-JSON, schema violation, retry, fabricated ids, downgrades | `test_a_non_json_market_reply_retries_once_then_fails`, `test_a_market_reply_that_breaks_the_schema_...`, `test_a_missing_llm_configuration_...`, `test_fabricated_source_ids_are_removed_...` (all domains), plus the Task 1 and 2 guard suites |
| Safety: injection in a snippet and in the idea | `test_injection_in_a_snippet_does_not_change_the_result` (all domains) and `test_injection_in_the_idea_cannot_open_a_prompt_block` |
| Orchestration: order, context passing, market fails, competitor fails, both fail, search fails, extraction fails, response validates | `test_m2_domains.py` for all three domains, plus the order spy and skip rules in `tests/test_m2_orchestrator.py` |
| Regression: Milestone 1 green, `/api/validate` keeps its fields | `test_the_milestone_1_pipeline_is_unchanged_for_every_domain`, `test_the_api_without_the_parameter_keeps_the_milestone_1_fields`, and the 299 Milestone 1 tests |

---

## 3. Live validation

Live runs spend real API credits and are run by hand, never by the assistant. One run is roughly
4 LLM calls and up to 11 web searches per idea, about 12 calls and 33 searches for the three, and
can take several minutes per idea.

```powershell
python scripts/run_live_m2.py --yes      # real keys needed; nothing runs without --yes
python scripts/make_m2_report.py         # refreshes the table below from run_summary.json
```

The runner writes `docs/test_runs_m2/<idea>.json`, `<idea>.md` and `run_summary.json`. Without
`--yes` it runs nothing. With missing keys it names the missing variables, never their values, and
writes no file at all.

<!-- live-runs:start -->

_Live section refreshed 2026-10-27 15:40 by `scripts/make_m2_report.py`._

From `docs/test_runs_m2/run_summary.json`, generated 2026-10-27 15:37 with model `gemini-3-flash-preview`. 3 of 3 ideas executed.

| Idea | Industry | Status | Total time | Competitors | Segments | Market sources | Competitor sources | Integrity violations |
|---|---|---|---:|---:|---:|---:|---:|---|
| `agritech` | Agriculture / AgriTech | complete | 159.3s | 1 | 2 | 10 | 6 | market_opportunity: none; competitor_analysis: none |
| `fintech_cashflow` | Finance / FinTech | complete | 102.5s | 5 | 3 | 10 | 11 | market_opportunity: none; competitor_analysis: none |
| `foodtech_surplus` | Food & Beverage | complete | 129.8s | 4 | 3 | 11 | 6 | market_opportunity: none; competitor_analysis: none |

Warnings recorded:
- `agritech`:
  - Market opportunity: market_demand.customer_problems[2]: it is not about the problem this idea solves, so it was removed
  - Market opportunity: segments[0].pain_points[0]: it is not about the problem this idea solves, so it was removed
  - Competitor analysis: Phase A: the candidate search failed (The AI service is busy right now. Please try again in a minute.), so only the generic searches were used
  - Competitor analysis: competitors[0].strengths[0]: removed strength 'Demonstrated massive scale with smallholder farmers.'; it had no valid source
  - Competitor analysis: competitors[0]: removed 'Plantix'; the founder did not name it in the submission
  - Competitor analysis: competitors[2]: removed 'Crop Disease Detection App (AI4D)'; it is not named in its cited sources
- `fintech_cashflow`:
  - Market opportunity: market_demand.demand_evidence[1]: a figure in this sourced claim does not appear with the same magnitude and unit in its cited sources, so it is now an AI interpretation
  - Market opportunity: limitations[0]: a figure in this sourced claim does not appear with the same magnitude and unit in its cited sources, so it is now an AI interpretation
  - Competitor analysis: differentiation_opportunities[2]: a figure in this sourced claim does not appear with the same magnitude and unit in its cited sources, so it is now an AI interpretation
- `foodtech_surplus`:
  - Competitor analysis: competitors[3]: removed 'Foodealz'; the founder did not name it in the submission
  - Competitor analysis: competitors[5]: removed 'Food banks and charities'; it is not named in its cited sources

<!-- live-runs:end -->

### Earlier standalone runs, for context

These are **not** Task 4 live runs. They exercised the Market Opportunity Agent on its own,
before the Task 1 quality fixes, and are kept as evidence of that stage only.

| File | What it was |
|:---|:---|
| `docs/test_runs_m2/dev_market_agritech.txt` | First standalone market run, 2026-10-24 |
| `docs/test_runs_m2/dev_market_agritech_v2.txt` | Second standalone market run after the scope fixes, 2026-10-24 |

The Milestone 1 live evidence in `docs/test_runs/` is from the two-stage pipeline and does not
include either analysis stage.

---

## 4. Human review checklist

To be completed by hand after reading each live output. Leave these empty until the live runs
exist. The items are those listed in Section 10.4.

### 4.1 `agritech`

- [ ] The industry and segments are relevant to the idea
- [ ] The pain points match the idea's problem
- [ ] Demand and trend claims carry sources
- [ ] Market size is sourced, or marked unavailable
- [ ] The priority segment has a rationale
- [ ] The competitors are relevant
- [ ] Direct, indirect and emerging are labelled correctly
- [ ] Comparison fields are filled where evidence exists
- [ ] Source URLs are retained and resolve
- [ ] The gaps are reasonable and evidence-based

### 4.2 `fintech_cashflow`

- [ ] The industry and segments are relevant to the idea
- [ ] The pain points match the idea's problem
- [ ] Demand and trend claims carry sources
- [ ] Market size is sourced, or marked unavailable
- [ ] The priority segment has a rationale
- [ ] The competitors are relevant
- [ ] Direct, indirect and emerging are labelled correctly
- [ ] Comparison fields are filled where evidence exists
- [ ] Source URLs are retained and resolve
- [ ] The gaps are reasonable and evidence-based

### 4.3 `foodtech_surplus`

- [ ] The industry and segments are relevant to the idea
- [ ] The pain points match the idea's problem
- [ ] Demand and trend claims carry sources
- [ ] Market size is sourced, or marked unavailable
- [ ] The priority segment has a rationale
- [ ] The competitors are relevant
- [ ] Direct, indirect and emerging are labelled correctly
- [ ] Comparison fields are filled where evidence exists
- [ ] Source URLs are retained and resolve
- [ ] The gaps are reasonable and evidence-based

---

## 5. Known gaps

- **Live validation is one run per idea.** Each Task 4 idea ran live once on 2026-10-27
  (Section 3). Their cost was not recorded, the review checklists in Section 4 are not filled in
  yet, and the runs went through the live runner, not the API or the UI. They were made before the
  three integration fixes in Section 2, so the saved results have no audit fields and no run was
  under the backend time limit.
- **The backend time limit is tested with simulated time only.** A run through
  `/api/validate?include_analysis=true` now stops at 90% of `PIPELINE_TIMEOUT_S` (162 seconds by
  default) and returns what finished as `partial`. The live runner sets no limit; the three live
  runs took 102.5 to 159.3 seconds. In the second standalone market run the first LLM call ended
  with HTTP 504 after about 90 seconds and the retry succeeded, so one slow call can still take
  over half of the limit.
- **The analysis stages are opt-in.** `POST /api/validate` runs them only with
  `include_analysis=true`, which the Streamlit UI always sends. The default stays the Milestone 1
  two-stage pipeline.
- **The Milestone 1 live runner** `scripts/run_live_ideas.py` is unchanged and still globs
  `data/test_ideas/`, so it would now cover six ideas rather than four, through the two-stage
  pipeline only. It was not run.

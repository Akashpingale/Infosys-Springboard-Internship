# 15. Final test report (Milestone 4, requirement R2)

**Project:** Development of AI Based Startup Idea Validator with Market Analysis Assistance

**Scope:** the whole system after Milestone 4 on branch `main` (last commit `94ddc9a`, with the Milestone 4 work uncommitted in the working tree). This report keeps measured automated evidence apart from live checks. Every automated number below was measured with fake providers on 18 November 2026. **No live check was executed**, so no number here describes real model or search behaviour.

**Requirement R2 is not fully evidenced.** Plan Section 6 asks for green regression suites, real-backend fake-provider journeys, targeted failure coverage and live results or explicit outstanding checks. The regression suites are green. The real-backend journeys, the targeted failure tests, coverage measurement and the reproducibility check were not executed, because the user skipped the end-to-end testing task (T7) and the live verification checkpoint (T8) on 18 November 2026. Section 5 lists every outstanding item. The milestone is not marked fully verified.

---

## 1. Summary

| Area | Command | Result (18 Nov 2026) |
|---|---|---|
| Backend | `python -m pytest -q -p no:cacheprovider` | **2956 passed**, 0 failed, 1 warning (Starlette/httpx deprecation), 103.52 s |
| TypeScript | `npm run typecheck` (in `web/`) | Clean, for the application and for the browser tests |
| Front-end unit and component tests | `npm test` | **552 passed** in 42 files; 0 MSW unhandled-request lines |
| Production build | `npm run build` | Entry chunk **269.24 kB, 85.73 kB gzip** (ceiling 269.24 kB / 85.73 kB); report page a separate lazy chunk of 18.08 kB / 5.98 kB gzip |
| Browser tests | Playwright, every spec, Chromium, 390, 820 and 1440 px | **369 passed** in 7 specs, 8.1 min |
| Accessibility | `accessibility.spec.ts`, `accessibility-m3.spec.ts` (inside the run above) | 0 serious or critical axe violations on the 27 earlier and 14 Milestone 3 screens at three widths. The report page has **no axe check** (not executed) |
| Secret scan | Section 2.6 | **0 hits** in the working tree (848 text files) |
| Coverage | `pytest-cov`, `@vitest/coverage-v8` | **Not measured.** The tools were never installed |
| Real-backend journeys J-1 to J-8 | Section 8.4 of the plan | **Not executed** |
| Failure-injection matrix and targeted integration tests | Section 8.3 of the plan | **Not executed** as a new suite; the existing per-stage failure tests run in the backend suite |
| Reproducibility check | an isolated copy of the working tree | **Not executed** |
| Live checks L-1 to L-8 | Section 4 | **Not executed** |

## 2. Automated tests

All tests use deterministic fakes. In the backend, `tests/conftest.py` blocks every non-local socket and sets placeholder keys. In the front end, MSW answers every request and fails any test that reaches an unmocked address. In the browser tests, `web/e2e/mockApi.ts` answers every API call by route interception and throws if anything tries to start a run.

### 2.1 Backend

2956 tests were collected and passed. The 2454 tests that existed before Milestone 4 all still pass; the edits Milestone 4 made to some of them are listed in Section 3. Milestone 4 added 502 tests in 16 files:

| File | Tests | What it covers |
|---|---:|---|
| `test_m4_usage_versions.py` | 44 | AI request and search counting, including retries and fallback; stage totals; versions; no secrets |
| `test_m4_profiles_v1_snapshots.py` | 21 | v1 prompts, query sets and reply schemas byte-identical to the T1 snapshots |
| `test_m4_report_models.py` | 35 | Report models and compatibility with every stored fixture |
| `test_m4_report_sections.py` | 36 | Each section builder on complete, partial, no-strategy and minimal results |
| `test_m4_report_bibliography.py` | 17 | Citation numbering, merges across analyses, the `S0` entry, uncited entries |
| `test_m4_report_checks.py` | 32 | Consistency checks C-01 to C-12 with planted offenders |
| `test_m4_report_agent.py` | 76 | Full build, summary failure and invalid output, partial run, fingerprint, exactly one AI request, no search |
| `test_m4_render_md.py` | 26 | Golden Markdown, escaping, URL allowlist |
| `test_m4_render_pdf.py` | 36 | Pages, contents and page numbers, links, missing fonts, determinism, metadata, hostile strings, page cap |
| `test_m4_cross_format.py` | 9 | The same text on screen, in Markdown and in PDF |
| `test_m4_report_api.py` | 39 | The five report routes, every rule and error code, file names, stale flag, busy, shared concurrency |
| `test_m4_store_migration.py` | 20 | New columns on synthetic old databases, deletion, redaction, reports for every saved result |
| `test_m4_parallel_search.py` | 26 | Parallel search: same output as sequential, order, failure isolation, deadline, cancel, rate-limit pause, one worker |
| `test_m4_profiles_v2.py` | 43 | Query profile v2 (Q-1 to Q-6), `search_terms` validation |
| `test_m4_prompt_profile_v2.py` | 21 | Prompt profile v2 (P-1, P-2, P-4, P-5, P-6): rules, positions, length budget, versions |
| `test_m4_matrix_consistency.py` | 21 | The matrix consistency check and the before-and-after comparison of the existing checks on all stored fixtures |

The Milestone 3 tests (`tests/test_m3_*.py`, 818 tests) are among the 2454.

### 2.2 Front end

552 tests in 42 files passed; 477 in 35 files existed before Milestone 4. Milestone 4 added 75 tests in 7 files: `ReportPage.test.tsx`, `ReportBlocks.test.tsx`, `DownloadMenu.test.tsx`, `ReportButton.test.tsx` and `useReport.test.tsx` in `web/src/features/report/`, `RunDetailsPanels.test.tsx` in `results/` and `StatusReport.test.tsx` in `status/`. They cover every block type, citation jumps, the three banners, generate, regenerate and cancel, the missing-fonts state, the header button states, the export menu labels, hostile text rendered as text, and the narrow layout of the contents list. The output had 0 lines mentioning an unhandled request.

### 2.3 Browser tests

Playwright 1.56.1, Chromium, one worker, run from a scratch folder so that the screenshot specs wrote their images there and not into `docs/assets/`. The 123 tracked screenshots in `docs/assets/ui_v2/` and `ui_v3/` were hashed before and after and are unchanged.

| Spec | Passed |
|---|---:|
| `accessibility.spec.ts` | 81 of 81 |
| `accessibility-m3.spec.ts` | 42 of 42 |
| `keyboard.spec.ts` | 21 of 21 |
| `keyboard-m3.spec.ts` | 60 of 60 |
| `focus-m3.spec.ts` | 42 of 42 |
| `screens-m3.spec.ts` | 42 of 42 |
| `screenshots.spec.ts` | 81 of 81 |

**Known issue, not fixed.** `keyboard-m3.spec.ts:293` "reduced motion on the Milestone 3 screens › advisor-full does not animate" [w1440] failed once in the Milestone 4 baseline run on 16 November (a 30-second timeout waiting for the tab list, with an empty main region in the page snapshot) and passed when re-run alone 3 times. It passed in the run above. Its root cause was to be found in T7, which was not executed, so it remains an intermittent test.

No browser test covers the new report page: there is no Playwright journey, axe check or screenshot of it, and no `docs/assets/ui_v4/` folder.

### 2.4 Build

`npm run build` transformed 2252 modules. The entry chunk is `index-CXZRsTUL.js`, 269.24 kB (85.73 kB gzip), the same file as at the end of the report interface task (T4). The report page (`ReportPage`, 18.08 kB) and its hooks (`useReport`, 7.56 kB) are separate lazy chunks.

The Milestone 3 entry was 268.79 kB (85.56 kB gzip), which was the ceiling the user approved for Milestone 4 (T0 conflict C-3). The required lazy report route adds 453 bytes to the entry: the route definition, its lazy wrapper, preload-map entries and one library branch. During T4 the workflow orchestrator raised the ceiling to 269.24 kB / 85.73 kB gzip, after a source-map comparison showed that the growth contains no report or app module. This is a deviation from the ceiling the user approved, recorded here for the user's review.

### 2.5 Offline checks of the documentation

The OpenAPI snapshot `docs/final/openapi.json` was written by an in-process dump with placeholder keys (21 operations, 101 schemas). `openapi-typescript` 7.13.0 turns it into a file byte-identical to the current `web/src/api/types.gen.ts`, so a fresh clone can generate the types without a running backend. Links between the Milestone 4 documents were checked by a script that resolves every relative link; external links were not opened.

### 2.6 Secret scan

The scan looks for seven key shapes: Google (AIza…), Gemini (AQ.…), Tavily (tvly-…), Groq (gsk_…), secret key (sk-…), bearer token and private key block. It prints only file paths and pattern names, never a matched value, and never opens a `.env` file.

| Scope | Result |
|---|---|
| Working tree: every tracked and untracked file that is not git-ignored | 1027 files listed, 848 text files scanned, 179 binary files skipped, **0 hits** |
| The files changed or added in Milestone 4 (including `docs/final/`) | 109 files scanned, **0 hits** |

Git history was not scanned again. The T0 audit found a Tavily-key-shaped string in three old versions of `docs/05_web_search_api.md` and an old `src/web_search/.env` in commit `50ea1ae`. Whether those keys were rotated is not confirmed (Section 5).

## 3. Existing tests edited in Milestone 4

Only the kinds of edit plan Section 20.4 and the approved conflict resolutions allow. Every comparison stays exact unless the row says which varying field is left out. For each edit, undoing it was shown to restore the previous file hash (task bookkeeping, outside the repository).

| Task | File | Change |
|---|---|---|
| T1 | `tests/test_m3_orchestrator.py:91` | The hashed digest leaves out `usage` and `versions` next to `timings`; `BASELINE_RESULT_SHA256` is unchanged |
| T1 | `tests/test_stage_events.py:273`, `tests/test_m2_time_limit.py:448` | Leave out only `usage.by_stage[*].seconds` next to `timings`; counts and versions are still compared |
| T1 | `tests/test_m2_groq_fallback.py:646`, `tests/test_m2_groq_structured.py:553` | Leave out `usage` next to `timings`, because counts differ by provider by design; `versions` still compared. `test_m4_usage_versions.py` asserts the left-out values exactly |
| T4 | `tests/test_m3_runs_api.py:120, 370`, `tests/test_m3_schemas.py:586` | The exact key sets gain `report` (run detail) and `report`, `profiles` (meta) |
| T4 | `tests/test_m3_store_migration.py:29, 145, 164`, `tests/test_run_store.py:162` | The exact column sets gain `report_json`, `report_fingerprint`, `report_generated_at` |
| T4 | `web/src/features/results/ExportMenu.test.tsx` (12 lines), `web/src/features/run/exportRun.test.tsx` (3), `web/src/features/run/RunPage.test.tsx` (2), `web/e2e/screens.ts` (1) | Label lookups only: "Markdown report" → "Raw results (Markdown)", "JSON result" → "Raw results (JSON)", "PDF" → "Print this page" |
| T5 | `tests/test_m4_profiles_v1_snapshots.py:282, 289` | `QUERY_PROFILES` becomes `("v1", "v2")`; `QUERY_PROFILE=v2` now gives v2 |
| T6 | `tests/test_m4_profiles_v1_snapshots.py:282` | `PROMPT_PROFILES` becomes `("v1", "v2")` |

## 4. Live checks (plan Section 20.7, reduced to the three-idea pilot of Section 3)

Live checks spend real credits and are run by the user, never by the assistant. Preconditions: the exposed keys rotated, `.env` filled, the report fonts installed, the backend running, credit use approved. The live verification checkpoint (T8), which was to prepare a checklist and a review form for these checks, was skipped by the user on 18 November 2026. The table below records the checks from the plan, with manual steps from existing runners, so that they can be run later. None has been run.

| Id | Check | How (existing runners or manual steps) | What to record | Approximate credits | Status |
|---|---|---|---|---|---|
| L-1 | Three ideas end to end with report | `python scripts/run_m3_live.py --yes`, then generate each report in the interface or with `POST /api/runs/{id}/report` | Status, seconds per stage, `usage`, warnings by code, consistency result, strategy counts | 3 runs of about 7 AI requests and up to about 12 searches each, plus 3 report requests | **Not executed** |
| L-2 | Report review | Open each PDF and fill in the review form below | The ten items | none | **Not executed** |
| L-3 | Advisor | `python scripts/check_advisor_live.py --yes` | The eight fixed questions and their answers | about 7 AI requests | **Not executed** |
| L-4 | Groq schema compatibility | `python scripts/check_groq.py` checks one schema (`CompetitorAnalysisDraft`); the other schemas are checked offline only (T0 conflict C-16) | Accepted or rejected | 1 AI request | **Not executed** |
| L-5 | Provider fallback | Observation only: no setting can force Groq | Whether any live run shows Groq taking over | 0 extra | **Not executed** |
| L-6 | Cancel and limits in reality | Cancel a real run during stage 3; start two runs and try a third. Only with quota and approval | Status, history, the refusal message | about 3 partial runs | **Not executed** |
| L-7 | Evaluation runs | [docs/14, section 2.1](14_evaluation_and_optimization.md#21-steps-for-the-user-not-run-by-kiro) | The comparison tables of docs/14 | about 63 AI requests and up to about 108 searches | **Not executed** |
| L-8 | Clean checkout and rehearsal | A clean checkout after the commit, then the steps in `docs/final/DEMO_RUNBOOK.md` with timings | Setup problems; minutes per step | 1 full run | **Not executed** |

### 4.1 Report review form (record here; do not tick for the reader)

| # | Check | Outcome |
|---:|---|---|
| 1 | All catalogue sections present or explained | **Not executed** |
| 2 | Five numbers spot-checked against the tabs | **Not executed** |
| 3 | Five citation numbers lead to the right source | **Not executed** |
| 4 | Ten statements spot-checked against the sources; none unsupported | **Not executed** |
| 5 | The summary reads naturally and gives no verdict | **Not executed** |
| 6 | Currency symbols and accents render | **Not executed** |
| 7 | Tables are readable and not cut | **Not executed** |
| 8 | The table of contents page numbers are right | **Not executed** |
| 9 | Caveats present (gaps, interpretations, partial) | **Not executed** |
| 10 | Page count reasonable | **Not executed** |

## 5. Outstanding: not executed or not verified

**From the skipped end-to-end testing task (T7):**
- the real-backend browser journeys J-1 to J-8 (happy path, partial, cancel, strategy added later, limits, edit and re-run, delete, offline), and the `scripts/serve_e2e_backend.py` server they need;
- the targeted integration and failure-matrix tests across the seven stages, the Advisor and the report (plan Section 8.3), beyond the existing per-stage failure tests;
- coverage measurement: `pytest-cov` and `@vitest/coverage-v8` were never installed, so coverage is **not measured** and the 90 percent line target for new modules is unchecked;
- the reproducibility check on an isolated copy of the working tree, and the clean-checkout check after the commit;
- axe checks, keyboard checks and screenshots of the report page at 390, 820 and 1440 px (`docs/assets/ui_v4/`);
- the root cause of the intermittent `keyboard-m3` "advisor-full does not animate" [w1440] test (Section 2.3);
- Firefox and WebKit smoke runs.

**From the skipped live verification checkpoint (T8):** every check in Section 4, the PDF review form, and the observation of provider fallback, cancel and limits with real providers.

**Other manual actions:**
- confirmation that the exposed keys were rotated (T0 audit, Section 8 of its report);
- the IBM Plex TTF files and the OFL licence in `assets/fonts/`, and a character-coverage check of those files;
- the user's preview of the report page and inspection of a PDF;
- the comparable baseline and the reference competitor names `[FOUNDER TO FILL]` (docs/14);
- the user's decisions on `SEARCH_MAX_PARALLEL` (1 now, 3 in plan 12.3) and on the single rate-limit retry (not built);
- the demo fallback report from the saved run (`docs/final/DEMO_RUNBOOK.md`, section 4), which needs the user's own database;
- the rehearsal of the demonstration.

**Reviews waived by the user:** the code reviews of T5 (web search optimisation) and T6 (prompt, reasoning and accuracy optimisation). The regression in this report runs their tests again, but no independent review of their code took place.

## 6. Requirement coverage (manual table)

The automatic traceability script was deferred (plan Section 3). This table was written by hand from the test names.

| Requirement or criterion | Evidence in tests |
|---|---|
| R1 all sections, missing parts explained (A-R1.1) | `test_m4_report_sections.py`; `test_m4_report_agent.py::test_a_partial_run_explains_what_did_not_finish` |
| R1 same meaning on screen, PDF and Markdown (A-R1.2) | `test_m4_cross_format.py::test_screen_markdown_and_pdf_hold_the_same_text` |
| R1 citations, no narrative statement sourced (A-R1.3) | `test_m4_report_agent.py::test_the_report_never_holds_a_narrative_statement_labelled_sourced`; check C-01 |
| R1 12 consistency checks on fixtures (A-R1.4, A-R1.5) | `test_m4_report_checks.py`; `test_m4_report_agent.py::test_every_stored_result_builds_a_checked_report`. The three live outputs the criterion names do not exist (not executed) |
| R1 PDF structure, determinism, accents (A-R1.6) | `test_m4_render_pdf.py` with ReportLab's bundled fonts. With the real fonts: not executed |
| R1 hostile text, `javascript:` URLs, planted keys (A-R1.7) | `test_m4_render_md.py`, `test_m4_render_pdf.py`, `ReportBlocks.test.tsx` |
| R1 stale after strategy is added (A-R1.8) | `test_m4_report_api.py::test_adding_strategy_makes_the_report_out_of_date_and_regenerating_makes_it_current` |
| R1 one AI request, no search (A-R1.9) | `test_m4_report_agent.py::test_the_report_makes_exactly_one_ai_request_and_no_search` |
| R2 regression suites green | Section 1 |
| R2 real-backend journeys, failure matrix, live results | Not executed (Section 5) |
| R3 v1 unchanged, v2 behind switches | `test_m4_profiles_v1_snapshots.py`, `test_m4_profiles_v2.py`, `test_m4_prompt_profile_v2.py`, `test_m4_matrix_consistency.py`, `test_m4_parallel_search.py` |
| R3 comparison and adoption decision | Not executed ([docs/14](14_evaluation_and_optimization.md)) |
| Streamlit and the legacy Markdown export unchanged | `tests/test_m2_ui.py`, `tests/test_m3_report.py` (hash), `test_m4_report_api.py::test_the_existing_markdown_export_is_unchanged` |

## 7. Problems found and fixed in Milestone 4

First-hand only, from the task records. Failures that were faults in a new test are not listed.

| Found by | What was wrong | Fix |
|---|---|---|
| The new report page tests (T4) | A second `<header>` element on the report page would be hidden when printing, because `print.css` hides `header` for the app bar | The report header is a `div` marked `data-report-header` |
| The same tests | The subtitle repeated the title when the two were equal | The subtitle is not shown when it equals the title |
| The bundle measurement (T4) | An early version extended `web/src/api/client.ts` for file downloads, which put 27 bytes of app code into the entry chunk | Downloads use their own `fetch` inside the lazy `useReport` chunk; `client.ts` is unchanged |

**Found and not fixed:** the intermittent browser test (Section 2.3), and the two Milestone 3 items in [docs/12, section 6](12_milestone3_test_report.md#6-bugs-found-and-fixed-during-the-milestone): the strategy stage keys in the legacy report's "Time taken" line, and Advisor replies that are not scanned for secrets before they are returned.

## 8. Fixtures

- `tests/m4_report_fixtures_synthetic.py` and `web/src/test/reportFixture.synthetic.json`: synthetic complete, partial, no-strategy and minimal results and one synthetic report, named "synthetic" and never used as evidence.
- `tests/snapshots/m4_v1_profiles.json` (v1 prompts and queries), `m4_v1_checks.json` (the existing checks before T6) and `m4_report_synthetic.md` (golden Markdown).
- The saved live results in `docs/test_runs/`, `docs/test_runs_m2/` and `web/src/test/live*.json` feed the compatibility tests. No `docs/test_runs_m4/` folder exists, because no Milestone 4 live run was made.

## 9. Reproducing these numbers

PowerShell, from the repository root with the virtual environment active:

```powershell
python -m pytest -q -p no:cacheprovider
cd web; npm run typecheck; npm test; npm run build
```

POSIX shell:

```sh
python -m pytest -q -p no:cacheprovider
cd web && npm run typecheck && npm test && npm run build
```

Run Playwright from a folder outside `web/`, so that the screenshot specs do not rewrite the tracked images in `docs/assets/`. For example, from an empty folder `C:\pw-run\run` (or `~/pw-run/run`):

```powershell
& "<repo>\web\node_modules\.bin\playwright.cmd" test --config "<repo>\web\playwright.config.ts"
```

```sh
<repo>/web/node_modules/.bin/playwright test --config <repo>/web/playwright.config.ts
```

Port 4173 must be free, because the configuration reuses an existing server on it.

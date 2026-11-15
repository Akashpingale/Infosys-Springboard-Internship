# T18 report: Export, print and re-run integration

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T18 (line ~1299), with 14.7 (export and print), 14.2 ("Edit and re-run" carries the stored constraints back), 17.5 (`RunPage.tsx` print flag includes Strategy and excludes Advisor; `print.css` Strategy print rules, Advisor hidden; `ExportMenu.tsx` no change expected) and D-14 (Markdown strategy sections on the `full=True` path only, Advisor transcript never exported). Nothing from T19 or later was built: no Playwright spec, `mockApi.ts`, screenshot or doc was touched.

No backend file changed. The full backend suite was not re-run (brief: frontend tasks run it only when a backend file changed). The Markdown route was verified by running the existing backend report and runs-API tests (below). No backend server was started.

## Files

| File | Status | Diff | Purpose |
|---|---|---|---|
| `web/src/features/run/RunPage.tsx` | changed (T18's named file) | +38 −13 vs start of task | `PRINTED_TABS` now drops only the Advisor, so Strategy is printed with the other tabs. At print time the Strategy section is laid out only when the run has any strategy part (`hasAnyStrategy`, the T14 rule the tab itself uses); otherwise the printed page is the same five tabs as before. Printing is now two steps (`printing: 'layout' \| 'print' \| null`). Step `layout` renders every printed tab and presses every `button[aria-expanded="false"][aria-controls]` inside the printed layout (`printedRef`); this opens the risk register's detail rows, the one fold in the app made with a button instead of `<details>`. Step `print` is the existing effect, unchanged apart from its guard: open every `<details>` except `data-print-keep-closed` (so the MVP "How the ranking works" disclosure opens), call `window.print()`, close them again, reset. The printed layout is unmounted afterwards, so the open tab keeps its own folds. The stale T17-era comment ("The two Milestone 3 tabs hold placeholders for now") is replaced, and `PRINTED_TABS` with its comment moved above `messageTone`'s doc comment, which it had been splitting from its function |
| `web/src/styles/print.css` | changed (T18's named file, committed M2 file) | +10 −0 | Hides `button[aria-expanded][aria-controls]` on paper: once the page has opened the button-folded panels, their "Hide details" buttons have no use on a printed page. The comment notes that the Advisor is never laid out for printing and that the Strategy tab's own controls already carry `data-print-hide` |
| `web/src/features/run/exportRun.test.tsx` | new | 308 lines, 8 tests | See Tests |

`ExportMenu.tsx` was not changed: the Markdown comes from the backend route and the JSON is the untouched result (17.5 "No change expected"). The new test file has no comments or docstrings (plan 0.5). The edits to the existing files follow their own commented style.

`hashes.py check` against the start-of-task baseline (87 uncommitted files) lists exactly: `changed web/src/features/run/RunPage.tsx`, `new web/src/features/run/exportRun.test.tsx`, `new web/src/styles/print.css`. `print.css` shows as "new" only because it was a clean committed file at the start, so it was not in the uncommitted baseline. No other file differs.

## Requirement mapping

| Requirement | Where | Test |
|---|---|---|
| 14.7 Print renders the Strategy tab with the others | `PRINTED_TABS` keeps `strategy` | `prints every Strategy section with its folded panels open, and no Advisor`: printed sections are exactly Overview, Market, Competitors, Strategy, Sources, Run details. The four Strategy headings are exactly SWOT, Risks, MVP plan, Go-to-market. The SWOT summary, all 8 MVP feature names and the GTM positioning statement are on the page |
| … opens its folded panels | `layout` step presses the button folds; `print` step opens `<details>` | Same test: the description and early-warning sign of all 6 risks are on the page, the "How the ranking works" `<details>` is open, and no folded toggle is left (`foldedToggles` 0) |
| … puts the page back | Printed layout unmounted; details closed again | `puts the page back afterwards: one tab, panels folded, risk details hidden again` (printed from the Strategy tab: tab still selected, 0 open details, no risk description on screen, every "Show details" toggle `aria-expanded="false"`) |
| … and excludes the Advisor tab | `PRINTED_TABS` drops `advisor` | First test: no Advisor title or empty copy and 0 `GET /chat` reads. `prints the Advisor nowhere even when it was the open tab`: printed from the Advisor tab, same section list, no Advisor text, no extra chat read at print time |
| Markdown route verified; "Markdown download request unchanged" | `ExportMenu` unchanged | `asks for the same Markdown report without a strategy …` and `… with a strategy …` (`it.each`): exactly one request, `GET`, URL `${API_URL}/api/runs/run-123/report.md` with no query, empty body, for both runs. The saved file is `.md`, type `text/markdown;charset=utf-8`, and its content is byte-equal to what the backend sent. Backend side: `tests/test_m3_report.py::test_the_report_route_exports_strategy_and_never_the_advisor_conversation` (T9) checks the route output; it was re-run here (pass) |
| "JSON contains the new fields" (14.7 "JSON is untouched") | `ExportMenu.exportJson` unchanged | `saves the JSON with the strategy fields, exactly as the backend returned it`: the parsed file `toEqual(STRATEGY_DONE.result)`, and `swot`, `mvp`, `gtm` and `constraints` each equal the fixture |
| "Edit and re-run" end to end with constraints | Existing T13 wiring (`RunPage` → `NewValidationPage` → `ReviewStep`), now tested as one flow | `carries the run, its constraints and the strategy choice back to a new run`: real `RunPage` on a strategy run → **Edit and re-run** → real form prefilled → **Review my idea** → constraints panel open with Team size 2, Months 4, Bootstrapped and an empty region, Include strategy on → **Run analysis**. `POST /api/runs` body is exactly `{ submission, idea_override: EXTRACTED, include_strategy: true, constraints: { team_size: 2, months_to_mvp: 4, budget_level: 'bootstrapped' } }` (only the filled fields), then the new run's page opens |
| Print of a run without strategy unchanged | `hasAnyStrategy` filter | `leaves Strategy out of a run that has none, rather than printing the offer and its form`: printed sections are exactly the five M2 tabs, no Strategy heading, no "No strategy yet." and no "Resources and goals (optional)" |

## Tests (8 new, `web/src/features/run/exportRun.test.tsx`)

- Printing (4): `prints every Strategy section with its folded panels open, and no Advisor`; `puts the page back afterwards: one tab, panels folded, risk details hidden again`; `prints the Advisor nowhere even when it was the open tab`; `leaves Strategy out of a run that has none, rather than printing the offer and its form`.
- Export (3): `asks for the same Markdown report without a strategy, once, and saves what the backend sent`; the same `with a strategy`; `saves the JSON with the strategy fields, exactly as the backend returned it`.
- Edit and re-run (1): `carries the run, its constraints and the strategy choice back to a new run`.

The existing print tests in `RunPage.test.tsx` (`lays every section out and opens the folded panels, then prints and puts them back`; `leaves the raw JSON folded, …`) pass unchanged. They use a run without strategy, which prints the same five tabs as before.

## Existing-test edits

None.

## Decisions and plan-vs-code points

1. **Button-folded panels are opened by pressing their buttons.** 14.7 says print "opens its folded panels". In the Strategy tab, the MVP ranking disclosure is a `<details>`, which the existing effect already opens. The risk register's expandable detail (description, early-warning sign, confidence, basis, citations: 14.4) is a button fold held in `RisksSection` state, so its content is not in the DOM until the button is pressed. A printed register without its citations would lose its sources. A prop or context would have meant editing T14/T15 files (`StrategyTab.tsx`, `RisksSection.tsx`), which T18's entry does not name. Instead, RunPage presses the buttons in the throwaway printed layout. This follows the existing effect, which already sets `details.open` directly. The selector `button[aria-expanded="false"][aria-controls]` matches only `RisksSection`'s `DetailToggle` on the run page (StrategyTab's regenerate button has no `aria-controls` and sits in `data-print-hide`; the export popover trigger is in the header).
2. **Strategy is left out of the printed page when the run has none.** Otherwise the print would show the "No strategy yet" offer, the Generate button and the constraints `<details>`, which the effect would open into a form on paper. With no strategy, the printed page is exactly what it was before T18. A run with any strategy part (done, running, failed or skipped) prints the Strategy tab with its section states.
3. **"Hide details" buttons are hidden on paper** with one print rule (`button[aria-expanded][aria-controls]`). jsdom does not apply print CSS, so this rule has no unit test. T19's browser specs are the place to see it.
4. **The "Try again" button of a failed Strategy section still prints.** It has no `data-print-hide`, and adding one means editing `StrategyStates.tsx` (T14), which T18 does not name. Left as is and noted here. The M2 tabs leave some buttons on paper too, for example citation chips, which are buttons on purpose.
5. **No backend test was added.** T9 already covers "Markdown route verified" at the route level, and D-14 keeps the default export byte-identical. T18's entry asks for frontend tests. The relevant backend tests were re-run (68 passed).

## Commands run and results

| Command | Result |
|---|---|
| `python .agents\tasks\m3-t18\hashes.py save` | 87 uncommitted files hashed (`baseline_hashes.json`) |
| `Get-FileHash` / `Get-Item data\runs.db` (start) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z |
| `npx vitest run src/features/run/exportRun.test.tsx` (`vitest-1.log`) | 8 tests: 7 passed, 1 failed. The test expected the MVP `summary`, which the Strategy tab does not render. Fixed in the test by checking every feature name instead |
| same (`vitest-2.log`) | 8 passed |
| `npm run typecheck` (first) | 1 error, TS2532 in the new test (`mvp.features` is optional). Fixed with `?? []` and an exact length assertion |
| `npm run typecheck` (`typecheck.log`) | Clean (exit 0), app and e2e |
| `npx vitest run src/features/run/exportRun.test.tsx` (`vitest-3.log`) | 8 passed |
| `npm test` (`npm-test.log`, run after the last edit) | **35 files, 477 passed** (469 after T17 + 8 new). **0** lines matching `unhandled`, `onUnhandledRequest` or `MSW]`. 5 `not wrapped in act` lines, the same as T16 and T17 |
| `npm run build` (`build.log`) | Built. Entry chunk `index-DY1vOW76.js` **268.79 kB / 85.56 kB gzip** (T17: 268.79 / 85.54; baseline 268.78 / 85.54). RunPage chunk 141.46 kB / 35.31 kB gzip (T17: 141.21 / 35.19) |
| `python -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_report.py tests/test_m2_report.py tests/test_runs_api.py` (`pytest-report.log`) | 68 passed, 1 warning (the known Starlette/httpx deprecation) |
| `python .agents\tasks\m3-t18\hashes.py check` (end) | Only the three files listed under Files |
| `Get-FileHash` / `Get-Item data\runs.db` (end) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z (unchanged) |

Pre-edit copies: `.agents\tasks\m3-t18\RunPage.tsx.orig`, `.agents\tasks\m3-t18\print.css.orig`.

Playwright was not run. T19 owns the browser specs, and the brief's frontend gate is typecheck, `npm test` and build. The ui_v2 screenshots spec was not run. Nothing was committed, pushed, reset, reverted or stashed. No branch was created or switched. No `.env` file and no `data/runs.db` content was opened. No live provider call was made.

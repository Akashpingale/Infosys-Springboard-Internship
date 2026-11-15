# T18 review: Export, print and re-run integration

Verdict: **APPROVED**. No blockers.

## Scope and file check
- `hashes.py check` against the start baseline (re-run by the reviewer) lists only `web/src/features/run/RunPage.tsx` (changed), `web/src/features/run/exportRun.test.tsx` (new) and `web/src/styles/print.css` (committed file, now modified). All three are allowed: RunPage.tsx and print.css are named in the T18 entry, and the test file is one of its new files.
- `RunPage.tsx.orig` SHA-256 `e849cf02…bc3f` matches the baseline entry for RunPage.tsx. `print.css.orig` blob `8a79569` equals `HEAD:web/src/styles/print.css`. The pre-edit copies are therefore the real start state, and the diffs (+38/−13, +10/−0) match the report.
- No backend file, no existing test, `mockApi.ts`, docs or screenshots changed. There were no existing-test edits. The new test file has no comments.
- data/runs.db: SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, size 311296, LastWriteTimeUtc 2026-11-08T15:31:17Z. These match the brief.

## Requirements (Section 18 T18, 14.7, 14.2, 17.5, D-14)
- Print includes Strategy and excludes the Advisor. `PRINTED_TABS` now drops only `advisor`. The test `prints every Strategy section…` asserts the exact section list, the four Strategy headings, SWOT/MVP/GTM content, all 6 risk descriptions and warning signs, the ranking `<details>` open, 0 folded toggles and 0 chat reads. `prints the Advisor nowhere even when it was the open tab` covers the case where printing starts from the Advisor tab.
- Folded panels open. The new `layout` step clicks `button[aria-expanded="false"][aria-controls]` inside `printedRef` only. In the app's source, that selector matches only `RisksSection`'s `DetailToggle`. `ResultsHeader` tabs have no `aria-expanded`, StrategyTab's change button has no `aria-controls`, and the Radix popovers (ExportMenu, IndustryCombobox) are outside the printed layout. The risk toggles update a `Set` functionally, so pressing all of them opens every row. The existing `<details>` effect is unchanged apart from its guard.
- The page is restored after printing. The test checks that the selected tab is kept, 0 `details[open]` remain and every risk toggle is collapsed again.
- Runs without strategy: Strategy is left out of the print, so the printed page is the same five M2 tabs as before. The existing RunPage print tests pass unchanged. This interprets 14.7 by not printing the "generate" offer and its form. It keeps M2 print output identical and is recorded in the report (decision 2). Not a blocker.
- Markdown: `ExportMenu` is unchanged. The test asserts exactly one `GET /api/runs/run-123/report.md` with no query and an empty body, for runs with and without strategy, and that the saved file equals the response. D-14 backend coverage is T9's, and the coder re-ran it (68 passed).
- JSON: the saved file `toEqual(STRATEGY_DONE.result)`, and `swot`, `mvp`, `gtm` and `constraints` each match the fixture.
- "Edit and re-run" end to end: runs the real RunPage, then NewValidationPage, then ReviewStep. The constraints panel opens prefilled and the `POST /api/runs` body is exact, with only the filled constraint fields.
- Print CSS: hiding `button[aria-expanded][aria-controls]` on paper hides only the risk "Show/Hide details" toggles and the header popover trigger. Citation chips are not affected.
- A failed section's "Try again" button still appears on paper (report decision 4). This is cosmetic and fixing it needs a T14 file, so it is not a blocker.

## Verification (reviewer re-runs)
- `npx vitest run src/features/run/exportRun.test.tsx src/features/run/RunPage.test.tsx`: 2 files, 45 passed (8 new + 37 existing).
- `npm run typecheck`: exit 0 (app and e2e).
- `npm test`: 35 files, 477 passed. 0 lines matching `unhandled|onUnhandledRequest|MSW]`. 5 "not wrapped in act" lines, the same count reported for T16/T17.
- `npm run build`: exit 0. Entry `index-DY1vOW76.js` 268.79 kB / 85.56 kB gzip, the same entry chunk as T17. RunPage chunk 141.46 / 35.31 kB.
- Full backend suite not required: no backend file changed.

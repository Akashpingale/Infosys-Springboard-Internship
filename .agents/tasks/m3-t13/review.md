# T13 review: Frontend foundation

Verdict: **APPROVED**. No blockers.

## Scope and file control
- `hashes.py check` against the coder's start baseline (49 uncommitted M3 files; it held no web file) lists only the 18 web files in the report. All 49 baseline files (backend, tests, Streamlit `frontend/analysis_views.py`) are unchanged. No backend file changed, so the brief does not require the backend suite.
- `types.gen.ts` (git-ignored) SHA-256 is `A03D7C42…8CF7C9`, the same as the report's before and after value.
- `RunPage.tsx` is not in the entry's "Existing files" list. T13's own requirements put work there: "Edit and re-run carries constraints" (the navigate state) and seven tabs "with placeholder tabs" (the panels). The edit is limited to that work plus `PRINTED_TABS`, which keeps print output as it is today. The coder recorded this as a plan-vs-code point. It is accepted as necessary and minimal.
- Nothing from T14 or later was built. Strategy and Advisor are `EmptyState` placeholders. `e2e/mockApi.ts`, `server.ts`, `fixtures.ts` and `StageTracker.tsx` are unchanged. New files have no comments.

## Existing-test edit
`web/src/features/run/RunPage.test.tsx` has four hunks: a title word, the exact tab list with the two names added, two added steps in the arrow-key cycle, and `toHaveLength(5)` changed to `7`. These fall under Section 20.4 ("add the two names to the expectation"), and every comparison is still exact. No assertion was removed or loosened. `undo_check.py` was re-run: the reversed file hashes to `3F64BA11…CC7668`, equal to the `.orig` copy. Its git blob `f138f261…` equals `HEAD:web/src/features/run/RunPage.test.tsx`.

## Requirement check (Section 18 T13, 14.1–14.3, 14.8, 17.4/17.5, 20.3–20.5)
- **Switch:** on by default, shown only when `meta.strategy.available`, and the helper text is the exact 14.2 copy. Turned off, it sends `include_strategy: false` and no constraints.
- **Constraints panel:** a native `<details>`, closed by default and open when prefilled. It has the planned fields and the 14.2 copy. Every option, range, length limit and message comes from `meta.strategy.constraints`; the narrowed-meta test proves this. Only filled fields are sent, trimmed and typed, and the request bodies are asserted exactly.
- **Edit and re-run:** sends `detail.constraints ?? null` through router state. `fromConstraints` maps nulls to unset, and the stored constraints are re-sent exactly.
- **Strategy mutation:** `useGenerateStrategy` posts `{mode}` (default `missing`), plus `constraints` only when they are given. It sets the cached state to the backend's `queued`, so the existing `refetchInterval` rule restarts polling. The test shows one read in 2 s while done, then reads resume, reach 7 stages and stop.
- **Chat hooks:** thread query, send with AbortController and `cancel()`, which rejects with `ChatCancelled` rather than the offline error, and clear. The Node AbortController stub is test-only.
- **Tracker:** 4 or 7 rows come from data, with the backend's labels. Tests cover this; the tracker was not edited.
- **Tabs:** seven tabs in the 14.1 order, roving tabindex, arrow keys wrap, one tabbable. The row has `min-w-0 max-w-full overflow-x-auto`, and an effect scrolls only the row.
- **MSW and fixture:** handler factories are in `strategyHandlers.ts`. `strategyFixture.synthetic.json` was spot-checked and validates as backend `PipelineResult` with swot/mvp/gtm/constraints and 0 key-shaped strings.

## Verification run by the reviewer
- `npm run typecheck`: clean (app and e2e).
- `npm test`: 24 files, 334 passed (295 baseline + 39 new).
- `npm run build`: passed; entry chunk `index-On-fyt_e.js` 268.78 kB / 85.53 kB gzip (baseline 268.78 / 85.54), so it did not grow.
- Spot-check, because the unit test only asserts classes. A throwaway Playwright spec under `.agents/tasks/m3-t13/review_check/` uses the existing mock API. It loaded `/runs/run-complete` and `/runs/run-partial` at 390, 820 and 1440 px and stepped through all seven tabs. Each time it found no page sideways scroll, `scrollX` 0, and the focused tab inside the row: 6/6 passed. The ui_v2 screenshots spec was not run. The preview server was stopped afterwards.
- `data/runs.db`: SHA-256 `00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D`, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17Z, unchanged at the start and the end.
- No `.env` or `data/runs.db` was opened, no live call was made, and there was no branch, commit, push, reset, revert or stash.

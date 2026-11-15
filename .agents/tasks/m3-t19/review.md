# T19 review: Browser tests, accessibility and screenshots

Verdict: **APPROVED**. No blockers.

Sources: the plan's T19 entry (l.1309), 14.8, 17.5, 20.4, 20.6 and 20.8; the brief, including the last addendum; `report.md`; the diff of `web/e2e/mockApi.ts` and `web/playwright.config.ts`; the five new e2e files; the first-run and resume logs in this folder.

## Method

The run context asks me to re-run the whole gate. The brief's last addendum, a user instruction, tells the T19 reviewer to check the evidence instead, and to re-run only where a file changed after its logged run or the coder made a fix. I followed the addendum.

- I re-ran `npm run typecheck`, because the coder's fix (`focus-m3.spec.ts`) is part of the e2e typecheck.
- I re-ran `e2e/focus-m3.spec.ts`, the only file changed after the first-run logs.
- I did not re-run `screens-m3.spec.ts`. It rewrites `docs/assets/ui_v3/*.png`, which are project files. Its files and PNGs are byte-identical to the tested state.
- `npm test`, the build and the other specs were not re-run. No file they read changed after their logs.

## Evidence that the logs tested the current files

- `review_check.py` (`review-checks.log`, `review-checks-end.log`) compares current hashes with `baseline_hashes.json`, the T19 start baseline. Only 49 entries differ:
  - the five new e2e files;
  - `mockApi.ts` and `playwright.config.ts` (clean at the start, so they show as "new");
  - the 42 new `docs/assets/ui_v3` PNGs.
- No backend, `web/src`, docs (other than ui_v3) or existing-spec file changed, so the backend suite is not required.
- All 54 entries of `resume-final-hashes.txt` match the current files. `resume-tested-hashes.txt` differs from it only by `focus-m3.spec.ts`.
- Write times all come before the runs that tested them:
  - The e2e files (newest 17:42:59) come before `pw-screens-3.log` (18:02:40) and `pw-gate.log` (18:05:50 to 18:11:05).
  - `focus-m3.spec.ts` (18:39:06) comes before `resume-typecheck.log` (18:39:29) and `resume-pw-focus.log` (18:41:03).
  - `web/src` (newest 17:14:16, T18) comes before `npm-test.log` (started 18:04:26) and `build.log` (18:05:26).
  - The ui_v3 PNGs (18:01:40 to 18:02:39) fall inside the passing screens run.
- `npx playwright test <six specs> --list` (`review-pw-list.log`) collects 288 tests: 42 + 60 + 42 + 42 + 81 + 21. Every test position equals the position in the logs (for example `keyboard-m3.spec.ts:89:3`, `focus-m3.spec.ts:71:3`, `accessibility.spec.ts:19:3`). The coder's "positions are not source lines" note is a transform artefact that also shows in the unchanged M2 specs. It is not a sign of edited files.

## Gate evidence

| Gate | Evidence | Result |
|---|---|---|
| Typecheck | `typecheck.log`, `resume-typecheck.log`, my `review-typecheck.log` | Clean |
| `npm test` | `npm-test.log` | 35 files, 477 passed (same as T18). 0 lines for `unhandled`, `onUnhandledRequest`, `MSW` or `matching request handler`. stderr was captured: 21 `stderr |` blocks and the 5 known "not wrapped in act" lines, so a missing MSW line means none was printed. vitest only reads `src/**/*.test.{ts,tsx}` |
| Build | `build.log` | Entry `index-DY1vOW76.js` 268.79 kB / 85.56 kB gzip, the same chunk name and size T18's review accepted. T19 changed no `web/src` file |
| screens-m3 | `pw-screens-3.log` | 42 passed: screenshot, no sideways scroll, 44 px targets at 390 px, no `POST /api/runs` and no `POST …/strategy` |
| axe, keyboard, motion, existing specs | `pw-gate.log` | 204 passed (accessibility-m3 42, keyboard-m3 60, accessibility 81, keyboard 21). 0 "moderate or minor" lines, although test stdout does reach this reporter |
| Focus rings (coder's fix) | `resume-pw-focus.log`; my re-run `review-pw-focus.log` | 42 passed both times. Tab stops equal the listed controls on every screen, with the same counts in both runs |
| ui_v2 | `review-check` [3] vs `ui_v2_hashes_before.txt` | 81 = 81, 0 differ, newest write 2026-11-02 |
| data/runs.db | Get-FileHash / Get-Item | 00A4F859…8337D, 311296, 2026-11-08T15:31:17Z, unchanged; no -wal or -journal file |
| Undo proof | `undo_check.py`, re-run (read-only git) | `mockApi.ts`: 0 removed, 276 added. `playwright.config.ts`: 0 removed, 2 added. Both undo hashes equal HEAD |

## Coverage against the T19 entry

- Mock: `mockApi.ts` gains the strategy routes (l.607, 202 `{run_id, state}` = `RunStarted`) and the chat routes (l.585: GET thread, POST reply, DELETE 204, 502 `llm_api_error`). These match `routes/chat_routes.py`, `models/chat.py`, `utils/errors.py:29-32` and the MSW handlers in `web/src/test/strategyHandlers.ts`. The `POST /api/runs` throw (l.652) is unchanged. The diff is extend-only, as 20.4 allows.
- Screens: all 14 entry screens are in `screensM3.ts`, each run at 390, 820 and 1440 px. All 42 PNGs are valid, at the viewport width, or at the element width for the MVP and GTM element shots. The ones I opened show the intended state: seven-stage tracker, empty, failed, pending, error with the draft kept, full, constraints open, MVP plan and strategy running.
- Output path: screenshots go to `docs/assets/ui_v3` only (`SHOTS_DIR_M3`, playwright.config.ts l.23).
- Keyboard spec items, all in `keyboard-m3.spec.ts`:
  - the seven tabs (exact list, arrow cycle and wrap, active tab in view, one `tabindex="0"`, no page scroll);
  - the constraints panel (keyboard only);
  - the composer (Shift+Enter, Enter, exact POST body, a single "Advisor replied." announcement, focus kept);
  - the suggestions;
  - the confirm dialogs (clear dialog, and regenerate confirm with no POST).
- Reduced motion: checked on all 14 screens at three widths.
- Touch targets: measured at 390 px. This follows docs/10, which requires 44 px below `sm` and documents the 820 px exception and the citation-chip exception. Text fields are left out because 14.8.3 lists only buttons, radios, selects and chips.
- 20.6 focus rings: covered by `focus-m3.spec.ts`.
- New files have no comments and no `.only`, `.skip` or `.fixme`. The edits to existing files follow those files' own style.

## Observations (not blocking)

- In the `strategy-running`, `strategy-partial` and `strategy-failed` mocks, `strategyResult()` (mockApi.ts l.160) nulls the missing parts but keeps the full fixture's `executive_summary` and `verify_next`. A real snapshot recomputes both (`orchestrator.py:384`, `with_derived_fields` in `agents/derived.py`). As a result, `strategy-running-*.png` shows the "First release …" and "Go-to-market, start here …" summary lines and the first-experiment checklist item while MVP is running and GTM is waiting, next to the tile "Not generated: the MVP plan and the go-to-market plan." The existing M2 `run-partial` mock does the same thing (ui_v2 `results-partial` shows "5 competitors found" next to "Competitors found: Not analysed"). Under D-15 these screenshots are layout evidence, and the layout and accessibility gates are unaffected. T21 should not present these screenshots' summary lines as real mid-run output.
- The Launch region text field is 42 px on a phone, the height of the shared `TextInput`. This is outside 14.8.3's list, and changing it would mean editing an earlier shared component.

## Housekeeping

- Files written, all in this folder: `review_check.py`, `review_png_sizes.py`, `review-checks.log`, `review-checks-end.log`, `review-pw-list.log`, `review-typecheck.log`, `review-pw-focus.log`, `review-pw-output/` (Playwright output via `--output`), `review.md`, `review.json`.
- `web/e2e-results.json` and `web/test-results` were not touched.
- Playwright started `vite preview` and stopped it after the focus run. Afterwards there were no node processes and no Playwright Chromium processes, and ports 4173, 5173 and 8000 were free. The Google Chrome processes on the machine are the user's own and were left alone.
- No `.env` file and no `runs.db` content was opened. Nothing was committed, pushed, reset, reverted or stashed.

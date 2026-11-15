# T19 report: Browser tests, accessibility and screenshots

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T19 (line ~1310), with 14.8 (responsive and accessibility rules), 20.4 (mockApi.ts and the Playwright screen list: extend only), 20.6 (browser gates for the new screens) and 17.5 (`mockApi.ts`: strategy and chat routes, still throws on an unexpected `POST /api/runs`). Nothing from T20 or later was built.

This task ran in two sessions. The first workflow run built T19 and stopped inside the step on a usage limit. Its session kept working until about 18:11 and left the files and logs listed below. This resume session did not repeat that work. Following the orchestrator's correction, it:

1. recorded the hashes of every T19 file as the tested state;
2. checked coverage against the T19 entry and 20.6;
3. confirmed the fingerprints and the undo proof;
4. fixed the one gap it found and re-ran only the affected spec and command.

No web/src, backend, docs (other than `docs/assets/ui_v3/`) or existing spec file changed in T19. The full backend suite was not run, because no backend file changed.

## Files

| File | Status | Diff | Purpose |
|---|---|---|---|
| `web/e2e/mockApi.ts` | changed (named in T19's entry, 20.4 "extend only") | +276 −0 vs HEAD (clean at T19 start) | Adds the `/api/meta` `strategy` and `chat` blocks; the synthetic strategy result (`src/test/strategyFixture.synthetic.json`, read like the other fixtures); a seven-stage helper; five strategy runs (`run-strategy`, `-progress`, `-running`, `-partial`, `-failed`); the Advisor conversation, empty, full and reply bodies; `GET`, `POST` and `DELETE /api/runs/{id}/chat` and `POST /api/runs/{id}/strategy` routes; the `thread` and `ask` mock options; and `constraints: null` on every run detail, as the T8 backend returns. The `POST /api/runs` throw is untouched |
| `web/playwright.config.ts` | changed (named in T19's entry) | +2 −0 vs HEAD | `SHOTS_DIR_M3 = '../docs/assets/ui_v3'`, so the M3 screenshots never go to ui_v2 |
| `web/e2e/screensM3.ts` | new | 224 lines | The 14 M3 screens (name, path, mock, ready, `after` steps, optional element `shot`, and `targets`: the regions that hold new controls). Reuses the `review-step` steps from `screens.ts` read-only |
| `web/e2e/screens-m3.spec.ts` | new | 72 lines, 14 tests × 3 widths | Screenshot per screen and width to `docs/assets/ui_v3/`; no sideways scroll; 44 px targets at 390 px; no `POST /api/runs` and no `POST …/strategy` |
| `web/e2e/accessibility-m3.spec.ts` | new | 37 lines, 14 × 3 | axe (wcag2a, 2aa, 21a, 21aa) on every M3 screen; serious or critical fails, moderate or minor is printed |
| `web/e2e/keyboard-m3.spec.ts` | new | 258 lines, (6 + 14) × 3 | The keyboard items of the entry and the reduced-motion check on every M3 screen |
| `web/e2e/focus-m3.spec.ts` | new (resume session) | 113 lines, 14 × 3 | 20.6 "focus ring on every reachable control": a Tab walk over each screen's new controls (see Decisions 7) |
| `docs/assets/ui_v3/*.png` | new | 42 files, 9,659,678 bytes | `<screen>-<width>.png` for 14 screens × 390, 820, 1440. All 42 written 18:01:40 to 18:02:39 by the passing run in `pw-screens-3.log` |

`hashes.py compare` against `baseline_hashes.json` (recorded 17:24:27, before any T19 edit) lists exactly these files: the five new e2e files, `mockApi.ts`, `playwright.config.ts` and the 42 PNGs. `mockApi.ts` and `playwright.config.ts` show as "new" only because they were clean committed files at the start, so they were not in the uncommitted baseline. No other file differs. The new files have no comments or docstrings (plan 0.5). The edits to the two existing files follow their commented style.

`resume-tested-hashes.txt` (18:24:22) holds the SHA-256 of all 53 e2e, config and ui_v3 files as tested by the first-run logs. `resume-final-hashes.txt` (18:45:07) differs from it only by the new `web/e2e/focus-m3.spec.ts` (4812EA8E119048B0A80FB3F2750DEBEC7A5F3E18FA8BF63B210C93A4F74D8134), which `resume-pw-focus.log` tested.

## Requirement mapping

| T19 requirement | Where | Evidence |
|---|---|---|
| Extend `mockApi.ts` | Hunks listed under Existing-test edits | `resume-undo-check.log`: 0 lines removed |
| Extend the Playwright specs | Four new specs and `screensM3.ts`; the existing four specs and `screens.ts` are byte-identical to HEAD | `git status` |
| Review step with constraints open | `review-constraints`: review step, "Resources and goals (optional)" opened | 3 PNGs, axe, motion, targets, focus |
| Run progress with seven stages | `run-progress-seven-stages`: `run-strategy-progress`, market running, four waiting | 3 PNGs, axe, motion, focus (no new control, so no target measurement: Decisions 4) |
| Strategy empty | `strategy-empty`: `run-complete` (no strategy) → Strategy tab, "No strategy yet." | same |
| Strategy running | `strategy-running`: `run-strategy-running`, SWOT done, MVP running, GTM waiting; tracker and "Results so far" | 3 PNGs, axe, motion, focus (no new control: Decisions 4 and 5) |
| SWOT and risks | `strategy-swot-risks`: Strategy tab, first risk detail opened | same |
| MVP | `strategy-mvp`: jump to MVP plan, "How the ranking works" opened; element shot `#strategy-mvp` | same |
| GTM | `strategy-gtm`: jump to Go-to-market; element shot `#strategy-gtm` | same |
| Strategy partial | `strategy-partial`: GTM failed, SWOT and MVP present | same |
| Strategy failed | `strategy-failed`: all three strategy stages failed | same |
| Advisor empty, conversation, pending, error, full | `advisor-empty` (starter questions), `advisor-conversation` (two exchanges, follow-ups), `advisor-pending` (`ask: 'hang'`, "Thinking"), `advisor-error` (`ask: 'fail'`, 502, draft kept), `advisor-full` (turn limit 2, "This conversation is full.") | same |
| Each at 390, 820, 1440 | Three projects `w390`, `w820`, `w1440` in `playwright.config.ts` | 42 tests per spec |
| Axe on all | `accessibility-m3.spec.ts` | `pw-gate.log`: 42 passed, 0 serious or critical, 0 moderate or minor lines |
| Keyboard: seven tabs | `the seven result tabs cycle with the arrow keys, stay in view and never move the page` (exact list of 7 labels; ArrowRight through all 7 and wrap; ArrowLeft wrap; each tab focused, selected, inside the tab list's box; one `tabindex="0"`; no sideways page scroll; focus ring) | `pw-gate.log` |
| Keyboard: constraints panel | `the constraints panel opens and fills with the keyboard alone` (Tab from the switch to the summary, Enter opens, selects by arrows, radios by Space and arrows, region typed with counter "4 / 60", Enter closes; rings on summary, select, radio and text field; no sideways scroll; no `POST /api/runs`) | `pw-gate.log`, `pw-kbd-2.log` |
| Keyboard: composer | `the composer: Shift+Enter starts a line, Enter sends, the reply is announced and focus stays` (exact POST body, "Advisor replied." in a polite live region once, reply in the thread, focus kept, box cleared) | `pw-gate.log` |
| Keyboard: suggestions | `a suggested question is reached with Shift+Tab and sent with Enter` (exact POST body = the suggestion) | `pw-gate.log` |
| Keyboard: confirm dialog | `the clear dialog opens on Keep it, keeps focus inside, closes with Escape and clears with Enter` (no DELETE on Escape, DELETE on "Clear it") and `the regenerate confirm opens on Keep it and Escape sends nothing` (no `POST …/strategy`) | `pw-gate.log` |
| Reduced motion on the new screens | `reduced motion on the Milestone 3 screens`: every element's transition and animation duration ≤ 0.05 s under `prefers-reduced-motion: reduce`, 14 screens × 3 | `pw-gate.log`: 42 passed |
| Screenshots in `docs/assets/ui_v3/` | `screens-m3.spec.ts` writes to `SHOTS_DIR_M3` | 42 PNGs; ui_v2 81 of 81 unchanged |
| No sideways scroll on any screen | `screens-m3.spec.ts` (every screen and width); also the tabs and constraints keyboard tests | `pw-screens-3.log` |
| 44 px touch targets on new controls | `screens-m3.spec.ts` `smallTargets` at 390 px over each screen's `targets` | `pw-screens-3.log`: 0 small targets |
| Mock API still throws on any unexpected `POST /api/runs` | Throw unchanged; `screens-m3` asserts no `POST /api/runs` and no `POST …/strategy` on every screen | `resume-undo-check.log`, `pw-screens-3.log` |
| 20.6 focus ring on every reachable control | `focus-m3.spec.ts` | `resume-pw-focus.log`: 42 passed, Tab stops = controls on every screen |
| Fix every problem found | See Problems found | No app change was needed |

## Tests (186 new Playwright tests)

- `screens-m3.spec.ts` (42): one test per screen, titled with the screen name: `review-constraints`, `run-progress-seven-stages`, `strategy-empty`, `strategy-running`, `strategy-swot-risks`, `strategy-mvp`, `strategy-gtm`, `strategy-partial`, `strategy-failed`, `advisor-empty`, `advisor-conversation`, `advisor-pending`, `advisor-error`, `advisor-full`; × 3 widths.
- `accessibility-m3.spec.ts` (42): `<screen> has no serious or critical violation`; × 3.
- `keyboard-m3.spec.ts` (60): the six keyboard tests named in the mapping (18), and `<screen> does not animate` for the 14 screens (42).
- `focus-m3.spec.ts` (42): `<screen>: every control the Tab key reaches shows a focus ring`; × 3. Tab stops per screen, the same at all three widths: review-constraints 7, run-progress-seven-stages 1, strategy-empty 3, strategy-running 23, strategy-swot-risks 45, strategy-mvp 43, strategy-gtm 43, strategy-partial 32, strategy-failed 9, advisor-empty 7, advisor-conversation 7, advisor-pending 3, advisor-error 7, advisor-full 4.

The existing `accessibility.spec.ts` (81) and `keyboard.spec.ts` (21) pass unchanged against the extended mock (`pw-gate.log`). The existing `screenshots.spec.ts` (81, ui_v2) was not run (brief).

## Existing-test edits

Both edits are pure additions. `undo_check.py` (written by the first-run session at 18:11:56; re-run in this session, `resume-undo-check.log` 18:16:52) parses `git diff -U0`, counts removed lines, deletes the added lines from the working file and compares the bytes with `git show HEAD:<file>`.

| File | Rule | Before | After | Undo proof |
|---|---|---|---|---|
| `web/e2e/mockApi.ts` | 20.4 "Playwright screen list and `mockApi.ts`: extend only" | 7 insertion points, no line changed: after `const AGRITECH` (l.37); end of `META` (l.91); after `STAGES_DONE` (l.114); in `detail()` (l.138); end of `RUNS` (l.222); end of `MockOptions` (l.265); before the `/api/runs/{id}` handler (l.335) | +6 (synthetic fixture), +14 (`strategy`, `chat` meta), +40 (seven stages, `strategyResult`), +1 (`constraints: null`), +177 (five strategy runs, conversation, threads, reply), +7 (`thread`, `ask` options), +31 (chat and strategy routes) | 0 removed, 276 added; undo SHA-256 c383e64283775c70c8b0138714a676822343cb20bdbc9696ed8b76615adf51cf = HEAD |
| `web/playwright.config.ts` | Named in T19's entry | `export const SHOTS_DIR = '../docs/assets/ui_v2';` then a blank line | The same, then `/** Milestone 3's screens (plan T19) go to their own folder, so the ui_v2 set is never rewritten. */` and `export const SHOTS_DIR_M3 = '../docs/assets/ui_v3';` | 0 removed, 2 added; undo SHA-256 f6830f15d9010b02472c592a158d78985b98045166b71a8f6b165ed8dbc2e7f6 = HEAD |

`screens.ts`, `screenshots.spec.ts`, `accessibility.spec.ts`, `keyboard.spec.ts` and `e2e/tsconfig.json` were not edited. No MSW handler or unit test was touched.

## Problems found and how they were handled

1. **44 px check on a text field** (`pw-screens-1.log`, 17:37:05: `review-constraints` and `strategy-empty` at 390 px, `input "" 282x42`). The field is Launch region. It uses the shared `TextInput` (`Field.tsx` `CONTROL`: `px-3 py-2`), the same height as every existing text field on the review step. 14.8.3 lists buttons, radios, selects and chips, and text fields are not on that list. The check was therefore limited to buttons, links, selects, summaries, radio and checkbox labels, and tabs. The field was not changed. The constraints panel's selects (`min-h-[44px] sm:min-h-0`), radio labels (`min-h-[44px]`) and summary all measure 44 px or more.
2. **Constraints keyboard test** (`pw-a11y-kbd-1.log`, 17:42:44: "Resources and goals summary has no focus ring" at all three widths). The first version focused the summary by script after mouse clicks, so `:focus-visible` did not apply. That was a test fault. The test now reaches the summary with Tab from the switch, which is what a keyboard user does (edit at 17:42:59). `pw-kbd-2.log` (17:43:24): 3 passed. The app was not changed.
3. **One timeout** (`pw-screens-2.log`, 18:01:07: `advisor-error` at 390 px, `page.goto` over 60 s, in a run that took 17.7 min while the machine was busy). It passed in the next run of the same files (`pw-screens-3.log`, 18:02:40: 42 passed in 1.1 min). Nothing was changed for it.
4. **Coverage gap found in the resume check: focus rings** (20.6: "focus ring on every reachable control" for the new screens). The keyboard spec checked rings on nine named controls only. `focus-m3.spec.ts` was added and only it was run. Run 1 passed 42 with a simpler check. The check was then strengthened to prove the walk reached every control. Run 2 failed 6 (`strategy-empty` and `strategy-running`, each at 3 widths): my expected list counted controls inside closed `<details>`, which still report a box to `getClientRects()` but which Tab skips. That was a test bug. Run 3, with a filter for folded content: 42 passed, and on every screen the Tab stops equal the controls listed.

No problem needed an application change, and no `web/src` file changed in T19 (newest `web/src` write 17:14:16, T18).

## Decisions and plan-vs-code points

1. **New specs and a new screen list instead of extending the existing ones.** 20.4 allows extending the screen list. But `screenshots.spec.ts` writes every entry of `screens.ts` to ui_v2, and the brief forbids touching ui_v2. So the M3 screens live in `screensM3.ts`, and the four new specs read it. The seven-tab cycle is in `keyboard-m3.spec.ts`; the existing keyboard spec is unchanged. 17.5's wording ("extended screen list; keyboard spec covers seven tabs and the composer") is met by the new files.
2. **The gate was run spec by spec, not with `npm run test:e2e`** (20.8). That script runs every spec, including the ui_v2 screenshots spec, which the brief forbids.
3. **Touch targets are measured at 390 px only**, below the `sm` breakpoint (640 px). This is docs/10's rule ("44 px touch targets below `sm`"; 820 px keeps the 40 px desktop row, a documented exception). Citation chips are excluded under the documented WCAG 2.5.8 inline exemption (24 px). Radios and checkboxes are measured by their label, as docs/10 describes for checklists.
4. **Screens with no new control** are `run-progress-seven-stages` (only the M2 "Cancel run") and `strategy-running` (tracker plus the M2 Overview, whose new tile and summary lines hold only citation chips). They have no `targets`, so they get no 44 px measurement. The focus walk covers their whole `main`.
5. **"Strategy running" is the run page while stage 6 runs.** While a run is active, `RunPage` shows the tracker and the Overview "Results so far" (the existing partial-result behaviour of 14.3). The tabs return when the run ends. That is T14's code, captured as it is.
6. **The MVP and GTM screens are element shots** (`#strategy-mvp`, `#strategy-gtm`, 358 px wide at 390). The whole tab is one long page, already shown in `strategy-swot-risks` and `strategy-partial`. Axe, the sideways check and the targets still use the whole page.
7. **Focus walk method** (`focus-m3.spec.ts`). It lists the visible, tabbable, unfolded controls in the screen's `targets` (or `main`), one stop per radio group, and focuses the first. Shift+Tab then Tab sets keyboard modality. It then presses Tab until focus leaves the regions (cap 500). Every stop must have an outline style other than `none`, at least 2 px wide (the existing keyboard spec's test), and the listed controls must all be reached in order.
8. **`advisor-full` uses a turn limit of 2**, a value the backend setting allows (`CHAT_MAX_USER_TURNS`). That shows the full state without 50 messages.
9. **Seen at three widths, left as the earlier task decided.**
   - The Overview Strategy tile wraps to its own row at 1280 px and wider (T16 decision 6, `strategy-running-1440.png`). It is not a 14.8 defect.
   - Risks shows the failed message without its own "Try again" (T14 decision 6: one button per stage, which SWOT carries).
   - "The rest of the strategy is below." also appears on the last section (14.10 copy).
10. **Line numbers in the Playwright logs are not source lines.** The list reporter's test positions do not match the source here, for example `keyboard-m3.spec.ts:89` for the test at source line 77. They look like positions in the transformed file. The link between log and file is the timestamps and hashes above.

## Commands run and results

First-run session. The logs are in this folder. The orchestrator confirmed that no file in web/e2e, web/src, `playwright.config.ts` or ui_v3 changed after 18:05:50, so these logs tested the current files. The command column is reconstructed from each log's header and test list; for `pw-gate.log` it is the command line seen in the process list.

| Command | Log (written) | Result |
|---|---|---|
| Start-of-task hashes (`hashes.py` save mode; SHA-256 of `docs\assets\ui_v2\*.png`) | `baseline_hashes.json`, `ui_v2_hashes_before.txt` (17:24:27) | Start baseline, before any T19 edit. Not overwritten |
| `npm run typecheck`; separate `tsc` runs | `typecheck-1.log` (17:33:12), `tsc-app.log` (17:33:33, empty), `tsc-e2e.log` (17:33:39, empty) | Clean |
| `npx playwright test e2e/screens-m3.spec.ts --reporter=list` | `pw-screens-1.log` (17:37:05) | 40 passed, 2 failed (problem 1) |
| `npx playwright test e2e/accessibility-m3.spec.ts e2e/keyboard-m3.spec.ts --reporter=list` | `pw-a11y-kbd-1.log` (17:42:44) | 99 passed, 3 failed (problem 2); axe 42 of 42 passed |
| same, constraints test only | `pw-kbd-2.log` (17:43:24) | 3 passed |
| `npx playwright test e2e/screens-m3.spec.ts --reporter=list` | `pw-screens-2.log` (18:01:07) | 41 passed, 1 failed (problem 3) |
| same | `pw-screens-3.log` (18:02:40) | **42 passed** (1.1 min). The 42 ui_v3 PNGs date from this run |
| `npm run typecheck` | `typecheck.log` (18:04:16) | **Clean**, app and e2e |
| `npm test` | `npm-test.log` (18:05:12, started 18:04:26) | **35 files, 477 passed**. 0 lines matching `unhandled`, 0 `onUnhandledRequest`, 0 `MSW`; 5 `not wrapped in act` lines, the same as T16 to T18 |
| `npm run build` | `build.log` (18:05:26) | Built. Entry `index-DY1vOW76.js` **268.79 kB / 85.56 kB gzip**, the same chunk name and size as T18. That is +0.01 kB / +0.02 kB gzip over the 268.78 / 85.54 baseline, within the small allowance 20.3 asks for (stated here as 1 kB). T19 changed no `web/src` file. RunPage 141.46 / 35.31 kB |
| `npx playwright test e2e/accessibility-m3.spec.ts e2e/keyboard-m3.spec.ts e2e/accessibility.spec.ts e2e/keyboard.spec.ts --reporter=list` | `pw-gate.log` (18:11:05) | **204 passed** (5.2 min): accessibility-m3 42, keyboard-m3 60, accessibility 81, keyboard 21. 0 "moderate or minor" lines |

The dist that the preview server used was built from the same sources as T18's build: same chunk names (`index-DY1vOW76`, `RunPage-ZP7MxAET`, `ConstraintsPanel-D-UpNPIQ`), and no `web/src` change after 17:14:16.

This session:

| Command | Log (written) | Result |
|---|---|---|
| `Get-CimInstance Win32_Process` (node, chrome) at start | – | The first-run gate (`pw-gate.log`) was still running. It ended by itself at about 18:11 and was not touched. Since then 0 node processes |
| `python hashes.py compare` (at the start and after the edit) | – | Only the T19 files listed under Files; the second run adds `focus-m3.spec.ts` |
| `python undo_check.py` | `resume-undo-check.log` (18:16:52) | `mockApi.ts`: removed 0, added 276, match True. `playwright.config.ts`: removed 0, added 2, match True |
| `Get-FileHash` of the 53 e2e, config and ui_v3 files | `resume-tested-hashes.txt` (18:24:22) | Tested state recorded |
| `Get-FileHash` of `docs\assets\ui_v2\*.png` vs `ui_v2_hashes_before.txt` | `resume-checks.log` (18:46:40) | 81 before, 81 now, **0 differ**; newest ui_v2 write 2026-11-02 |
| `Select-String` on `npm-test.log` | `resume-checks.log` | `unhandled` 0, `onUnhandledRequest` 0, `MSW` 0 |
| `Get-FileHash` / `Get-Item data\runs.db` | `resume-checks.log` | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z (**unchanged**) |
| `npm run typecheck` (after each of the three versions of `focus-m3.spec.ts`) | `resume-typecheck.log` (18:39:29, last) | Clean all three times |
| Process and port check before each Playwright run | – | 0 node processes and ports 4173 and 5173 free each time; 0 Playwright Chromium processes before run 1 |
| `npx playwright test e2e/focus-m3.spec.ts --reporter=list`, run 1 | overwritten | 42 passed (simpler check) |
| same, run 2 | overwritten | 36 passed, 6 failed (problem 4, test bug) |
| same, run 3 | `resume-pw-focus.log` (18:41:03) | **42 passed** (1.2 min) |
| `Get-FileHash` after the edit | `resume-final-hashes.txt` (18:45:07) | Only `focus-m3.spec.ts` differs from the tested state |
| Process and port check at the end | – | 0 node, python or msedge processes; 0 Playwright Chromium; ports 4173, 5173 and 8000 free |

`npm test` and the build were not re-run in this session. They do not read e2e files: vitest includes only `src/**/*.test.{ts,tsx}`, and the build compiles `src`. The other specs were not re-run, because their files are unchanged since the logs above.

## Not done or not verified

- The ui_v2 screenshots spec was not run (brief). With the extended mock it would now draw the M3 additions (Include strategy switch, seven tabs) into ui_v2, so it should stay unrun unless you decide to refresh ui_v2.
- `npm run test:e2e` as one command was not run, for the same reason.
- No print-media browser check. T18 noted that its print rule (hide "Hide details" on paper) has no unit test. T19's entry does not ask for a print check, so none was added. Printing remains verified only by T18's unit tests.
- The screenshots render the synthetic fixture (`strategyFixture.synthetic.json`, D-15). They show layout, not real model output. The live UI walkthrough (20.7 L-4) is not executed.

Nothing was committed, pushed, reset, reverted or stashed. No branch was created or switched. No `.env` file and no `data/runs.db` content was opened. No backend or dev server was started. Playwright's `webServer` started `vite preview` on 127.0.0.1:4173 for each of the three focus runs and stopped it afterwards. No live provider call was made. Logs and helper scripts are only in `.agents\tasks\m3-t19\`.

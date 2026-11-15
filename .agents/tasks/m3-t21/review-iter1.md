# T21 review: documentation, demonstration material and completion

Verdict: **CHANGES_REQUESTED**. Two blockers, both false statements in the T21 documents. That breaks the T21 entry ("only verified facts") and X-12. Everything else checked out.

## Blockers

**B-1. docs/12 overstates the existing-test edits.** `docs/12_milestone3_test_report.md:101-102` says of `RunPage.test.tsx`: "Two of its tests gained MSW handlers, as setup only".
- Only one test did. `git diff HEAD -- web/src/features/run/RunPage.test.tsx` adds `server.use(...)` handlers only in `moves between tabs with the arrow keys`: the `/api/meta` handler (T14 report l.68) and `chatThreadOk(() => EMPTY_THREAD)` (T17 report l.77).
- No other test in the file uses `META` or `chatThreadOk`.
- Consequence: the test report lists the existing-test edits (plan 20.4) wrongly. A reader checking those edits will look for a second changed test that does not exist.
- Fix: write "One of its tests, `moves between tabs with the arrow keys`, gained two MSW handlers (`/api/meta` and the chat thread), as setup only, for the requests the new tabs make."

**B-2. docs/12 and docs/10 say the browser specs were run "one at a time".** The phrase appears at `docs/12_milestone3_test_report.md:23` ("Playwright, one spec at a time") and `:119-120` ("which is why the specs were run one at a time"). It also appears at `docs/10_ui_design_system.md:359` ("During Milestone 3 the specs were run one at a time").
- This is false. `m3-t19/pw-gate.log` is one invocation ("Running 204 tests using 1 worker", "204 passed (5.2m)") covering four specs together: accessibility-m3 (42), keyboard-m3 (60), accessibility (81) and keyboard (21).
- The 288 results come from three runs: `pw-screens-3.log` (screens-m3, 42), `pw-gate.log` (the four specs above, 204) and `resume-pw-focus.log` (focus-m3, 42).
- Consequence: the test report describes a procedure that was not followed.
- Fix: in the three places, say the specs were named on the command line, never run as the whole suite, in the three runs above, so the ui_v2 screenshot spec never ran. Then re-run your link and count checks on the edited files.

## Evidence (all offline; files written only in this folder)

- **State.** Branch main, HEAD a098aef. `data/runs.db` checked with Get-FileHash and Get-Item at start and end: 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes, 2026-11-08T15:31:17Z, no -wal or -journal file.
- **Changed files.** `hashes.py check` against `baseline_hashes.json` lists only README.md, docs/10, docs/11 and docs/12.
  - The baseline is T20's 138 entries plus T20's six files, which match `m3-t20/tested-hashes.txt`.
  - README and docs/10 were clean at 9b5350c, so their whole diffs are T21's (+162 −43 and +119 −10).
  - The four current hashes equal `final-hashes.txt`.
  - docs/agile, docs/assets/ui_v2, the plan and the KIRO files are unchanged.
- **Logged runs still valid.** Outside `.agents/`, the only files newer than T20's final suite run (14:19) are the four documents (469 files scanned).
  - Under `web/`, only `focus-m3.spec.ts` (18:39:06) is newer than the T19 gate. It was tested afterwards (`resume-pw-focus.log` 18:41, and the T19 reviewer's run at 19:16) and type-checked clean (`resume-typecheck.log` 18:39:29).
  - Vitest and the app tsconfig cover `src/` only, so the `npm test` and build logs still apply.
  - T21 changed no code, so no regression suite needed a re-run.
- **Counts.** My `pytest --collect-only` (ids not saved) collected 2454 tests in 64 files.
  - 818 tests in 18 `test_m3_*` files, and every per-file count equals docs/12. 1636 tests in the 46 earlier files.
  - `test_m2_domains` 92; `test_m2_report` 24 from 22 functions; 36 planted contract cases.
  - Backend logs: `pytest-full-3.log` and `review-pytest-full.log` both say 2454 passed, 1 warning.
  - `npm-test.log`: 477 tests in 35 files; 182 in the 15 new files, each per-file count equal to docs/12; 0 MSW-unhandled lines.
  - `build.log`: entry 268.79 / 85.56 kB, RunPage 141.46 / 35.31 kB.
  - Playwright: 42 + 204 + 42 = 288 passed; 369 tests in total including the unrun 81-test ui_v2 screenshot spec.
  - I swept every count phrase in the four documents, and each one matches a measured value.
- **Links and references.** My checker uses GitHub heading anchors, and its self-test catches both planted faults.
  - The four documents have 107 relative links, 0 broken. All 33 Markdown files have 130, 0 broken.
  - All 113 file:line references in docs/11 land on the cited symbol (`review-refs.log`).
  - All 181 cited test names, paths and web test titles exist.
- **Code facts spot-checked against source**, all matching:
  - settings, bounds and fallback;
  - error codes, statuses and messages;
  - the `/api/meta` blocks;
  - model limits;
  - check constants;
  - notice codes and severities;
  - severity, score, capacity, statement and channel order;
  - digest trim order;
  - Advisor messages and limits;
  - `start_strategy` and `_finish`;
  - role lines;
  - D-01 to D-15 against plan 1.2.
- **P-3.** No claim remains in README or docs/10 that a live React run is unverified. The five runs and nine rows match the brief. Parity and Streamlit retirement are left to the user.
- **Live sections and privacy.** Every live section reads "not executed" (docs/12 §1, §4, 4.1, 4.2; docs/11 status and §14; README; docs/10 §9). The 15.5 privacy sentence is in README.
- **Facts for the user.** docs/agile is not edited. The facts list's line references are right (140, 171 to 173).
- **Bug sources.** All seven fixed bugs and both unfixed items have first-hand records: T4 B-1, the user's T7 request, T10 first run, T11 first run, T15 typecheck, T20 row 9 and point 10, T20 point 9, T12 point 3.
- **git status.** 148 entries outside `.agents/` (35 modified, 113 untracked), grouped the same way as the coder's report.
- **Secret scan.** My own scanner (AIza, AQ., gsk_, tvly-, sk-, Bearer, PRIVATE KEY; `.env` and `.db` files excluded and never opened) listed 857 files, scanned 720, skipped 137 binary, and found 0 hits.

## Notes (not blocking)

- Facts item 3 cites PRODUCT_BACKLOG.md lines 151 to 158. The rows end at 157.
- The final report should carry forward the T20 reviewer's note that a retro run's `strategy_seconds` includes saved seconds when the saved run already has part of its strategy.
- The `strategy-running` screenshot shows the full fixture's summary lines (T19 review). docs/10 and docs/11 call the screenshots synthetic layout evidence, which covers it.

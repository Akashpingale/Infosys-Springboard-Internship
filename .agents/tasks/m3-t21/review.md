# T21 review, iteration 2: B-1 and B-2 re-check

Verdict: **APPROVED**. Both blockers are fixed, and no blockers remain.

Scope: the brief's iteration-2 addendum allows four checks. All other T21 checks were completed in iteration 1 and were not repeated. The iteration-1 review is kept as `review-iter1.md` and `review-iter1.json`.

## 1. B-1 and B-2 fixed, and the wording matches the evidence

**B-1** (docs/12 lines 100 to 103). The paragraph now says that one test, `moves between tabs with the arrow keys`, gained two MSW handlers (`/api/meta` and the chat thread) as setup only.

- `git diff HEAD -- web/src/features/run/RunPage.test.tsx` shows that only that test's `server.use(...)` gained handlers: `http.get(`${API_URL}/api/meta`, () => HttpResponse.json(META))` and `chatThreadOk(() => EMPTY_THREAD)`.
- `chatThreadOk` is `http.get(`${runUrl(id)}/chat`, ...)` (`web/src/test/strategyHandlers.ts:125-127`), which is the chat-thread handler.
- No other test in the file uses `META`, `chatThreadOk` or `/api/meta`.

**B-2** (docs/12 line 23 and lines 119 to 124; docs/10 lines 359 to 362). Both documents now say the results come from three runs that named their specs on the command line, never from the whole suite. I counted the distinct test indexes per spec in each log (`iter2_review_pw_specs.py`):

- `pw-screens-3.log`: screens-m3 42. Header "Running 42 tests", result "42 passed (1.1m)".
- `pw-gate.log`: accessibility-m3 42, keyboard-m3 60, accessibility 81 and keyboard 21. Header "Running 204 tests", result "204 passed (5.2m)".
- `resume-pw-focus.log`: focus-m3 42. Result "42 passed (1.2m)".
- `screenshots.spec.ts` appears in none of the three logs, and 42 + 204 + 42 = 288.
- T19 report lines 115, 123 and 140 record the matching commands, each naming its specs (`npx playwright test e2e/... --reporter=list`).
- `web/e2e` holds seven specs, and `test:e2e` is `playwright test`. This supports "runs all seven specs, including the screenshot spec".
- No "one at a time" claim about specs remains in the four documents. The two remaining "at a time" matches are about Advisor questions (README:131) and the responsive layout (docs/10:267), not specs.

## 2. Only docs/10 and docs/12 changed after the first review

- README (EF560E91…7D3D) and docs/11 (AED213D3…9BC9) still equal `final-hashes.txt`.
- `newer_than.py` (464 tracked and untracked files) and `review_newer.py` (469 files, ignored ones included) both find only docs/12 (16:29:02) and docs/10 (16:29:04) newer than 14 Nov 15:38:00, which is before the first review started.
- `hashes.py check` against `baseline_hashes.json` lists only the four T21 documents, the same as iteration 1.
- `git status` shows 148 entries outside `.agents/` (35 modified, 113 untracked), the same counts as iteration 1.
- Undo proof (`iter2_review_undo.py`). Reversing the three docs/12 replacements and the one docs/10 replacement in memory gives 308 and 447 lines. The resulting hashes equal the iteration-1 values 410EABC8…BC9 and 4FEBE0DD…0BC exactly, so nothing else in those files changed. Both files are LF only.

## 3. Link check and quoted-count check

- `check_links.py`: 4 documents, 107 relative links, 0 broken (docs/10 42, docs/12 6), exit 0.
- My own checker, `review_links.py`, run on docs/10 and docs/12: 48 relative links, 0 broken.
- `check_counts.py`: 72 expected phrases, 0 missing, exit 0.
  - The measured values are unchanged: gate 204, screens 42, focus 42, 288 passed out of 369.
  - The three new quoted counts (42, 204 and 42 tests) match the logs above.
  - The new docs/10 sentence contains no counts.

## 4. data/runs.db

Get-FileHash and Get-Item at the start and end of this review both give 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes and LastWriteTimeUtc 2026-11-08T15:31:17Z. There is no -wal or -journal file. Branch main, HEAD a098aef.

No project file was modified. Files written in this folder: `iter2_review_pw_specs.py`, `iter2_review_undo.py`, `iter2-review-runs-db.txt`, `review-iter1.md`, `review-iter1.json`, this file and `review.json`.

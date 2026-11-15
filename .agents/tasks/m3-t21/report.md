# T21 report: Documentation, demonstration material and completion

Plan entry: `MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md` Section 18, T21 (line 1334), with Section 22 (documents and their content), 17.6 (documentation files), 15.5 (privacy sentence), 20.5 to 20.8 (fixtures, live protocol, gate), 21 (A-X, X-12), 25 (checklist), precondition P-3 and the brief's T21 rules. Only documents changed. No code, test, configuration or `docs/agile/*` file was edited, no test suite was re-run (see Decisions 2), no backend or dev server was started, and no live call was made.

## Files

`hashes.py check` against `baseline_hashes.json` (recorded before the first edit: 144 uncommitted files) lists exactly the four files below. `README.md` and `docs/10_ui_design_system.md` show as "new" there because they were clean committed files at the start, so they were not in the uncommitted baseline.

| File | Status | Diff | SHA-256 (final) | Purpose |
|---|---|---|---|---|
| `README.md` | changed (named in T21's entry) | +162 −43 | EF560E91EDB0101213EEE717C163533B0670EAC245E127FDAF866AB966F97D3D | Milestone 3 section (what it adds, how to use it in the React interface, cost, Advisor limits, the 15.5 privacy sentence); diagram with the three strategy agents and the Advisor; P-3 corrections; the eight new settings; new and changed routes; Milestone 3 test commands and live scripts; measured counts; project structure; documentation table; roadmap |
| `docs/10_ui_design_system.md` | changed (named in T21's entry) | +119 −10 | 4FEBE0DDCE3B38B882DD70AB98F7E08A5F1185BE926BD815CF982298D58160BC | P-3 correction in section 9 (the five live React runs, from the brief's verified facts); seven tabs and seven tracker rows noted; section 10 counts and commands; new section 11: Milestone 3 components with their guarantees, visual rules, the 14 `ui_v3` screens with one embedded screenshot, measured responsive and accessibility results |
| `docs/11_milestone3_strategy_and_advisor.md` | new | 631 lines | AED213D34A8BBF4EA0758B5CA370EA930ADEF631EAAB53D4DF970DE7A9C47B96 | Audit table I-01 to I-21 with real names and file:line, architecture diagram, stage rules, digest, models, checks and notices, formulas and constants, prompts (trimmed), the Advisor, API/settings/storage, UI map, D-01 to D-15 as built, known limits |
| `docs/12_milestone3_test_report.md` | new | 308 lines | 410EABC88A4D5C2B94264603D1F7E5E54749C48D9E949A492F3403C5B22C6BC9 | Measured counts per suite and per new test file, browser specs, contract check, secret scan, acceptance coverage map, live checks L-1 to L-5 and the review checklist all **Not executed**, unverified list, bugs found and fixed (each with the test that pins it), open issues, fixtures |

Full hashes are also in `final-hashes.txt`. The two existing files keep their line endings (README CRLF, docs/10 LF, like the unmodified docs/08); the two new files are LF. With `core.autocrlf=true`, git prints "LF will be replaced by CRLF" for docs/10; that is a checkout conversion, not a content change.

Helper files, all in this folder: `hashes.py` (copy of T20's; `save` never overwrites a baseline), `baseline_hashes.json`, `find_lines.py` (line lookups for the audit table), `newer_than.py` (files changed after a given time), `counts.py` (per-file counts from the logs), `check_links.py` (relative links and anchors, plus `selftest.md`), `check_refs.py` (cited file:line, test names, web test titles, paths), `check_counts.py` (quoted counts against measured logs), `secret_scan.py` (copy of T12's), `git_status_summary.py`, and the logs listed under Commands.

## Requirement mapping

| T21 / Section 22 requirement | Where |
|---|---|
| Update `docs/10` (new components and screens, with `ui_v3` screenshots) | docs/10 section 11: 12 component rows, visual rules, the 14 screens table linking the 1440 px PNG of each, one embedded screenshot (`advisor-conversation-1440.png`, viewed), measured accessibility table; intro, sections 7 and 10 updated |
| Update README (Strategy and Advisor usage, endpoints, settings, test commands, privacy sentence; 17.6 also "how to run strategy, Advisor limits") | README "Milestone 3: strategy and Advisor" (usage steps, cost, limits, "What is sent where"), API table rows for `/strategy` and the three chat routes plus changed rows, eight settings rows, test commands and live scripts |
| Write `docs/11` (audit table, architecture diagram, stage rules, models, checks, scoring formulas and constants, prompts trimmed, API additions, UI map, D-01 to D-15, known limits) | docs/11 sections 2 to 14, one per item |
| Write `docs/12` (measured test counts, fixtures, live results table filled only from real runs, review checklist outcomes, unverified list, bugs found and fixed first-hand) | docs/12 sections 1 to 7; live table and checklist all **Not executed** |
| Only verified facts; no invented dates, stand-ups, retrospectives or sign-offs; "not executed" where not run; each bug has a source | Every count from a log (table below); every file:line checked (`refs-check-3.log`); every test name checked to exist; dates only from log or file timestamps; every bug row names the test that pins the fix |
| P-3: docs/10 and README no longer claim a live React run is unverified | docs/10 section 9 (run table); README "Two interfaces" status row and paragraph, M2 Task 3 row, "Testing the React interface" last paragraph, Roadmap. `Select-String` for "unverified / not yet / live run" in both files shows no remaining claim (only section titles and accurate statements) |
| Every live section marked "not executed" | docs/12 section 1 row, section 4 table (L-1 to L-5), 4.1, 4.2 (8 items); docs/11 status line and section 14; README Milestone 3 section, live-scripts paragraph, roadmap; docs/10 section 9 (L-4) |
| Final secret scan | 838 files listed, 701 text files scanned, 137 binary skipped, **0 hits** (`secret-scan.log`) |
| Final test counts | docs/12 sections 1 and 2, from the last runs on the unchanged code (Decisions 2) |
| `git status` summary | Below |
| List of facts for `docs/agile` | Below; `docs/agile/*` not edited |
| Tests: link check on documents | `check_links.py`: 4 documents, 107 relative links, 0 broken; all 33 Markdown files, 130 links, 0 broken; self-test finds both planted faults |
| Tests: test counts quoted equal the measured counts | `check_counts.py`: 69 quoted counts, 0 mismatches |

## Measured values and where they come from

No file outside `.agents/` changed after the logged runs: `newer_than.py 2026-11-14T14:19:42` found 0 of 462 files newer than T20's final full suite; `newer_than.py 2026-11-13T18:05:50 web/` found only `web/e2e/focus-m3.spec.ts` (18:39:06), which `resume-pw-focus.log` (18:41:03) tested.

| Value in the documents | Source |
|---|---|
| Backend 2454 passed, 1 warning | `m3-t20/pytest-full-3.log` (14 Nov 14:19:42) and `m3-t20/review-pytest-full.log` (14:32:17); `pytest-collect-ids.log` here: 2454 collected |
| 64 files; 1,636 tests in 46 files from before M3; 818 in 18 `tests/test_m3_*.py` files, per-file counts | `pytest-collect-ids.log`, counted by `counts.py` |
| `test_m2_domains.py` 92; `test_m2_report.py` 24 from 22 functions; 36 planted contract cases | same log, and `def test_` count of the file |
| `npm test` 477 in 35 files; 182 in 15 new files; per-file counts | `m3-t19/npm-test.log` (13 Nov 18:05:12) |
| Typecheck clean | `m3-t19/typecheck.log` (18:04:16) |
| Entry 268.79 kB / 85.56 kB gzip; RunPage 141.46 kB / 35.31 kB | `m3-t19/build.log` (18:05:26) |
| Playwright: accessibility-m3 42, keyboard-m3 60, accessibility 81, keyboard 21 (204) | `m3-t19/pw-gate.log` (18:11:05) |
| screens-m3 42; focus-m3 42 | `m3-t19/pw-screens-3.log` (18:02:40); `m3-t19/resume-pw-focus.log` (18:41:03) |
| 369 total, 288 passed, 81 not run | sum of the above plus the unrun `screenshots.spec.ts` (27 screens × 3, `screens.ts` unchanged) |
| Secret scan 838 / 701 / 137 / 0 | `secret-scan.log` (final run, 14 Nov 15:38) |
| Five live React runs, nine rows, run ids and statuses | The brief's verified facts; `data/runs.db` was not opened. Last write 2026-11-08T15:31:17Z from `Get-Item`; pre-M3 table layout from the T2 report |

## Existing-test edits

None.

## Decisions and plan-vs-code points

1. **Audit table rebuilt from the code.** T0's entry says the audit table goes into the T21 document, but no T0 audit was saved in the repository or in `.agents/tasks/`. The table in docs/11 section 2 was therefore built from the code with real names and file:line. `check_refs.py` printed the target line of all 113 references (`refs-check-3.log`); each names the cited symbol. One reference was corrected during the check (`agents/mvp_agent.py:370`, a blank line, became `:353`, `assign_tiers`).
2. **Counts measured, suites not re-run.** T21 changes no code, and the last runs of every suite on the same code are logged (above). Re-running them would repeat checks on unchanged code, and the brief's final verification step runs the complete list once anyway. I proved the code is unchanged since those runs and only collected the backend test ids (`pytest --collect-only`, no test executed) to get per-file counts. If the final verification measures different numbers, docs/12 and README need the new ones.
3. **No probe that imports `config`.** `config.py` calls `load_dotenv` at import, so a custom script that builds a digest would read `.env`. Instead of quoting T3's digest sizes, docs/11 cites the passing tests `test_the_saved_live_results_fit_under_the_cap_with_nothing_dropped` and `test_the_saved_milestone_2_runs_fit_under_the_cap`. (The pytest collection above imports `config` as every earlier suite run did.)
4. **Bug sources.** docs/12 section 6 names the repository test that pins each fix, not `.agents/` files, which may not be committed. Only fixes to code are listed; faults in new tests found during development are not. Two defects found and not fixed are listed separately: the raw strategy stage keys in the report's "Time taken" line (T20 point 9) and the missing secret scan on Advisor replies (T12 point 3).
5. **P-3 wording.** The documents state the verified facts (five real React runs, all before Milestone 3, so four-stage). They do not say parity is confirmed or that Streamlit should be retired; README keeps "Streamlit stays" and says confirming parity and deciding on retirement are still open. That decision is the user's (US-WEB2-13, US-WEB2-14).
6. **README text outside Milestone 3 left as written**, including "Milestone 2 (in progress)", except where it now contradicts a verified fact: the M2 Task 3 row said the pipeline had not run "through the API or either UI", and the "Two interfaces" line said all 1636 backend tests are unchanged (Milestone 3 changed one line of `tests/test_run_store.py`, approved in T2).
7. **Privacy sentence** (15.5) is in README's Milestone 3 section, "What is sent where". "Nothing is sent to analytics" holds: no analytics dependency in `web/package.json` or `requirements.txt`.
8. **Secret scan and my own log.** The first scan reported 9 hits, all in my own `pytest-collect.log`: the parameter ids of `tests/test_m2_llm_errors.py::test_keys_tokens_and_authorization_values_are_redacted` contain that test's fake key-shaped values. I wrote `pytest-collect-ids.log` with the ids cut before `[`, deleted the raw log (my own helper output), and the re-run found 0. Any saved `pytest --collect-only` or `-v` output would trip the scan the same way.
9. **Counts in the scan row** are those of the final scan; later files in this folder (this report, the last logs) are not in them.
10. **`web/.env.local`** is reported by `check_refs.py` as a missing path: README mentions it as an optional file the user may create. Not a defect.

## Fingerprints and state

| Check | Start of T21 | End of T21 |
|---|---|---|
| `data/runs.db` SHA-256 (Get-FileHash) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D |
| `data/runs.db` size, LastWriteTimeUtc (Get-Item) | 311296, 2026-11-08T15:31:17Z | 311296, 2026-11-08T15:31:17Z |
| Files differing from the baseline (`hashes.py check`) | 144 hashed | only README.md, docs/10, docs/11, docs/12 |
| Branch, HEAD | main, a098aef | main, a098aef |

### git status summary (`git_status_summary.py`, before this report was written: 521 entries)

| Area | Modified | Untracked |
|---|---:|---:|
| repository root (`.env.example`, `README.md`, `app.py`, `config.py`, `orchestrator.py`) | 5 | 0 |
| backend: agents / models / routes / utils | 3 / 2 / 2 / 6 | 6 / 2 / 2 / 1 |
| backend: tests | 1 (`tests/test_run_store.py`) | 20 |
| scripts | 0 | 4 |
| Streamlit (`frontend/analysis_views.py`, the `full=True` path) | 1 | 0 |
| web: app and unit tests / browser tests / config | 12 / 1 / 1 | 28 / 5 / 0 |
| docs (docs/10) / docs/assets/ui_v3 | 1 / 0 | 3 (docs/11, docs/12, docs/test_runs_m3/README.md) / 42 |
| workflow notes (`.agents/`) | 0 | 373 |

Nothing is committed: every Milestone 3 change is in the working tree on `main` at a098aef.

## Facts for you to enter into docs/agile (not edited by me)

1. **Stale: `docs/agile/PRODUCT_BACKLOG.md`, section 6 addendum, US-WEB2-13 (line 140)** reads "PLANNED (needs real API credits; not yet run)". Verified fact: `data/runs.db` holds 9 rows, 4 seeded demonstration rows and 5 real runs started from the React interface: `a7c930285cf1437780f8408b4c7c670d` complete, `3a88f83cd7464d2e9b742a55aab6e98c` complete, `1ea1af5c13fb424dadd7e10424e44448` partial (Gemini quota error), `1c169d267b6a4d4ebdb3a26e2d4cdc84` complete, `a078ebf6a9514ef78e318b7b2db8aaa6` partial. The file was last written 2026-11-08T15:31:17Z, before Milestone 3, so all five are four-stage runs. Whether this closes US-WEB2-13, and so US-WEB2-14 and the Streamlit decision, is yours to decide.
2. **Stale: same file, "What is not done" (lines 171 to 173)**: "US-WEB2-13 is open. No validation has been run live from the React interface. Everything verified so far replays the saved 27 October live results or seeded history rows." The same five runs contradict it. The next bullet ("Streamlit is therefore not retired … until US-WEB2-13 is closed") depends on your decision in item 1.
3. **Superseded numbers: same file, "Measured results" (lines 151 to 158)** are from before Milestone 3 (1636, 295 in 20 files, 268.78 kB, 183, 27 screens, 81 screenshots). Milestone 3 measurements: backend 2454 passed, 1 warning (1636 + 818 new); `npm test` 477 passed in 35 files (295 + 182); typecheck clean; entry bundle 268.79 kB, 85.56 kB gzipped; Playwright 288 passed in six specs (186 new, 102 earlier), the ui_v2 screenshot spec (81) not run; axe 0 serious or critical on the 14 new screens and the 27 earlier ones at three widths; 42 screenshots in `docs/assets/ui_v3/`; secret scan 0 hits. `npm run test:e2e` now runs 369 tests, including the ui_v2 screenshot spec.
4. **Milestone 3 stories (if you add them):** SWOT and risk (R1), MVP recommendation (R2), go-to-market (R3), Startup Advisor (R4), strategy on a saved run, and the React Strategy and Advisor tabs are built and covered by automated tests with fakes only ("VERIFIED WITH FAKES" in that file's vocabulary). Live checks L-1 to L-5 are not executed.
5. **US-WEB2-04** speaks of "the four stages"; a run with strategy now shows seven.
6. **Open items to track:** the full report's "Time taken" line names strategy stages by key; Advisor replies are not scanned for secrets; the real `data/runs.db` will be migrated in place at the next backend start (two columns and the chat table; rows unchanged, hash and mtime change).
7. **Dates I can state are file timestamps only:** the Milestone 3 task folders run from 2026-11-10 (T1) to 2026-11-14 (T20, T21). I wrote no stand-up, retrospective, sprint date or sign-off.

## Commands run and results

All from the repository root in PowerShell, `$env:PYTHONIOENCODING="utf-8"`, Python `.\.venv\Scripts\python.exe -B`.

| # | Command | Result |
|---|---|---|
| 1 | `Get-ChildItem -Force .agents\tasks`; test for `.agents\tasks\m3-t21` | Task folders listed; no `m3-t21` yet (first iteration) |
| 2 | `Get-ChildItem -Recurse -File .agents\tasks` | Earlier reports and logs located; no T0 audit file exists |
| 3 | `Get-Content` of `m3-t19\review.json`, `m3-t20\review.json` | Both APPROVED |
| 4 | `New-Item .agents\tasks\m3-t21`; `Copy-Item m3-t20\hashes.py` | Folder and helper created |
| 5 | `hashes.py save`; `Get-FileHash`/`Get-Item data\runs.db`; `git branch --show-current`; `git rev-parse --short HEAD` | "saved 144 files" (before any edit); 00A4F859…8337D, 311296, 2026-11-08T15:31:17Z; main; a098aef |
| 6 | `Select-String` on the plan's headings; `Get-ChildItem docs` | Read only |
| 7 | `git status --porcelain -uall` (filtered); `git log --oneline -5` | 33 modified tracked files outside `.agents/`, untracked M3 files, 42 ui_v3 PNGs; HEAD a098aef |
| 8 | `Select-String` lookups of constants, functions and classes in the M3 modules, `config.py`, `utils/errors.py`, `routes/meta_routes.py` | Read only |
| 9 | `find_lines.py` (`find-lines.log`) and further lookups (Basis, StageTracker, Claim, ideas, scripts, fakes, evidence ids, LLM errors) | Line numbers for the audit table |
| 10 | `pytest --collect-only -q -p no:cacheprovider` | **2454 tests collected** in 6.09 s, exit 0, no test executed |
| 11 | Summary lines of the T19 and T20 logs | Values in the table above |
| 12 | `newer_than.py 2026-11-14T14:19:42`; `newer_than.py 2026-11-13T18:05:50 web/` | 0 of 462 newer; 1 of 136 (`focus-m3.spec.ts`, tested afterwards) |
| 13 | `counts.py` (three runs: an f-string error, then unparsed ANSI codes, then correct; `counts.log`) | 64 files, 2454; 18 M3 files, 818; 46 earlier files, 1636; web 35 files, 477, new 15 files, 182; Playwright per spec |
| 14 | `Select-String config.py dotenv` | `load_dotenv` at import, so no custom probe was run (Decisions 3) |
| 15 | `Get-Date` | 2026-11-14 15:09:24 |
| 16 | Read two ui_v3 PNGs (`strategy-swot-risks-1440`, `advisor-conversation-1440`) | Captions checked against what they show |
| 17 | `check_links.py` (`link-check-1.log`, `-2.log`, `-final.log`); `--all` (`link-check-all.log`, `-2.log`); self-test on `selftest.md` (`link-check-selftest.log`) | 4 docs: 107 relative links, 2 external not fetched, **0 broken**; 33 Markdown files: 130 links, **0 broken**; self-test: 4 checked, both planted faults reported |
| 18 | `check_refs.py` (`refs-check-1.log`, `-2.log`, `-3.log`) | 113 file:line references, each printed with its target line; one fixed (Decisions 1); 67 test names and 6 web test titles all found; 1 expected note (Decisions 10) |
| 19 | `secret_scan.py` (copy of T12's) | First run: 9 hits, all in my own `pytest-collect.log` (Decisions 8) |
| 20 | Strip parameter ids into `pytest-collect-ids.log`; `Remove-Item pytest-collect.log`; point `counts.py` at the new log; re-run `counts.py` | 2462 lines, 2454 ids; counts unchanged |
| 21 | `secret_scan.py` | 827 listed, 690 scanned, 137 binary, **0 hits** |
| 22 | `hashes.py check` (`hash-check-1.log`); runs.db fingerprint; `git diff --numstat` of the two edited files | Only the four documents; fingerprint unchanged |
| 23 | Line-ending count (Python, read only) and `git config --get core.autocrlf` | README CRLF only; docs/10, 11, 12 LF only; docs/08 LF, docs/09 CRLF; autocrlf true |
| 24 | Collected counts: `test_m2_domains.py`, `test_m2_report.py` (and its `def test_` count), the planted contract cases | 92; 24 from 22; 36 (docs/11 corrected from "22 tests" to "24 tests from 22 test functions") |
| 25 | `check_counts.py` (`count-check-1.log`, `-2.log`, `-final.log`) | **69 quoted counts, 0 missing**; every other count phrase listed and reviewed |
| 26 | `Select-String` / grep on README, docs/10 and docs/agile (read only) | No remaining stale claim in the edited files; stale lines in `PRODUCT_BACKLOG.md` located (facts above) |
| 27 | `hashes.py check` (`hash-check-2.log`); runs.db fingerprint (`runs-db-fingerprint-end.txt`); `git_status_summary.py` (`git-status-summary.log`) | Only the four documents; unchanged; 521 entries, grouped above |
| 28 | `secret_scan.py` (final, after the last document edit except the scan row) | **838 listed, 701 scanned, 137 binary, 0 hits**; docs/12 row updated to these numbers |
| 29 | `check_counts.py` (`count-check-final.log`), `check_links.py` (`link-check-final.log`), `hashes.py check` (`hash-check-final.log`), runs.db fingerprint, `Get-FileHash` of the four documents (`final-hashes.txt`) | 69 of 69; 0 broken; only the four documents; 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z; hashes as in Files |

No `.env` file was opened or printed, and `data/runs.db` was only fingerprinted. Nothing was committed, pushed, reset, reverted or stashed, and no branch was created or switched. No server, browser or Playwright run was started. Logs and helper scripts are only in `.agents\tasks\m3-t21\`.

## Iteration 2 (review findings B-1 and B-2)

Scope, from the orchestrator's note: fix only the two blockers in `review.md`, change nothing else, re-run only the link check and the quoted-count check, and run no test suite. Only `docs/12_milestone3_test_report.md` and `docs/10_ui_design_system.md` changed. README and docs/11 are byte-identical to iteration 1.

Start state: the four documents' hashes equalled `final-hashes.txt` (`iter2-start-hashes.txt`), and the `data/runs.db` fingerprint was unchanged (`runs-db-fingerprint-iter2-start.txt`). `baseline_hashes.json` already existed and was not overwritten.

### B-1: docs/12, the `RunPage.test.tsx` edit

Source: `git diff HEAD -- web/src/features/run/RunPage.test.tsx`. Only `moves between tabs with the arrow keys` gained handlers in its `server.use(...)`: a `GET /api/meta` handler returning `META`, and `chatThreadOk(() => EMPTY_THREAD)`.

Before (docs/12 lines 100 to 102):

```
**Existing test changed.** `src/features/run/RunPage.test.tsx`: the expected tab list grew from five
to seven names and the arrow-key cycle gained Strategy and Advisor (plan Section 20.4). Two of its
tests gained MSW handlers, as setup only, for the requests the new tabs make.
```

After (lines 100 to 103):

```
**Existing test changed.** `src/features/run/RunPage.test.tsx`: the expected tab list grew from five
to seven names and the arrow-key cycle gained Strategy and Advisor (plan Section 20.4). One of its
tests, `moves between tabs with the arrow keys`, gained two MSW handlers (`/api/meta` and the chat
thread), as setup only, for the requests the new tabs make.
```

### B-2: "one at a time"

Source: the three Playwright logs in `m3-t19\`. `pw-screens-3.log`: "Running 42 tests using 1 worker" (screens-m3). `pw-gate.log`: "Running 204 tests using 1 worker" (accessibility-m3, keyboard-m3, accessibility and keyboard, named together on one command line, T19 report line 123). `resume-pw-focus.log`: "Running 42 tests using 1 worker", "42 passed (1.2m)" (focus-m3). 42 + 204 + 42 = 288.

docs/12 line 23, before:

```
| Browser tests | Playwright, one spec at a time (section 2.3) | **288 passed** in six specs. The ui_v2 screenshot spec (81 tests) was not run |
```

After:

```
| Browser tests | Playwright, specs named on the command line in three runs (section 2.3) | **288 passed** in six specs. The ui_v2 screenshot spec (81 tests) was not run |
```

docs/12, before (lines 119 and 120):

```
`npm run test:e2e` runs all seven specs, including the screenshot spec, which is why the specs were
run one at a time. The new screens are listed in
```

After (lines 120 to 124; the next line, the link to docs/10 section 11, is unchanged):

```
`npm run test:e2e` runs all seven specs, including the screenshot spec. The results above therefore
come from three runs that named their specs on the command line, never from the whole suite:
`screens-m3.spec.ts` (42 tests); the four accessibility and keyboard specs, new and earlier,
together (204 tests); and `focus-m3.spec.ts` (42 tests). The ui_v2 screenshot spec was in none of
them. The new screens are listed in
```

docs/10, before (lines 359 to 361):

```
During Milestone 3 the specs were run one at a time and the ui_v2 screenshot spec was not run, so
the images in `assets/ui_v2/` still show the interface before Milestone 3. The measured results are
in [docs/12](12_milestone3_test_report.md).
```

After (lines 359 to 362):

```
The measured Milestone 3 results, in [docs/12](12_milestone3_test_report.md), come from three runs
that named their specs on the command line, never from the whole suite: `screens-m3.spec.ts`; the
four accessibility and keyboard specs together; and `focus-m3.spec.ts`. The ui_v2 screenshot spec
was not run, so the images in `assets/ui_v2/` still show the interface before Milestone 3.
```

Wording: both documents say the *results* come from three runs, not that Milestone 3 had only three Playwright runs. T19 ran more during development (for example `pw-screens-1.log` and `pw-a11y-kbd-1.log`), and each of those also named its specs.

### Files after iteration 2

| File | Diff | SHA-256 |
|---|---|---|
| `README.md` | +162 −43 (unchanged) | EF560E91EDB0101213EEE717C163533B0670EAC245E127FDAF866AB966F97D3D (unchanged) |
| `docs/10_ui_design_system.md` | +120 −10 (iteration 1: +119 −10) | 748970D50DD9AA1E1FF797B019186E0824D5E622A4377C763896C976687A9BEF |
| `docs/11_milestone3_strategy_and_advisor.md` | new, 631 lines (unchanged) | AED213D34A8BBF4EA0758B5CA370EA930ADEF631EAAB53D4DF970DE7A9C47B96 (unchanged) |
| `docs/12_milestone3_test_report.md` | new, 312 lines (iteration 1: 308) | E07E0EDDFA36E441D63F4171F22B96FC71C063EFFE8B002739DC6EE2E0917180 |

These hashes (`final-hashes-iter2.txt`) replace the docs/10 and docs/12 values in the Files table at the top. Both edited files are still LF only.

Helper change: `check_counts.py` gained three expected phrases for the new quoted counts (`` `screens-m3.spec.ts` (42 tests) ``, `together (204 tests)`, `` `focus-m3.spec.ts` (42 tests) ``), measured from `pw-screens-3.log`, `pw-gate.log` and `resume-pw-focus.log`. Its expected phrases went from 69 to 72.

### Commands run in iteration 2

| # | Command | Result |
|---|---|---|
| 1 | Read `review.json`, `review.md`, this report, the brief and the plan's T21 entry; search the four documents for "at a time" | B-1 and B-2 located; no other "one at a time" claim about specs (README's "one question at a time" and docs/10's "one layout … at a time" are unrelated) |
| 2 | `git diff HEAD -- web/src/features/run/RunPage.test.tsx`; `Select-String` for "Running N tests" and "N passed (" in the three Playwright logs; `Get-Date` | One test gained two handlers; 42, 204 and 42 tests; 2026-11-14 16:26:35 |
| 3 | `Get-FileHash` of the four documents (`iter2-start-hashes.txt`); `Get-FileHash` and `Get-Item` of `data\runs.db` (`runs-db-fingerprint-iter2-start.txt`) | Equal to `final-hashes.txt`; 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z, no -wal or -journal file |
| 4 | Three replacements in docs/12 and one in docs/10 (above); three rows added to `check_counts.py` | Done |
| 5 | `check_links.py` (`link-check-iter2.log`) | Exit 0. 4 documents, 107 relative links, 2 external not fetched, **0 broken** (docs/10: 42 links; docs/12: 6) |
| 6 | `check_counts.py` (`count-check-iter2.log`) | Exit 0. **72 expected phrases, 0 missing**. Measured values unchanged (gate 204, screens 42, focus 42, total 288 of 369). New count phrases at docs12:122 and :123 |
| 7 | `hashes.py check` (`hash-check-iter2.log`) | Only `README.md`, docs/10, docs/11 and docs/12 differ from the baseline, listed as "new" as in iteration 1 |
| 8 | `Get-FileHash` and `Get-Item` of `data\runs.db` (`runs-db-fingerprint-iter2-end.txt`) | **Unchanged**: 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z, no -wal or -journal file |
| 9 | `Get-FileHash` of the four documents (`final-hashes-iter2.txt`); `git diff --numstat HEAD` of README and docs/10; line-ending count of docs/10 and docs/12 | As in the table above; 0 CRLF in either file |
| 10 | Search of the four documents for "one spec at a time", "specs were run one", "run one at a time" and "Two of its" | No match |

Not run in this iteration, as instructed: no test suite, no secret scan, no `check_refs.py`, and no server or browser. docs/12's secret-scan row still reports iteration 1's final scan (838 listed, 701 scanned, 137 binary, 0 hits). The edits add no key-shaped text.

### Reviewer notes not acted on (orchestrator: change nothing else)

- Facts item 3 above gives `PRODUCT_BACKLOG.md` lines 151 to 158 for the "Measured results" rows. The rows end at line 157.
- Carried forward from the T20 review, not in docs/12: with `--saved` on a run that already holds part of its strategy, the retro summary's `strategy_seconds` includes the saved stages' seconds. The default L-2 input (the Milestone 2 run, which has no strategy) is not affected.
- The `strategy-running` screenshot shows the full fixture's summary lines. docs/10 and docs/11 already call the screenshots synthetic layout evidence, so nothing was changed.

No `.env` file was opened or printed, and `data/runs.db` was only fingerprinted. Nothing was committed, pushed, reset, reverted or stashed, and no branch was created or switched. Logs and helper changes are only in `.agents\tasks\m3-t21\`.

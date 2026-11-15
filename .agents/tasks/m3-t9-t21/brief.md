# Milestone 3, tasks T9 to T21: workflow brief

Repo: C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship (branch `main`, HEAD a098aef, all M3 work T1-T8 uncommitted and approved).
Plan (authoritative): C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship\MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md
Section 18 task entries: T9 at ~line 1197, T10 ~1209, T11 ~1220, T12 ~1231, T13 ~1244, T14 ~1255, T15 ~1266, T16 ~1277, T17 ~1288, T18 ~1299, T19 ~1310, T20 ~1323, T21 ~1334. Each entry lists objective, requirements (with section refs), existing files, new files, integration, dependencies, tests and result. Also read Sections 4, 10 (Advisor, R4), 11, 12 (esp. 12.2-12.5), 13, 14 (React: 14.1-14.10 incl. copy table), 15, 16, 17 (file-by-file), 19 (order and cut line), 20 (testing; 20.4 = existing tests allowed to change; 20.7 live protocol), 21 (acceptance), 22 (docs), 25 (checklist), Appendices A.4/A.5/B/C.

This is HEAVY: 13 sequential tasks across backend (T9-T12), React (T13-T19), scripts (T20) and docs (T21). Do them strictly in plan order T9, T10, ..., T21, one at a time. Do not start a task until the previous one's checks pass and its review is APPROVED.

## Per-task shape (repeat for every task)
1. Implement exactly that task's Section 18 entry and referenced sections. No features beyond the plan; nothing from a later task.
2. Run that task's tests plus the regression suites below.
3. Independent review (code reviewer gates with a verdict file per task, e.g. .agents\tasks\m3-tN\review.json); loop back to fix on rejection (max about 3 iterations per task).
4. Write .agents\tasks\m3-tN\report.md (files changed with purpose and diff size, requirement mapping, test names and counts, existing-test edits with before/after, fingerprints, plan-vs-code conflicts).
Bookkeeping and helper scripts only under .agents\tasks\m3-tN\ (one folder per task); never put helper scripts in the project tree. Leave the existing m3-t1 ... m3-t8 folders untouched.

## Stop conditions (pause with a warning notification and wait; do NOT guess)
- A blocking failure that cannot be fixed within the task's own files.
- An unclear or self-contradictory plan requirement whose choice changes behaviour or API.
- Any change that would damage existing work: editing a file that belongs to an earlier task beyond what the current task's entry names, or changing an existing response field's name/type/value.
- An existing test that fails or needs editing, unless it is covered by the pre-approved rules below.

## Pre-approved existing-test edit rules (anything else: stop and ask)
- Edits that Section 20.4 explicitly lists, done exactly as 20.4 describes.
- Updating an exact expected value (registry list, key set, stage list) to include a new value the plan adds, while keeping an exact comparison (never loosen to a subset/any check).
- Restoring a placeholder or fake for a test that exercises a placeholder/fake code path, via one pytest `monkeypatch` line, with no assertion change.
Every edit to an existing test: show before/after lines in the task report and prove that undoing it restores the previous file hash. Never delete or weaken an assertion.

## Hard constraints (every task)
- No network, no live provider/API calls, no provider credits. Tests use fakes only (tests/conftest.py autouse `fake_env` and `block_network`; tests/m3_fakes.py; MSW in web/src/test; web/e2e/mockApi.ts which must still throw on any unexpected POST /api/runs).
- Never open or print any `.env` file (one is open in the user's editor; ignore it). Fake keys in tests are built from string parts.
- Never open the real data/runs.db and never start the backend against it: opening it through RunStore would migrate it in place. If a running backend is genuinely needed (e.g. `npm run api:types`), prefer generating types from a dumped OpenAPI file (`npx openapi-typescript <tempfile> -o src/api/types.gen.ts` in web/, as T1 and T8 did). If a live process is unavoidable, start it only with RUNS_DB_PATH pointing at a temp file in that process's environment, on a non-default port, stop it afterwards, and verify the data/runs.db fingerprint. Expected fingerprint (check with Get-FileHash/Get-Item only): SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, size 311296, LastWriteTimeUtc 2026-11-08T15:31:17Z. Confirm unchanged at the end of every task.
- Do not create or switch branches; do not commit, push, reset, revert or stash.
- Preserve M1, M2 and T1-T8 work: record SHA-256 of all uncommitted M3 files at the start of each task; at the end only files the task's entry names (plus its new files and pre-approved test edits) may differ. Streamlit (frontend/) behaviour and output stay byte-identical (T9 requires this for the Markdown default).
- Do not modify KIRO_PROMPT_M2.md, KIRO_UI_UPGRADE_SPEC.md or the plan. Do not edit docs/agile/* (T21 produces a list of facts for the user to enter there). Do not modify or regenerate docs/assets/ui_v2/*.png: do NOT run the existing ui_v2 screenshots spec; T19 screenshots go to docs/assets/ui_v3/ only (configure the new spec's output path accordingly).
- T20 writes the live scripts (`scripts/run_m3_live.py`, `scripts/run_m3_retro_live.py`, `scripts/check_advisor_live.py`) and docs/test_runs_m3/README.md, and tests them only with the `--fake` flag. Never run them live. Every live section in docs (docs/12 etc.) is marked "not executed".
- T21 documents only verified facts. P-3 correction: docs/10_ui_design_system.md and README must no longer claim a live React run is unverified. Verified facts: data/runs.db holds 9 rows (4 seeded demos + 5 real React-UI runs: a7c930285cf1437780f8408b4c7c670d complete, 3a88f83cd7464d2e9b742a55aab6e98c complete, 1ea1af5c13fb424dadd7e10424e44448 partial (Gemini quota), 1c169d267b6a4d4ebdb3a26e2d4cdc84 complete, a078ebf6a9514ef78e318b7b2db8aaa6 partial). The docs/agile backlog addendum carries the same stale statement but is user-owned: list it in T21's facts-for-the-user, do not edit it.
- New files carry no comments/docstrings (plan 0.5); edits to existing files follow their own style. React work follows docs/10_ui_design_system.md (tokens, IBM Plex, icon plus word, no new hues, `dangerouslySetInnerHTML` forbidden with a guard test).
- Where plan and code conflict, follow existing code conventions and record the conflict in the task report.

## Context already established (T0-T8; reports in .agents\tasks\m3-tN\final-report.md or report.md)
- Backend: models (T1), store migration + chat_store (T2), digest + checks (T3: agents/strategy_context.py, agents/strategy_checks.py), stage plumbing (T4), real agents SwotRiskAgent/MvpAgent/GtmAgent (T5-T7; positioning always names the priority segment when one exists), strategy API + /api/meta `strategy` and `chat` blocks + `has_strategy` + RunDetail.constraints + POST /api/runs/{id}/strategy with mode missing/all (T8).
- Warnings from strategy agents are plain strings; notice templates/codes for them are T9's job (incl. `strategy_items_cut`, `strategy_text_shortened`, MVP over-capacity/constraints-assumed, GTM budget conflict, missing SWOT/MVP/segment notices). `notices.STAGE_TITLES` is pinned by tests/test_notices.py to the four M1/M2 titles; strategy titles live in `notices.STRATEGY_TITLES`.
- Markdown export: `report_markdown(result, *, full=False)` at frontend/analysis_views.py:367 and `report_file_name` :222; tests/test_m2_report.py pins 22 behaviours. The report.md route passes full=True. Default output must stay byte-identical.
- Known open points to keep in mind (do not silently change): Gemini path sets no max_output_tokens; Groq strategy calls request 6144 tokens (`STRATEGY_MAX_OUTPUT_TOKENS`); `has_strategy` costs one extra store read per list row (optional LIST_COLUMNS fix noted in T8; only do it if a task's entry calls for it).
- Frontend facts: web/src/features/results/ResultsHeader.tsx `TABS` (5 tabs, optional `tabs` prop); RunPage.tsx print effect and `panel(key)`; useRun.ts POLL_INTERVAL_MS=1500, ACTIVE=['queued','running']; Claim.tsx `ClaimItem`; lib/results.ts (`buildSourceIndex`, `collectClaims`, `resolveSources`, `splitEvidenceIds`, `claimsCiting`, `sourceKey`); StageTracker.tsx data-driven; web/src/test (setup.ts with MSW onUnhandledRequest 'error', server.ts, render.tsx `renderWithApp`, fixtures.ts, runFixtures.ts, liveAgritech.json, liveFintech.json); web/e2e/mockApi.ts (347 lines). Earlier UI decisions in force: display numbers never backend S-ids; sources keyed `analysis:id`; CSS bars not Recharts; native `<dialog>` for drawer/confirm; `useMediaQuery` chooses table or cards so only one layout is in the DOM; citation chips 24 px under the WCAG 2.5.8 inline exemption.

## Environment
Windows, PowerShell (run commands singly; multi-line foreach loops get mangled; multi-line logic goes in temp scripts). Python `.\.venv\Scripts\python.exe` (3.11.9); set `$env:PYTHONIOENCODING="utf-8"`. Node v26.13.0 / npm 11.20.0 in web/. Vite dev compiles routes lazily; kill stray msedge between CDP captures.
Commands: backend `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE`; web `npm test`, `npm run typecheck`, `npm run build`, `npx playwright test <spec>`.
Baselines after T8: backend 2195 passed, 1 warning (Starlette/httpx deprecation); frontend 295 passed in 20 files; typecheck clean; build entry chunk 268.78 kB / 85.54 kB gzip; Playwright 183 (81 screenshots + 81 axe + 21 keyboard); axe 0 serious/critical.

## Regression gates
- Every backend task (T9-T12, T20): that task's tests + full backend suite, 0 failures.
- Every frontend task (T13-T19): `npm run typecheck`, `npm test`, `npm run build` (entry chunk within the plan's allowance), plus full backend suite once per task if any backend file changed.
- T19: the new Playwright specs plus the existing axe and keyboard specs (not the ui_v2 screenshots spec); 0 serious/critical axe violations; no sideways scroll; 44 px targets on new controls.

## Final step after T21
Run everything offline: full backend suite; `npm run typecheck`; `npm test`; `npm run build`; Playwright (all specs except the ui_v2 screenshots spec, and state that it was skipped and why); `scripts/check_m3_contracts.py`; the T20 scripts with `--fake`; doc link check; secret scan of all tracked and untracked non-ignored text files (patterns AIza..., gsk_..., tvly-..., sk-..., Bearer tokens, PRIVATE KEY; .env files excluded and never opened); data/runs.db fingerprint; `git status --porcelain` grouped by area.
Write ONE consolidated report to .agents\tasks\m3-t9-t21\final-report.md covering T9-T21: per task what was built and how it maps to the plan, every changed/new file, every existing-test edit with justification, all test/build/axe numbers, remaining issues and plan-vs-code conflicts, every skipped live check (T20 scripts, live acceptance items such as A-R1..A-R4 "on every live idea", live React walkthrough), and the git status summary. Then stop. Do not commit or push.

## Addendum (orchestrator, during T14): unmocked requests in frontend tests
- `npm test` output must contain no MSW 'unhandled' / 'onUnhandledRequest' lines. web/src/test/setup.ts uses onUnhandledRequest: 'error' so no test reaches an unmocked address; a test that passes while that error prints is bypassing the safety net. Check the full `npm test` output for such lines in every frontend task (T13-T19) and in the final verification.
- Pre-approved (added to the existing-test edit rules): when new UI makes an existing test call an endpoint it did not call before, add the missing MSW handler to that test as setup only (server.use(...) with the existing fixtures or handler factories such as metaWithStrategy()), with no assertion change. List each such edit with before/after in the task report. Anything beyond setup-only handler additions still needs a stop-and-ask.
- T14 decisions already made: strategyRun.test 'opens a placeholder for the Strategy and Advisor tabs' was renamed to 'opens the Strategy tab and a placeholder for the Advisor tab' and its Strategy assertion now expects 'No strategy yet.' (14.10 empty-state copy); the Advisor assertion is unchanged. T17 replaces the Advisor placeholder, so the same kind of placeholder-to-real assertion update is expected there: keep it exact (assert the real empty-state copy from 14.10), and report it.

## Addendum (orchestrator, during T15): wiring new Strategy sections and exact lists
- Pre-approved for T15, T16 and T17: wiring the task's new section components into T14's `StrategyTab.tsx` (add the entry to `SECTIONS`; render the section or the existing `notReady(partState(...))` state) and, for T17, adding the plan's "Ask the advisor about this" prefill buttons to the Strategy section components and, only if a one-line addition fits, to the Market and Competitors tabs (T17 entry). These are integration edits the task's result depends on; list each in the task report with before/after.
- Pre-approved: extending `collectClaims` (lib/results.ts) for the new section's items as 17.5 describes (GTM in T16), and updating exact assertions in existing tests (e.g. StrategyTab.test section list, strategyClaims.test counts and `where` lists, source-drawer claim lists) by adding the new values only, keeping exact comparisons. Never remove an assertion or loosen to a subset.
- Decided: every failed Strategy section shows its own "Try again" (plan 14.4). All of them trigger the same single `missing`-mode strategy request; while it is pending every "Try again" (and Generate/Regenerate) button is disabled, so only one request is sent. Test it.
- Anything else that touches an earlier task's files still needs a stop-and-ask.

## Addendum (orchestrator): resume after the first run stopped in T19
The first run (wf_edae29bc1c556130) completed and APPROVED T9-T18 (verdicts in .agents\tasks\m3-t9 ... m3-t18\review.json; reports in each folder). It stopped inside the T19 coder step with "Usage limit reached" (an infrastructure limit, not a code failure). Do NOT redo T9-T18.
State left by the interrupted T19 coder (verified by the orchestrator, read-only):
- Changed: web/e2e/mockApi.ts, web/playwright.config.ts. New: web/e2e/accessibility-m3.spec.ts, web/e2e/keyboard-m3.spec.ts, web/e2e/screens-m3.spec.ts, web/e2e/screensM3.ts, docs/assets/ui_v3/ (42 PNGs).
- docs/assets/ui_v2: 0 files changed. data/runs.db fingerprint unchanged. No dev server, preview server, python or msedge process left running.
- Its logs in .agents\tasks\m3-t19\: typecheck clean; npm test 477 passed in 35 files; build entry 268.79 kB / 85.56 kB gzip; screens-m3 spec 42 passed; accessibility-m3 + keyboard-m3 run 1 had 3 failures (keyboard 'the constraints panel opens and fills with the keyboard alone' at all three widths), and a later re-run of that test passed 3 of 3 (pw-kbd-2.log). No T19 report and no review exist yet.
- .agents\tasks\m3-t19\baseline_hashes.json and ui_v2_hashes_before.txt were recorded BEFORE any T19 edit: use them as T19's start baseline; do not overwrite them.
Resume T19 from this state: read the plan's T19 entry and every file above, finish anything missing against the entry (14 screens x 3 widths, axe on all, keyboard spec items, reduced motion, no sideways scroll, 44 px targets on new controls), re-run the full gate yourself (typecheck, npm test with 0 unhandled lines, build, the new m3 specs plus the existing accessibility and keyboard specs, NOT the ui_v2 screenshots spec), confirm ui_v2 PNG hashes equal ui_v2_hashes_before.txt, write .agents\tasks\m3-t19\report.md, then hand over to the T19 review. Then continue with T20, T21 and the final verification exactly as this brief describes.

## Addendum (orchestrator, user instruction): do not repeat completed T19 work
The user asked that T19 work already completed in the first run is not repeated. The orchestrator checked file times: no project file under web/e2e, web/src, web/playwright.config.ts or docs/assets/ui_v3 changed after 18:05:50 on 13 Nov 2026. The first run's logs in .agents\tasks\m3-t19\ therefore tested exactly the current files and are the T19 gate evidence: typecheck.log (18:04:16, clean), npm-test.log (18:05:12, 477 passed in 35 files), build.log (18:05:26, entry 268.79 kB / 85.56 kB gzip), pw-screens-3.log (18:02:40, screens-m3 42 passed), pw-gate.log (18:11:05, 204 passed: accessibility-m3, keyboard-m3 and the existing accessibility and keyboard specs).
- T19 coder: record the tested-state hashes, do a read-only coverage check against the T19 entry, confirm ui_v2 hashes, the runs.db fingerprint and the undo proof, fix only real gaps and re-run only the affected spec, then write report.md citing those logs. No full gate re-runs.
- T19 reviewer: verify the evidence instead of repeating it. Confirm that the current hashes of the T19 files equal the tested-state hashes in the coder's report and that no file changed after the logged runs; read the logs, the specs and the code; check coverage against the T19 entry. Re-run a spec or command only if a file changed after its logged run or the coder made a fix. If you find a real gap, reject with findings as usual.
- T20 and T21 are new work and follow the normal per-task shape. The final verification after T21 still runs the complete offline check list once, as the user asked for that explicitly.

## Addendum (orchestrator, user instruction): final-verify step cancelled
The user has cancelled the final verification step and the consolidated T9-T21 report. Neither is required.
- This applies ONLY to the final-verify agent (the step after the T21 loop). The T21 review continues exactly as before, and if it rejects, the T21 loop iterates as normal until it is approved.
- final-verify agent: do not run any test, build, Playwright spec, script, scan or check. Do not start any server or browser. Do not write .agents\tasks\m3-t9-t21\final-report.md or any other file. Send one success notification saying "Final verification skipped on the user's instruction", then end the step.

## Addendum (orchestrator, user wants T21 finished quickly): T21 iteration 2 re-review
The first T21 review (CHANGES_REQUESTED) verified everything except blockers B-1 and B-2, both wording errors in docs/12 and docs/10. The iteration-2 reviewer checks only these four things:
1. B-1 and B-2 are fixed, and the new wording matches the RunPage.test.tsx diff and the Playwright logs (pw-gate.log, pw-screens-3.log, resume-pw-focus.log).
2. No file other than docs/12_milestone3_test_report.md and docs/10_ui_design_system.md changed after the first review (bookkeeping under .agents\ excepted).
3. The link check and the quoted-count check still pass on those two files.
4. The data/runs.db fingerprint is unchanged.
Do not repeat the other checks. Write review.md and review.json, then end. If a fix is still wrong, reject with findings as usual.

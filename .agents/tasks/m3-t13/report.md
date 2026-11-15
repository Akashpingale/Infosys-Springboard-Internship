# T13 report: Frontend foundation

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T13 (line ~1243), with Sections 12.1 to 12.3, 14.1 to 14.3, 14.8, 17.4, 17.5, 20.3 to 20.5. Nothing from T14 or later was built: the Strategy and Advisor tabs hold placeholders, no Strategy section, no Advisor screen, no print or Overview change beyond keeping today's print output.

No backend file changed. `types.gen.ts` was regenerated and is byte-identical to the T12 output.

## Files

| File | Status | Diff / size | Purpose |
|---|---|---|---|
| `web/src/api/types.gen.ts` | regenerated (git-ignored) | unchanged, SHA-256 A03D7C42…CF7C9 before and after | Generated from a fresh `create_app().openapi()` dump (11 paths, 79 schemas) |
| `web/src/api/mutations.ts` | changed | +4 | `StartRunInput` gains optional `include_strategy` and `constraints` |
| `web/src/api/queries.ts` | changed | +2 | `queryKeys.chat(id)` = `['chat', id]` |
| `web/src/features/run/useRun.ts` | changed | +33 | `useGenerateStrategy(runId)`: `POST /api/runs/{id}/strategy` with `{mode}` (default `missing`) and `constraints` only when given; on success the cached run takes the answered state (`queued`), the run is re-read and the history list invalidated, so the existing `refetchInterval` rule restarts polling and stops it when the job ends |
| `web/src/features/new-validation/schema.ts` | changed | +129 | `ConstraintFormValues`, `EMPTY_CONSTRAINTS`, `constraintIssues`, `constraintsFormSchema(limits)`, `reviewStepSchema(limits, constraintLimits)`, `toConstraints`, `fromConstraints`. Every number and choice comes from `meta.strategy.constraints` |
| `web/src/features/new-validation/ReviewStep.tsx` | changed | +93 −15 | "Strategy" panel with the "Include strategy" switch (native checkbox, `role="switch"`, on by default, plan helper text) and the constraints panel; prop `constraints` from edit-and-rerun; `onRunAnalysis(idea, strategy?)`. Shown only when `meta.strategy.available` |
| `web/src/features/new-validation/NewValidationPage.tsx` | changed | +17 −4 | Reads `constraints` from router state; sends `include_strategy` and only filled `constraints` |
| `web/src/features/new-validation/ConstraintsPanel.tsx` | new | 150 lines | Native `<details>` "Resources and goals (optional)", closed unless prefilled; team size select, months select, budget and skill radios, launch region with counter; reads the form through `useFormContext` so T14 can reuse it in the regenerate flow |
| `web/src/lib/strategy.ts` | new | 28 lines | Plain labels for the budget and skill enums (with a plain fallback for an unknown value), `range(min, max)`, type aliases |
| `web/src/features/advisor/useChat.ts` | new | 73 lines | `useChatThread(runId, enabled)`, `useSendChat(runId)` (AbortController; `cancel()`; a cancelled request rejects with `ChatCancelled`, not the offline `ApiError`), `useClearChat(runId)`; `isCancelled` |
| `web/src/features/results/ResultsHeader.tsx` | changed | +34 −4 | `TABS` gains Strategy and Advisor after Competitors (Section 14.1 order); tab row `min-w-0 max-w-full overflow-x-auto`; an effect scrolls only the tab row (never the page) so the open tab stays in view; two comments say seven instead of five |
| `web/src/features/run/RunPage.tsx` | changed | +11 −2 | Placeholder panels for `strategy` and `advisor`; print lays out the five existing tabs only (`PRINTED_TABS`), so a PDF is unchanged until T18; "Edit and re-run" also carries `detail.constraints ?? null` |
| `web/src/test/strategyFixture.synthetic.json` | new | 60,615 bytes | Synthetic `PipelineResult` with `swot`, `mvp`, `gtm`, `constraints`, made by the real backend agents over the existing fake drafts (`.agents/tasks/m3-t13/synthetic_fixture.py`); validates as `PipelineResult`; `check_m3_contracts.py` reports no violations; no key-shaped text |
| `web/src/test/strategyHandlers.ts` | new | 124 lines | `META_WITH_STRATEGY` (the real `/api/meta` strategy and chat blocks), `SYNTHETIC_STRATEGY_RESULT`, seven-stage run fixtures, chat message and thread fixtures, MSW handler factories for meta, strategy and the three chat routes |
| `web/src/features/new-validation/ConstraintsPanel.test.tsx` | new | 16 tests | Form tests |
| `web/src/features/run/strategyRun.test.tsx` | new | 11 tests | Tracker, tabs, edit-and-rerun, polling |
| `web/src/features/advisor/useChat.test.tsx` | new | 8 tests | Chat hooks |
| `web/src/lib/strategy.test.ts` | new | 4 tests | Labels, range, fixture shape |
| `web/src/features/run/RunPage.test.tsx` | existing test edited | +9 −3 | Section 20.4 (see below) |

`hashes.py check` against the start-of-task baseline (49 uncommitted files) lists only the web files above. No backend file, no file of T1 to T12 and no Streamlit file changed. New files have no comments (plan 0.5).

Helper files (only in this folder): `hashes.py`, `baseline_hashes.json`, `dump_openapi.py`, `openapi-temp.json`, `synthetic_fixture.py`, `RunPage.test.tsx.orig`, `undo_check.py`.

## Requirement mapping

| T13 requirement | Where |
|---|---|
| Regenerate `types.gen.ts` | Dumped schema, `npx openapi-typescript` (as T1, T8, T12; the brief forbids starting the backend on `data/runs.db`). Output identical to T12's |
| Strategy mutation | `useGenerateStrategy` in `useRun.ts` |
| Chat queries and mutations (abort support) | `useChat.ts` |
| Constraints panel and zod schema from `/api/meta` | `ConstraintsPanel.tsx`, `schema.ts` (`constraintsFormSchema`, `reviewStepSchema`) |
| "Include strategy" switch | `ReviewStep.tsx`, on by default, helper text from 14.2 |
| Review step wiring | `ReviewStep.tsx` → `NewValidationPage.tsx`: `POST /api/runs` with `include_strategy` and only the filled `constraints` |
| "Edit and re-run" carries constraints | `RunPage.tsx` puts `constraints` in router state; `NewValidationPage.tsx` passes them to the review step, which opens the panel on them |
| Seven-row tracker via data | `StageTracker.tsx` already renders `run.stages` and the labels the backend sends (`notices.STRATEGY_TITLES` via the run manager, T4). Confirmed by tests; not edited |
| Tab list with seven tabs that scrolls inside its container | `ResultsHeader.tsx` |
| Polling restarts after a strategy job begins on a finished run | `useGenerateStrategy` updates the cached state; `useRun`'s existing rule does the rest |
| MSW handlers | `strategyHandlers.ts` factories. `server.ts` stays empty on purpose: default handlers for strategy or chat would let an unexpected POST pass silently |
| Synthetic fixture | `strategyFixture.synthetic.json` |
| Limits come from `/api/meta` only | Selects, radios, region length and every message read `meta.strategy.constraints`; a test with narrowed limits proves it |

### Copy used (Section 14.2)

Switch label "Include strategy"; helper "Adds a SWOT and risk review, an MVP plan and a go-to-market plan. Uses 3 more AI requests and about 1 to 2 minutes."; panel "Resources and goals (optional)"; "If you skip these, the plan assumes a team of 2 and 3 months, and marks that as an assumption."; budget "Bootstrapped, Small budget, Funded"; skill "Non-technical, Some technical, Strong technical team".

## Tests

New, 39 tests:

`ConstraintsPanel.test.tsx` (16)
- Switch: `is on by default and says what it costs`; `sends the switch and no constraints when none was given` (body `toEqual` `{submission, idea_override, include_strategy: true}`); `sends neither strategy nor constraints when it is switched off` (exact body with `include_strategy: false`, a filled team size is dropped); `is not offered when the backend has no strategy, and the request is the one sent before` (exact body `{submission, idea_override}`); `is not offered when the backend reports strategy as unavailable`.
- Panel: `is closed by default and states the assumption`; `offers the fields and choices the plan names`; `sends only the fields that were filled, trimmed and typed as the backend expects` (exact body, `constraints: {team_size: 3, budget_level: 'bootstrapped', launch_region: 'Pune, India'}`); `takes its options and limits from /api/meta, and refuses what they do not allow` (narrowed meta: options 1–4, months 2–6, two budgets, one skill, 10-character region; the error shows and nothing is sent).
- Edit and re-run: `opens the panel on the stored constraints and sends them again` (exact body); `keeps the panel closed when the earlier run had no constraints`.
- Rules: `accepts a form left empty`; `builds its messages from the limits the backend reported`; `checks the constraints in the review step only while strategy is switched on`; `keeps only the filled fields, and gives null when none was filled`; `turns stored constraints back into the form and back again`.

`strategyRun.test.tsx` (11)
- Tracker: `shows four rows for a run without strategy`; `shows seven rows, with the three strategy labels the backend sent, when strategy was asked for`; `announces a running strategy stage like any other`.
- Tabs: `lists the seven tabs in the planned order`; `moves through all seven with the arrow keys, wrapping at both ends, with one tab tabbable`; `scrolls the tab row inside its own container`; `opens a placeholder for the Strategy and Advisor tabs`.
- Edit and re-run: `carries the stored constraints back to the form`; `carries null when the run had none`.
- Polling: `stays quiet on a finished run, then polls again until the strategy job ends` (one read in 2 s while done; after the request, body `{mode: 'missing'}`, reads resume, seven stages, then stop again); `sends the mode and the constraints it is given`.

`useChat.test.tsx` (8): `reads the saved conversation`; `asks nothing while it is not enabled`; `passes on the backend's reason when the conversation is not open yet`; `posts the question alone, then reads the thread again`; `can be cancelled while it waits, and says so rather than reporting a lost connection`; `keeps the backend's code for a refused question`; `does nothing when cancel is pressed with no question in flight`; `sends a delete, then reads the empty thread`.

`strategy.test.ts` (4): `names every budget level and skill the backend offers in plain words`; `never shows a raw code for a choice it does not know`; `lists every whole number between the limits`; `is a complete result with all three strategy parts, and its constraints use the offered choices`.

### Existing test edited (Section 20.4, "Frontend tests that assert the exact tab list or count: add the two names")

`web/src/features/run/RunPage.test.tsx`, four hunks; no assertion removed or loosened:

| Line | Before | After |
|---|---|---|
| 140 | `it('shows the header, the status and the five tabs', …` | `it('shows the header, the status and the seven tabs', …` |
| 148 | `for (const tab of ['Overview', 'Market', 'Competitors', 'Sources', 'Run details'])` | `for (const tab of ['Overview', 'Market', 'Competitors', 'Strategy', 'Advisor', 'Sources', 'Run details'])` |
| 172 (arrow-key test) | Competitors → ArrowRight → Sources | Competitors → ArrowRight → `Strategy` selected → ArrowRight → `Advisor` selected → ArrowRight → Sources (two steps added to the cycle; every earlier assertion kept) |
| 606 | `expect(screen.getAllByRole('tab')).toHaveLength(5);` | `…toHaveLength(7);` |

Undo proof: `undo_check.py` reverses the four hunks on the current file and hashes the result: `3F64BA11A37D3A81C437E5AC81E857F0B2FC4B9E7E90A4199A9B52A4D3CC7668`, equal to the pre-edit copy and to `git show HEAD:` (blob `f138f2613d4878898d5b227278719250145059fd`).

No other existing test changed. `web/src/test/fixtures.ts` (`META`) was left alone, so every existing form test still runs against a meta without a `strategy` block, which is the "no switch" path and sends today's body.

## Plan-vs-code points and decisions

1. **RunPage.tsx is not in T13's file list**, but the entry requires seven tabs ("with placeholder tabs") and "Edit and re-run carries constraints", and both live there. The change is limited to two placeholder panels, the navigate state, and keeping print to the five existing tabs. T18 owns "print includes Strategy and excludes Advisor".
2. **Strategy mutation location.** It is in `useRun.ts` next to `useCancelRun`, because it writes the run's cached detail that drives polling (Section 17.5 lists `useRun.ts` for exactly this). `mutations.ts` only gains the two request fields.
3. **StageTracker.tsx unchanged.** The labels live on the backend stages (T4 `STRATEGY_TITLES`), and the tracker renders `run.stages` as sent. Section 17.5 says "confirm data-driven". The tests confirm it.
4. **`server.ts` unchanged.** Handlers are factories in `strategyHandlers.ts` that each test opts into. This keeps `onUnhandledRequest: 'error'` meaningful for strategy and chat routes.
5. **Switch hidden when strategy is unavailable.** When `meta.strategy` is missing or `available` is false, there is no switch and no panel, and the body is exactly the M2 body. Otherwise the switch is on by default. Turning it off hides the panel, skips constraint checks, and sends `include_strategy: false` with no constraints.
6. **Constraints are checked only while the switch is on** (`superRefine` in `reviewStepSchema`), so a hidden, unsent value cannot block the submit.
7. **Defaults in the copy.** "a team of 2 and 3 months" is the plan's copy text. `/api/meta` does not publish the defaults, so the text is written as the plan gives it. These are not limits, so "no limit is written twice" still holds.
8. **Radios cannot be cleared** once chosen, because the plan lists only the three choices. A founder who never touches them sends nothing.
9. **Abort in tests.** In jsdom, `AbortController` is jsdom's, and Node's fetch (which MSW intercepts) rejects its signal as the wrong type. So `useChat.test.tsx` stubs the global `AbortController` with Node's own class (from `node:util.transferableAbortController()`) for that file only, and unstubs it afterwards. Browsers need no stub. Production code is unchanged by this.
10. **Stored constraints carry nulls** (`technical_skill: null`, `launch_region: null`). `fromConstraints` maps null to "not set", so the review step never sends a null field.
11. **The `e2e/mockApi.ts` meta has no `strategy` block** (T19 extends it). The e2e review step therefore shows no switch yet.

## Commands run and results

| Command | Result |
|---|---|
| `python .agents\tasks\m3-t13\hashes.py save` | 49 uncommitted files hashed |
| `Get-FileHash` / `Get-Item data\runs.db` (start) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z |
| `python -B .agents\tasks\m3-t13\dump_openapi.py` | 11 paths, 79 schemas; `db_created False`, `db_dir_created False` |
| `npx openapi-typescript ..\.agents\tasks\m3-t13\openapi-temp.json -o src/api/types.gen.ts` (web/) | 7.13.0, written; hash unchanged A03D7C42…CF7C9 |
| `python -B .agents\tasks\m3-t13\synthetic_fixture.py` | `status complete swot True mvp True gtm True`; contract script: no violations, exit 0; 60,615 bytes; 0 key-shaped matches |
| `npm run typecheck` | Clean (both passes) |
| `npx vitest run` on the four touched folders (first run) | 4 failed / 112 passed: an expected-text mismatch (stored constraints carry nulls) and the jsdom AbortSignal mismatch. Fixed the expectation and added the test-only stub (point 9) |
| Same, second run | 7 files, 116 passed |
| `npm test` | **24 files, 334 passed** (baseline 295 + 39 new) |
| `npm run typecheck` (final) | Clean |
| `npm run build` | Built; entry chunk `index-On-fyt_e.js` **268.78 kB / 85.53 kB gzip** (baseline 268.78 / 85.54); RunPage chunk 82.71 kB, NewValidationPage chunk 144.78 kB |
| `npx playwright test e2e/keyboard.spec.ts` (extra, offline, mock API) | 21 passed (tabs spec passes with seven tabs). The ui_v2 screenshots spec was not run |
| `python .agents\tasks\m3-t13\undo_check.py` | match True (hash above) |
| `python .agents\tasks\m3-t13\hashes.py check` (end) | Only the 18 web files listed above |
| `Get-FileHash` / `Get-Item data\runs.db` (end) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z (unchanged) |

The backend suite was not re-run, because no backend file changed (brief: frontend tasks run it only if a backend file changed). No backend server was started. Nothing was committed, pushed, reset, reverted or stashed. No branch was created or switched. No `.env` file and no `data/runs.db` content was opened. No live provider call was made.

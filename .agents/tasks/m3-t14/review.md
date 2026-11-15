# T14 review: Strategy tab, states, SWOT and Risks (R1 UI)

Verdict: APPROVED. No blockers.

## Scope and file set
- `hashes.py check` against the start baseline (67 files) lists only: new `StrategyTab.tsx`, `StrategyStates.tsx`, `SwotSection.tsx`, `RisksSection.tsx`, their three test files, `lib/strategyClaims.test.ts`; changed `RunPage.tsx`, `results.ts` (clean tracked file at start, so it shows as "new"); test edits in `RunPage.test.tsx` and `strategyRun.test.tsx`. All are the T14 entry's named files, its new files, or approved test edits. No backend, Streamlit, e2e or other T1–T13 file changed, so the backend suite was not required.
- Baseline hashes for the two edited tests (921e1f9a…, 2e0f3dfa…) equal the `.orig` copies. `undo_check.py` reverses exactly the listed hunks and both files match: True.
- Test edits, checked against `git diff --no-index` with the `.orig` copies: `RunPage.test.tsx` adds one `META` import and one GET `/api/meta` handler (setup only). `strategyRun.test.tsx` adds the `metaWithStrategy` import and handler to two tests (setup only), plus the orchestrator-approved rename and the placeholder assertion changed to the exact 14.10 copy `'No strategy yet.'`. The Advisor assertion is unchanged. Every edit falls under the brief's addendum rules. No assertion was removed or loosened.

## Requirements (Section 18 T14, 14.4, 14.8–14.10)
- Header block: the basis line comes from `inputs_used`/`inputs_missing`. Grounding reads "{n} of {m} points" with no percentage (test asserts no `%`). Assumed chips and the caveat are present. "Change resources and regenerate" opens `ResourcesForm` on the stored constraints, then a confirm dialog, then sends `mode: 'all'`.
- States (`StrategyStates.tsx` `partState`): loading = skeleton while active. Failed = "This part could not be completed. {reason} The rest of the strategy is below." with Try again (`mode: 'missing'`). Skipped shows the `strategy_stage_skipped` notice or the row message. Empty uses the 14.10 copy, the constraints panel and "Generate strategy". Stage keys and the notice code match the backend (`orchestrator.py` uses `StageError(stage=stage.name)`, `agents/notices.py` has `STAGE_SWOT`/`CODE_STRATEGY_SKIPPED`). A retry without constraints keeps the stored ones (`utils/run_manager.py` `start_strategy`: missing mode falls back to `_stored_constraints`).
- SWOT: 2×2 grid at `lg`, quadrant counts, one basis chip per point, citations through `resolveStrategySources`, summary labelled AI interpretation.
- Risks: summary counts, five coverage chips, and gap text "None found in this run. Not checked is not the same as safe." The severity sort keeps the backend order, which `swot_risk_agent._risk_order` sorts by severity. The category sort is stable. The table or the cards are chosen with `useMediaQuery(NARROW)`, so only one is in the DOM. Severity chips are icon plus word on existing status tokens.
- `collectClaims(result, { strategy: true })` feeds only the drawer. The evidence mix and Sources tab still use the default output, unchanged per 14.5. `StrategyClaim` replaces `ClaimItem` because `ClaimItem` takes a single analysis. The report records this conflict, and `Claim.tsx` was not edited.
- The "Ask the advisor about this" button is deferred to T17. It is not in the T14 requirement list, and the report records the deferral.
- New files have no comments and no `dangerouslySetInnerHTML`. Touch targets follow the existing `min-h-[44px] sm:min-h-*` pattern.

## Verification re-run by the reviewer
- `npm run typecheck`: clean (app and e2e).
- `npm test`: 28 files, 373 passed (334 after T13 + 39 new). There were 0 lines matching `unhandled`/`onUnhandledRequest`/`MSW]`. stderr held only the existing React Router future-flag and Node localStorage warnings.
- `npm run build`: entry `index-pC6MYD47.js` 268.79 kB / 85.55 kB gzip (+0.01 kB over 268.78 baseline, stated in the report). RunPage chunk 103.83 kB / 25.61 kB gzip.
- data/runs.db: SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17Z, which matches the brief.
- No backend was started, no .env was opened, no live calls were made, and no git state was changed.

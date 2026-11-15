# T16 review: Strategy tab Go-to-market (R3 UI) and Overview tile

Verdict: APPROVED. No blockers.

## Scope checked
- Spec: plan Section 18 T16 (line 1277), 14.4 (Go-to-market part, section states), 14.5, 14.8, 14.9, 17.4, 17.5, 9.4 to 9.6. Brief including the T14 and T15 addenda.
- Files read: `GtmSection.tsx` (new), the `OverviewTab.tsx` diff against HEAD, and the diffs of `StrategyTab.tsx`, `results.ts`, `StrategyTab.test.tsx` and `strategyClaims.test.ts` against the coder's `.orig` copies. Also read `OverviewStrategyTile.test.tsx`, `MetricTile.tsx`, `format.count`, and the backend sources the UI depends on: `gtm_agent._quality` (`inputs_missing` names `swot`/`mvp`), the NO_SWOT/NO_MVP sentences, and `derived.first_release` (`tier == "mvp"`, which matches the tile's count).

## Requirements
- Positioning: the statement is rendered verbatim (`positioning.statement`) and never rebuilt. The card shows the six parts, a differentiator chip (Hypothesis/Supported, icon plus word, info/success tokens), a basis chip and citations.
- Channels: backend order is kept, and a single "Start here" chip goes on the first flagged channel. Kind, role, cost and speed are shown as words. Fit rationale and citations are shown. Audience fit is an `aria-hidden` 5-step CSS meter with the text "Strong, 4 of 5". The first experiment and success signal are shown. Linked MVP features and risks are resolved to names, and unknown ids are dropped. A `budget_conflict` channel shows the 9.5 wording "May be above a bootstrapped budget".
- Early customers are tactic cards. The launch plan is an `<ol>` showing only the phases returned, and a tab-level test confirms it is the only `<ol>`. Key messages are a table with a caption and row headers. The missing-SWOT and missing-MVP notes reuse the backend sentences.
- Each section state comes from T14's `notReady(partState(..., 'go_to_market'), true)`, so a failed part shows its own "Try again" through the shared `mode: 'missing'` mutation.
- Overview: a fifth `MetricTile` "Strategy" shows a value like "6 risks, 6 features for the first release". Its status reads Generated, Partly generated or Not generated through `StatusChip`. The other tiles, EvidenceMix and the summary components are unchanged. The extended summary lines render with their chips (tested).
- `strategyClaims` adds the positioning, the channels and the tactics. The default `collectClaims` output is unchanged.
- No T17 or later feature was built: no Advisor tab, no prefill button, no print change. The new files have no comments and no `dangerouslySetInnerHTML`. Only existing tokens are used.
- The coder's plan-vs-code decisions are reasonable and recorded:
  - Channels carry no rank number (14.9.3).
  - Audience-fit words are UI labels.
  - The tile wraps to a second row at xl widths.
  - "Partly generated" also shows while strategy is still running.

## Files and existing-test edits
- `hashes.py check` against the start baseline, re-run by me, lists exactly the eight files in the report. The four `.orig` hashes equal the baseline values. The test-file baselines equal T15's recorded end hashes. No backend, Streamlit or e2e file changed.
- The `StrategyTab.tsx` wiring (import, `SECTIONS` entry, section render) and the `results.ts` change (17.5, GTM items) are covered by the T15–T17 addendum.
- The `StrategyTab.test.tsx` section list gains 'Go-to-market' and stays an exact `toEqual`.
- In `strategyClaims.test.ts`:
  - The length goes from 26 to 37 (1 positioning, 6 channels, 4 tactics).
  - The `where` list and the two `claimsCiting` lists gain only the new values, and all stay exact.
  - The test title is renamed the same way T15 did it.
- No assertion was removed or loosened. The coder's undo proof matches the `.orig` hashes.

## Verification (re-run by reviewer)
| Check | Result |
|---|---|
| `npx vitest run src/lib/strategyClaims.test.ts src/features/strategy src/features/results/OverviewStrategyTile.test.tsx` | 7 files, 96 passed |
| `npm run typecheck` | exit 0 (app and e2e) |
| `npm test` | 31 files, 430 passed; 0 lines matching `unhandled`/`onUnhandledRequest`/`MSW]` |
| `npm run build` | exit 0; entry `index-B8wp-9DY.js` 268.79 kB / 85.55 kB gzip (baseline 268.78 / 85.54) |
| Backend suite | Not required: no backend file changed |
| data/runs.db | SHA-256 00A4F859…FEA8337D, 311296 bytes, 2026-11-08T15:31:17Z (matches the brief) |
| Git | branch `main`, HEAD a098aef, nothing committed |

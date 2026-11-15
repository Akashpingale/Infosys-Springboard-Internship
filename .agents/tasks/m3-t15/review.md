# T15 review: Strategy tab, MVP plan (R2 UI)

Verdict: APPROVED. No blockers.

## Scope and file set
- `hashes.py check` against the T15 start baseline (76 files, saved 15:58:55, after the T14 review) lists only: new `MvpSection.tsx`, new `MvpSection.test.tsx`, changed `StrategyTab.tsx`, `StrategyTab.test.tsx`, `results.ts`, `strategyClaims.test.ts`. The baseline entries for the three edited T14 files match their `.orig` copies, so the baseline was taken before the edits.
- No backend, Streamlit, e2e or other T1–T14 file changed, so the backend suite was not required.
- `results.ts`: T14 was +72 −3 vs HEAD and the file is now +78 −3. The T15 part is limited to `strategyClaims` (MVP features with `where` "MVP plan"; the SWOT loops use `swot?.`). The default `collectClaims` output is unchanged. Only `RunPage` `citing` uses `{ strategy: true }`.
- `StrategyTab.tsx` diff vs `.orig`: an import, a `SECTIONS` entry, `mvp`/`mvpState`, and a section rendering `MvpSection` or `notReady(mvpState, true)`. This is the wiring the T15 addendum pre-approves.

## Requirements (18 T15, 14.4 MVP part, 8.4, 14.9)
- Capacity text "Planned {x} of {y} person-months", an `aria-hidden` CSS bar, an "Over capacity" warning chip (icon plus word) and the assumptions line: present.
- Tiers: "In the first release" and "Later" are filtered by `tier` in backend array order, with no sort.
- Feature cards: rank, name, tier chip (success/info tokens, icon plus word), "Effort: S, AI estimate", score and Need/Differentiation/Feasibility as labelled `dl` values, rationale with citations, linked risk titles resolved from `swot.risks`, origin chip, basis chip.
- "How the ranking works" disclosure: 0.4/0.3/0.3, S 0.5 / M 1 / L 2 and focus 0.6. These equal `agents/mvp_agent.py:72-76`. The order rule matches `_rank_key`/the tier walk.
- Success metrics: a target is shown only when present and is labelled an assumption.
- Assumed chips: built from `quality.constraints_assumed`.
- Missing SWOT: the 8.6 note is shown and there are no links.
- Failed/loading/skipped states: handled through T14's `partState`/`notReady`.
- The over-capacity copy matches the backend notice `mvp_over_capacity` (agents/notices.py:434).
- No GTM, Overview tile, advisor prefill or print work leaked in from later tasks.
- No comments, no `dangerouslySetInnerHTML` and no percentages in the new file.

## Existing-test edits
- `StrategyTab.test.tsx`: the exact section list gains 'MVP plan'.
- `strategyClaims.test.ts`: length 18→26, `where` list gains 8× 'MVP plan', the competitors:S1 list gains 'Local language support', and the title is renamed. All stay exact comparisons and nothing was removed. These are pre-approved (addendum T15).
- `undo_check.py`: both reverted files match their `.orig` hashes (EA0258CC…6E526B4C, FAB087CB…D0C9A9BE).

## Verification re-run by the reviewer
- `npx vitest run src/features/strategy src/lib/strategyClaims.test.ts`: 5 files, 60 passed (21 new).
- `npm run typecheck`: clean, app and e2e.
- `npm test`: 29 files, 394 passed. There are 0 lines matching `unhandled|onUnhandledRequest|MSW]` (log: `review-npm-test.log`). There are 5 act() warnings from T14's StrategyEmpty tests, the same count as T14's final log, so they predate T15.
- `npm run build`: entry `index-ZlIxOW3y.js` is 268.79 kB / 85.55 kB gzip, unchanged from T14. RunPage is 113.25 / 27.75 kB (log: `review-build.log`).
- data/runs.db: SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, size 311296, LastWriteTimeUtc 2026-11-08T15:31:17Z. All three match the brief.
- Branch `main`, HEAD a098aef. No commits were made. No .env file or database contents were opened.

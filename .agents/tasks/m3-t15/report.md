# T15 report: Strategy tab, MVP plan (R2 UI)

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T15 (line ~1266), with Section 14.4 (MVP plan part and section states), 14.8, 14.9, 17.4, 17.5, 8.4 and Appendix C (constants shown in the UI). Nothing from T16 or later was built: no GTM section, no Overview tile, no Advisor prefill button, no print change.

No backend file changed, so the backend suite was not re-run (brief: frontend tasks run it only when a backend file changed). No backend server was started.

## Files

| File | Status | Size / diff | Purpose |
|---|---|---|---|
| `web/src/features/strategy/MvpSection.tsx` | new | 353 lines | The MVP section. It has a capacity block with the text "Planned {x} of {y} person-months", a CSS bar (`aria-hidden`, because the text says the same), and an "Over capacity" warning chip (icon plus word, warning tokens) with a plain note. Under that are the assumptions line ("Based on a team of {n} and {m} months to the first release.") and an "Assumed: …" chip for each default the plan used (`quality.constraints_assumed`). Then come two lists, **In the first release** and **Later**. They are filtered by `tier` and keep the backend's array order, so the UI never re-ranks. Each feature is an entity card: "Rank {n}", name, tier chip (icon plus word, success/info tokens), "Effort: S, AI estimate" chip, origin chip ("Your feature" or "Suggested"), "Score 3.80 of 5" with Need / Differentiation / Feasibility as labelled values, rationale with citation chips, "Why later: …" from `deferred_reasons`, "Reduces these risks" with risk titles resolved from the SWOT result, and a basis chip. A "How the ranking works" disclosure states the formula, the weights, the effort conversion, the focus factor and the order rule. The success metrics come last, with a target shown only when given and labelled as an assumption. When SWOT is missing the section shows "Risks were not considered when choosing features." |
| `web/src/features/strategy/MvpSection.test.tsx` | new | 387 lines, 21 tests | |
| `web/src/features/strategy/StrategyTab.tsx` | changed (T14 file; pre-approved wiring) | +11 −0 | Adds `{ id: 'strategy-mvp', label: 'MVP plan' }` to `SECTIONS`, imports `MvpSection`, and renders it or the existing `notReady(partState(run, result, 'mvp_recommendation'), true)` |
| `web/src/lib/results.ts` | changed (pre-approved, 17.5) | T15 part: +12 −6, in `strategyClaims` only (file total vs HEAD +78 −3 including T14) | `strategyClaims` also adds each MVP feature (text = feature name, `where` "MVP plan", its `sources`) when `collectClaims(result, { strategy: true })` is used, so the source drawer lists features. It now runs when `swot` is null as well, so a result with an MVP plan but no SWOT still lists its features. The default `collectClaims` output is unchanged |
| `web/src/features/strategy/StrategyTab.test.tsx` | existing test edited (pre-approved B) | 1 line | See below |
| `web/src/lib/strategyClaims.test.ts` | existing test edited (pre-approved C) | 4 hunks | See below |

`hashes.py check` against the start-of-task baseline (76 uncommitted files) lists exactly these six files. `results.ts` was already a T14 change, so it shows as "changed". No backend, Streamlit, e2e or other T1–T14 file changed. `MvpSection.tsx` has no comments, no docstrings and no `dangerouslySetInnerHTML`. Helpers are all in this folder: `hashes.py`, `baseline_hashes.json`, `undo_check.py`, `*.orig`, `*.log`.

## Requirement mapping (Section 18 T15, 14.4 MVP part)

| Requirement | Where |
|---|---|
| Capacity bar with text | `MvpSection` capacity block: `capacityLine` text, CSS bar (14.9 rule 2, FeatureCoverage precedent), over-capacity chip and note |
| Tiers | Two `FeatureList`s, "In the first release" and "Later", filtered on `tier`, in backend order; tier chip on each card |
| Feature cards | `FeatureCard` (`article` named by the feature heading) |
| Rating values | Score `x.xx of 5` and Need / Differentiation / Feasibility `n of 5` in a `dl` |
| Effort chips labelled AI estimate | "Effort: {S/M/L}, AI estimate" |
| Linked risks | `linkedRiskTitles(feature, swot)` resolves `mitigates_risk_ids` against `swot.risks[].id` (case-insensitive, deduplicated, unknown ids dropped). With no SWOT there are no links |
| Origin chips | `founder_listed` shows "Your feature" (user icon). `gap_opportunity` and `suggested` show "Suggested" (14.4 names only these two words) |
| Ranking disclosure | `<details>` "How the ranking works". The API result carries no weights, so it shows the documented constants (8.4, Appendix C): 0.4 / 0.3 / 0.3, S 0.5 / M 1 / L 2, focus 0.6 |
| Metrics | "Success metrics" region; target labelled "Suggested target, an assumption" and shown only when present; basis chip |
| Assumed-constraint chips | `mvpAssumedChips` from `mvp.quality.constraints_assumed` and `constraints_used`. The tab header's T14 chips are unchanged |
| Integration: linked risk titles from the SWOT result | `StrategyTab` passes `result.swot` to `MvpSection` |
| States (14.4 "States for every section") | Through T14's `notReady`: loading skeleton, failed with its own "Try again" (`mode: missing`), skipped with reason |

## Tests (21 new, in `MvpSection.test.tsx`)

- Capacity: `shows the planned effort against the capacity, in words, with the assumptions behind it`; `warns with an icon and a word when the essential features do not fit`; `shows a chip for each resource the plan assumed, with the value used`.
- Lists: `splits the features into the first release and later, in the order the backend ranked them`; `never re-ranks: a list out of score order stays as given`; `says so when a list is empty`.
- Card: `shows rank, tier, effort as an AI estimate, score and the three ratings as labelled values`; `marks the founder’s own features and the suggested ones`; `names the risks a feature reduces, taken from the SWOT result`; `opens the source a feature cites`; `handles a plan made without the SWOT: no risk links, and a plain note`; `has no note about risks when the SWOT was used`.
- Ranking and metrics: `explains how the ranking works with the documented weights and constants`; `lists the success metrics, with a target only where one was given, labelled an assumption`; `shows no percentage anywhere`.
- Mobile layout: `stacks the cards in one column below the widest breakpoint, with one layout in the page`. The lists are `grid` with only `xl:grid-cols-2`, so they are one column below 1280 px. Cards are `min-w-0`. There is one DOM layout, with no media-query switch.
- In the Strategy tab: `renders the MVP plan as its own section`; `says the MVP part could not be completed and offers a retry, while SWOT stays`; `gives each failed section its own retry, sends one request, and blocks both while it is pending` (SWOT and MVP failed: two "Try again" buttons. A click on one sends exactly `[{mode:'missing'}]`. Both are disabled while the request is held pending, and a click on the other sends nothing. Both are enabled again after the response); `shows the reason the MVP part was skipped`; `lists an MVP feature in the drawer of the source it cites` (run page: F1's citation opens "Farmer survey", whose drawer lists "MVP plan: Photo-based diagnosis").

T14's `no internal names` tests (wide and narrow) now also render the MVP section and still pass: no ids, refs or snake_case names are visible.

## Existing-test edits (all pre-approved by the orchestrator; no assertion removed or loosened)

1. `web/src/features/strategy/StrategyTab.test.tsx`, `has a section list that moves focus to the section chosen` (approval B, exact list gains the new value):

| Before | After |
|---|---|
| `expect(within(nav).getAllByRole('link').map((link) => link.textContent)).toEqual(['SWOT', 'Risks']);` | `expect(within(nav).getAllByRole('link').map((link) => link.textContent)).toEqual(['SWOT', 'Risks', 'MVP plan']);` |

2. `web/src/lib/strategyClaims.test.ts` (approval C, needed because of the `results.ts` change; both stay exact comparisons):

| Before | After |
|---|---|
| `it('adds every SWOT point and every risk, after the analyses', () => {` | `it('adds every SWOT point, every risk and every MVP feature, after the analyses', () => {` |
| `expect(added).toHaveLength(18);` | `expect(added).toHaveLength(26);` |
| `      ...Array(6).fill('Risks'),` / `    ]);` | `      ...Array(6).fill('Risks'),` / `      ...Array(8).fill('MVP plan'),` / `    ]);` |
| `'Farmers stay with the free app',` / `]);` (competitors:S1 list) | `'Farmers stay with the free app',` / `'Local language support',` / `]);` (F3 cites competitors S1) |

No MSW setup handler was needed. The final `npm test` log has 0 lines matching `unhandled`, `onUnhandledRequest` or `MSW]`.

Undo proof (`undo_check.py`): it reverses exactly these hunks on the current files and hashes the result against copies taken before the edits.

| File | Current SHA-256 | Reverted | Pre-edit copy (`.orig`) | Match |
|---|---|---|---|---|
| `StrategyTab.test.tsx` | E8931DF7…FEEB0DBA3 | EA0258CC093E24E09B8CAD33386C1F0525240BF5602855C19CD386276E526B4C | EA0258CC…6E526B4C | True |
| `strategyClaims.test.ts` | 1A6B02D8…215EE7CF5 | FAB087CB351D1BE210FE18185799EAF93D0EF30383D4EE79F0F48AA9D0C9A9BE | FAB087CB…D0C9A9BE | True |

## Integration edit to an earlier task's file (pre-approved A, brief addendum)

`web/src/features/strategy/StrategyTab.tsx` (T14), pre-edit copy `StrategyTab.tsx.orig` (SHA-256 FACC9F13…48CEADE):

| Before | After |
|---|---|
| `import { RisksSection } …` | `import { MvpSection } from '@/features/strategy/MvpSection';` added above it |
| `SECTIONS`: SWOT, Risks | adds `{ id: 'strategy-mvp', label: 'MVP plan' },` |
| `const swotState = partState(run, result, 'swot_risk');` | followed by `const mvp = result.mvp ?? null;` and `const mvpState = partState(run, result, 'mvp_recommendation');` |
| Sections: SWOT, Risks | adds `<Section id="strategy-mvp" title="MVP plan">{mvp ? <MvpSection mvp={mvp} swot={swot} …/> : notReady(mvpState, true)}</Section>` |

Retry rule (orchestrator decision): MVP always gets its own "Try again" when it failed, including when SWOT failed too. Every button calls the same `useGenerateStrategy` mutation with `mode: 'missing'`. It is `loading={generate.isPending}`, and `Button` disables itself while loading, so only one request can be sent. The Generate and Regenerate submit buttons and the confirm dialog already use the same `isPending`. SWOT and Risks still share one button, because they come from one stage (T14 decision, pinned by T14's test `toHaveLength(1)`).

## Plan-vs-code points and decisions

1. **Disclosure weights come from documented constants.** `MvpResult` carries no weights, so `MvpSection` holds `SCORE_WEIGHTS`, `EFFORT_MONTHS` and `FOCUS_FACTOR` equal to `agents/mvp_agent.py` (`SCORE_WEIGHTS`, `EFFORT_MONTHS`, `FOCUS_FACTOR`) and Appendix C. The values are written in two places, backend and UI. The other option, publishing them in the API, changes the API and is outside T15.
2. **`constraints_used` fields are nullable in the generated type.** The backend always fills team size and months after defaults. If a value is still missing, the UI falls back to the documented defaults (2, 3), as T14's header chips do.
3. **Origin `gap_opportunity` reads "Suggested".** 14.4 names only "Your feature" and "Suggested".
4. **Over-capacity note** uses the same words as the backend notice `mvp_over_capacity` (agents/notices.py), so the section and the quality notes agree.
5. **"Risks were not considered when choosing features."** is shown when `swot` is null or `mvp.quality.inputs_missing` includes `swot` (8.6 copy).
6. **Mobile layout** is a CSS grid (one column below `xl`), not a media-query switch, because the cards are the only layout at every width. The capacity bar and chips wrap. Playwright at 390/820/1440 px is T19's job.
7. **"Ask the advisor about this"** is not built here. T17 builds it.

## Commands run and results

| Command | Result |
|---|---|
| `python .agents\tasks\m3-t15\hashes.py save` | 76 uncommitted files hashed |
| `Get-FileHash` / `Get-Item data\runs.db` (start) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z |
| `npx vitest run src/lib/strategyClaims.test.ts src/features/strategy` (after `results.ts` change, before approval) | 37 passed, 2 failed: the two exact lists in `strategyClaims.test.ts`. Stop condition raised; edits A, B and C approved |
| Same, after the approved edits and new tests (`vitest-1.log`) | 5 files, 60 passed (39 existing + 21 new) |
| `npm run typecheck` (first) | 2 errors: nullable `months_to_mvp` in `MvpSection.tsx`. Fixed with the documented defaults |
| `npm run typecheck` (final, `typecheck.log`) | Clean (exit 0), app and e2e |
| `npm test` (final, `npm-test.log`) | **29 files, 394 passed** (373 after T14 + 21 new); **0** lines matching `unhandled`, `onUnhandledRequest` or `MSW]` |
| `npm run build` (final, `build.log`) | Built. Entry chunk `index-ZlIxOW3y.js` **268.79 kB / 85.55 kB gzip** (unchanged from T14; baseline 268.78 / 85.54). RunPage chunk 113.25 kB / 27.75 kB gzip (T14: 103.83 / 25.61) |
| `python .agents\tasks\m3-t15\undo_check.py` | Both edited tests match their pre-edit hashes (table above) |
| `python .agents\tasks\m3-t15\hashes.py check` (end) | Only the six files listed in Files |
| `Get-FileHash` / `Get-Item data\runs.db` (end) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z (unchanged) |

Playwright was not run: T19 owns the browser specs, and the brief's frontend gate is typecheck, `npm test` and build. The ui_v2 screenshots spec was not run. Nothing was committed, pushed, reset, reverted or stashed. No branch was created or switched. No `.env` file and no `data/runs.db` content was opened. No live provider call was made.

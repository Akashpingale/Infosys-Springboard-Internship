# T16 report: Strategy tab, Go-to-market (R3 UI) and Overview tile

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T16 (line ~1277), with Section 14.4 (Go-to-market part and the section states), 14.5, 14.8, 14.9, 17.4, 17.5 and 9.4 to 9.6 (the data the UI shows). Nothing from T17 or later was built: no Advisor tab, no "Ask the advisor about this" button, no print change, no Playwright spec.

No backend file changed, so the backend suite was not re-run (brief: frontend tasks run it only when a backend file changed). No backend server was started.

## Files

| File | Status | Size / diff | Purpose |
|---|---|---|---|
| `web/src/features/strategy/GtmSection.tsx` | new | 456 lines | The Go-to-market section, with five parts. **Positioning** is a card with "Target segment: …", the statement exactly as the backend returned it plus its citation chips, the six parts as labelled values (For whom, Problem, Category, Key benefit, Alternative, Differentiator), a differentiator status chip and a basis chip. The status chip is "Hypothesis" (flask icon, info tokens) or "Supported" (check icon, success tokens). **Channels** are cards in backend order (the UI never re-ranks). One card carries a "Start here" chip (flag icon, success tokens), at most one in the list. Each card shows its name, fit rationale with citations, then Type, Role, Audience fit, Cost, First results in, First experiment and Success signal as labelled values. Audience fit is a 5-step CSS meter (`aria-hidden`) with its text, for example "Strong, 4 of 5". Linked MVP features ("Uses these features") and risks ("Addresses these risks") are resolved to names from the MVP and SWOT results. A channel with `budget_conflict` gets the note "May be above a bootstrapped budget" (warning icon plus words). There is a basis chip. **Early customers** are tactic cards: tactic, Where to find them, Offer, How to measure, basis, citations. **Launch plan** is an `<ol>` of the phases returned, each with its name, "Goal: …" and a bullet list of actions. **Key messages** is a small table (Audience, Message, Proof needed, with "Not given" when there is no proof). When the plan was made without the SWOT or the MVP, the section shows plain notes. They use the backend's own warning sentences (9.6, `agents/notices.py` rules) |
| `web/src/features/strategy/GtmSection.test.tsx` | new | 448 lines, 28 tests | |
| `web/src/features/results/OverviewStrategyTile.test.tsx` | new | 136 lines, 8 tests | |
| `web/src/features/results/OverviewTab.tsx` | changed (T16's named file; committed M2 file) | +65 −1 | Adds `strategyTile(result)` and a fifth `MetricTile` labelled "Strategy" at the end of the tile row. The value counts the strategy, for example "6 risks, 6 features for the first release" (first-release count = features with `tier === 'mvp'`). The status chip (`StatusChip`, icon plus word) reads "Generated" (complete tone), "Partly generated" (partial tone) or "Not generated" (unavailable tone). The detail line says which parts exist, or names the missing ones ("Not generated: the go-to-market plan."). The import line gains `count`. Nothing else in the tab changed: the evidence-strength tile, EvidenceMix, summary and verify-next components are untouched |
| `web/src/features/strategy/StrategyTab.tsx` | changed (T14 file; pre-approved wiring) | +11 −0 | Imports `GtmSection`, adds `{ id: 'strategy-gtm', label: 'Go-to-market' }` to `SECTIONS`, and renders `GtmSection` or the existing `notReady(partState(run, result, 'go_to_market'), true)` |
| `web/src/lib/results.ts` | changed (pre-approved, 17.5) | T16 part: +32 −1 in `strategyClaims` and its doc comment (file total vs HEAD +109 −3, including T14/T15) | `strategyClaims` adds the positioning (text = statement, `where` "Go-to-market: Positioning"), each channel (text = name, "Go-to-market: Channels") and each early-customer tactic (text = tactic, "Go-to-market: Early customers"), with their `sources`. So the source drawer lists them. The default `collectClaims` output is unchanged, so the evidence mix and the Sources tab are unchanged |
| `web/src/features/strategy/StrategyTab.test.tsx` | existing test edited (pre-approved) | 1 line | See below |
| `web/src/lib/strategyClaims.test.ts` | existing test edited (pre-approved) | 5 hunks | See below |

`hashes.py check` against the start-of-task baseline (78 uncommitted files) lists exactly these eight files. OverviewTab.tsx shows as "new" because it was committed and unmodified at the start. No backend, Streamlit, e2e or other T1–T15 file changed. `GtmSection.tsx` has no comments, no docstrings and no `dangerouslySetInnerHTML`. Helpers are all in this folder: `hashes.py`, `baseline_hashes.json`, `undo_check.py`, `*.orig`, `*.log`.

## Requirement mapping (Section 18 T16; 14.4 GTM part; 14.5)

| Requirement | Where |
|---|---|
| Positioning card with the assembled statement | `PositioningCard`: `positioning.statement` is rendered verbatim and never rebuilt in the UI |
| The six parts | `dl` with For whom, Problem, Category, Key benefit, Alternative, Differentiator |
| Differentiator status chip "Hypothesis" / "Supported" | `DifferentiatorChip` in the Differentiator value, icon plus word |
| Basis and citations | `BasisChip` and `Citations` on positioning, channels and tactics |
| Channels as ranked cards, first has "Start here" | Backend order kept. The chip goes on the first channel with `start_here` (the backend sets it on the first), so there is never more than one. Channels carry no visible number, because 14.9.3 reserves numbering for the launch plan |
| Kind, role, fit rationale, cost, speed, audience fit as words and a 5-step meter with text | `KIND_WORD`, `ROLE_WORD`, `COST_WORD`, `SPEED_WORD`, `FitMeter` (`aria-hidden` bar plus "Strong, 4 of 5") |
| First experiment, success signal | Labelled values on each card |
| Linked features and risks (Integration: "Channel links to features and risks") | `linkedFeatureNames` / `linkedRiskNames`: case-insensitive id match against `mvp.features` and `swot.risks`, deduplicated, unknown ids dropped |
| Budget-conflict note | "May be above a bootstrapped budget" (9.5 check 4 wording), warning chip with icon |
| Early customers as tactic cards | `TacticCard` |
| Launch plan as three ordered phases | `<ol aria-label="Launch plan">`. It shows only the phases returned (9.4: the UI shows what came back, code never invents a phase) |
| Key messages as a small table | `<table>` with caption, column headers and a row header per audience |
| States for every section | Through T14's `notReady`: loading skeleton, failed with its own "Try again" (`mode: missing`, shared pending state), skipped with reason |
| 9.6 missing MVP / SWOT in plain words | Notes "Risks were not considered when planning go-to-market." and "The plan is not tied to a feature set because no MVP recommendation was available." |
| 14.5 Strategy tile with value and the three chip states | `strategyTile` + `MetricTile` in `OverviewTab` |
| 14.5 extended `executive_summary` and `verify_next` through the existing components | No code change was needed. The existing summary list renders the backend's `top_risk`, `mvp_scope` and `start_channel` lines with their chips. Tested |
| 17.5 `collectClaims` walks positioning, channels, tactics | `strategyClaims` in `results.ts` |

## Tests (36 new)

`GtmSection.test.tsx` (28):
- Positioning: `shows the statement exactly as the backend returned it, with the segment and the six parts`; `never rebuilds the statement from its parts`; `marks a differentiator that rests on a gap as a hypothesis, with an icon and a word`; `marks a differentiator backed by a competitor fact as supported`; `opens a source the positioning cites`.
- Channels: `keeps the backend order and puts a single "Start here" chip on the first channel`; `never re-ranks, and still shows only one "Start here"` (three channels all flagged `start_here`, given out of order: order kept, one chip); `gives every audience-fit meter its value in words and numbers` (5 steps, filled count = rating, text "Very strong, 5 of 5" and so on); `shows type, role, cost, speed, the first experiment and the success signal in words`; `names the MVP features and the risks a channel is linked to`; `shows no link to a feature or risk the results do not hold`; `links nothing when the plan has no MVP or SWOT to point to`; `notes a channel that may be above a bootstrapped budget, and only that one`; `opens the source a channel cites`.
- Early customers, launch plan, messages: `shows each early-customer tactic as a card with where, offer and measure`; `lists the launch phases in order as a numbered list, with goal and actions`; `shows only the phases returned, never inventing one`; `shows the key messages as a small table, saying when no proof was named`; `shows no percentage anywhere`.
- Missing inputs: `says plainly when the plan was made without the risks or the MVP`; `has no such notes when both were used`.
- Layout: `stacks channel and tactic cards in one column below the widest breakpoint, with one layout in the page`.
- In the Strategy tab: `renders the go-to-market plan as its own section`; `has the launch plan as the only numbered list in the tab` (the whole tab has exactly one `<ol>`, the launch plan); `says the go-to-market part could not be completed and offers a retry`; `shows the reason the go-to-market part was skipped`; `shows a placeholder while the go-to-market part is being prepared`; `lists a channel in the drawer of the source it cites` (run page: the start channel's citation opens "Plantix crop doctor app", whose drawer lists "Go-to-market: Channels: Short demo videos on a messaging app").

`OverviewStrategyTile.test.tsx` (8):
- `counts the risks and the first-release features when all three parts were generated` ("6 risks, 6 features for the first release", "Generated" with icon); `says partly generated and names the part that is missing`; `counts only what is there when the SWOT is missing`; `says not generated for a result without any strategy` (M2 `COMPLETE_RESULT`: "No strategy yet", "Not generated"); `works the states out from the result alone` (singular forms, GTM-only value); `adds one tile to the row and leaves the others as they were` (tile headings exactly Evidence strength, Market size (TAM), Competitors found, Priority segment, Strategy).
- `shows the main risk, the first-release scope and the start channel, each with its chips` (the main-risk line has chips Source 5 and Source 9; the scope line, `user_provided`, shows "From your idea"; the start-channel chip opens `market:S2`); `adds no strategy line when the result has no strategy`.

T14's `no internal names` tests (wide and narrow) now also render the Go-to-market section and still pass: no ids, refs or snake_case names are visible. T14's and T15's retry tests still pass with the GTM section present.

## Existing-test edits (pre-approved by the orchestrator addendum for T15–T17; no assertion removed or loosened)

1. `web/src/features/strategy/StrategyTab.test.tsx`, `has a section list that moves focus to the section chosen` (exact list gains the new value):

| Before | After |
|---|---|
| `expect(within(nav).getAllByRole('link').map((link) => link.textContent)).toEqual(['SWOT', 'Risks', 'MVP plan']);` | `expect(within(nav).getAllByRole('link').map((link) => link.textContent)).toEqual(['SWOT', 'Risks', 'MVP plan', 'Go-to-market']);` |

2. `web/src/lib/strategyClaims.test.ts` (needed because of the `results.ts` change; all stay exact comparisons; T15 renamed the same test title the same way):

| Before | After |
|---|---|
| `it('adds every SWOT point, every risk and every MVP feature, after the analyses', () => {` | `it('adds every SWOT point, every risk, every MVP feature and the go-to-market items, after the analyses', () => {` |
| `expect(added).toHaveLength(26);` | `expect(added).toHaveLength(37);` (1 positioning + 6 channels + 4 tactics) |
| `      ...Array(8).fill('MVP plan'),` / `    ]);` | `      ...Array(8).fill('MVP plan'),` / `      'Go-to-market: Positioning',` / `      ...Array(6).fill('Go-to-market: Channels'),` / `      ...Array(4).fill('Go-to-market: Early customers'),` / `    ]);` |
| `'Local language support',` / `]);` (competitors:S1 list) | `'Local language support',` / `SYNTHETIC_STRATEGY_RESULT.gtm!.positioning.statement,` / `]);` (the positioning cites competitors S1) |
| `expect(plantixMarket.map((claim) => claim.where)).toEqual(['SWOT: Opportunities', 'SWOT: Threats']);` | `expect(plantixMarket.map((claim) => claim.where)).toEqual([` / `'SWOT: Opportunities',` / `'SWOT: Threats',` / `'Go-to-market: Channels',` / `]);` (the start channel cites market S2) |

No MSW setup handler was needed. The final `npm test` log has 0 lines matching `unhandled`, `onUnhandledRequest` or `MSW]`.

Undo proof (`undo_check.py`): it reverses exactly these hunks on the current files and hashes the result against copies taken before the edits.

| File | Current SHA-256 | Reverted | Pre-edit copy (`.orig`) | Match |
|---|---|---|---|---|
| `StrategyTab.test.tsx` | 4880395659DA18F0169114F17F75480F8B9BEF4B662F8A6C843422732FD1819A | E8931DF76B82B92F4BCF290E32F254CEA06131F810EBD492C08D77DFEEB0DBA3 | E8931DF7…FEEB0DBA3 | True |
| `strategyClaims.test.ts` | 3A6844B9D67CBC9F8FB708C62C2A437C407D01454AB71116855E05104B22FC19 | 1A6B02D80CD2E5A49EAE3FE99CEF5B5D7043DBDE100DA243E850500215EE7CF5 | 1A6B02D8…215EE7CF5 | True |

Both pre-edit hashes equal the "current" hashes T15's report recorded for these files.

## Integration edit to an earlier task's file (pre-approved, brief addendum during T15)

`web/src/features/strategy/StrategyTab.tsx` (T14), pre-edit copy `StrategyTab.tsx.orig`:

| Before | After |
|---|---|
| `import { MvpSection } …` | `import { GtmSection } from '@/features/strategy/GtmSection';` added above it |
| `SECTIONS`: SWOT, Risks, MVP plan | adds `{ id: 'strategy-gtm', label: 'Go-to-market' },` |
| `const mvpState = partState(run, result, 'mvp_recommendation');` | followed by `const gtm = result.gtm ?? null;` and `const gtmState = partState(run, result, 'go_to_market');` |
| Sections: SWOT, Risks, MVP plan | adds `<Section id="strategy-gtm" title="Go-to-market">{gtm ? <GtmSection gtm={gtm} mvp={mvp} swot={swot} …/> : notReady(gtmState, true)}</Section>` |

Retry rule (orchestrator decision): GTM gets its own "Try again" when it failed. It calls the same `useGenerateStrategy` mutation with `mode: 'missing'` and shares `generate.isPending`, so only one request can be sent. T15's test for the shared pending state still passes.

## Plan-vs-code points and decisions

1. **Channels show no rank number.** 14.4 calls them "ranked cards", and 14.9.3 says the launch plan is the only numbered sequence. The cards keep the backend's order, the list is a `ul`, and the "{n} channels, best fit first" line states the ordering in words.
2. **"Start here" goes on the first channel with `start_here`.** The backend sets the flag on the first channel (9.4). If more than one were flagged, only the first gets the chip, so "a single Start here" always holds.
3. **Audience-fit words** ("Very weak" to "Very strong") are UI labels for the 1 to 5 rating. The plan asks for "words and a 5-step meter with text" but names no words. Cost and speed are 3-level enums, so they are shown as words with no meter.
4. **The GTM `summary` and `limitations` are not rendered**, the same as T15 did for the MVP. 14.4's GTM list does not name them, and `limitations` already reach the user through the notices.
5. **Linked features and risks are plain name chips, not in-page links.** This follows T15's MVP "Reduces these risks" chips.
6. **Strategy tile layout.** The tile is a fifth `MetricTile` in the existing `sm:grid-cols-2 xl:grid-cols-4` row. The grid classes were not changed, so at 1280 px and wider it wraps to a second row. Widening the grid to five columns would narrow the four M2 tiles, so it was left as it is. T19 will see this at three widths.
7. **"Partly generated" covers a run whose strategy is still running.** `OverviewTab` receives only the result, and 14.5 defines the three states from what is present. A run whose strategy stages are still in progress therefore reads "Partly generated" until all three parts arrive.
8. **"Ask the advisor about this"** is not built here. T17 builds it.

## Commands run and results

| Command | Result |
|---|---|
| `python .agents\tasks\m3-t16\hashes.py save` | 78 uncommitted files hashed |
| `Get-FileHash` / `Get-Item data\runs.db` (start) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z |
| `npx vitest run src/lib/strategyClaims.test.ts src/features/strategy src/features/results/OverviewStrategyTile.test.tsx` (`vitest-1.log`) | 7 files, 96 passed (60 existing + 36 new), first run |
| `npm run typecheck` (`typecheck.log`) | Clean (exit 0), app and e2e |
| `npm test` (`npm-test.log`) | **31 files, 430 passed** (394 after T15 + 36 new); **0** lines matching `unhandled`, `onUnhandledRequest` or `MSW]` |
| `npm run build` (`build.log`) | Built. Entry chunk `index-B8wp-9DY.js` **268.79 kB / 85.55 kB gzip** (unchanged from T15; baseline 268.78 / 85.54). RunPage chunk 126.65 kB / 30.60 kB gzip (T15: 113.25 / 27.75) |
| `python .agents\tasks\m3-t16\undo_check.py` | Both edited tests match their pre-edit hashes (table above) |
| `python .agents\tasks\m3-t16\hashes.py check` (end) | Only the eight files listed in Files |
| `Get-FileHash` / `Get-Item data\runs.db` (end) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z (unchanged) |

Playwright was not run: T19 owns the browser specs, and the brief's frontend gate is typecheck, `npm test` and build. The ui_v2 screenshots spec was not run. Nothing was committed, pushed, reset, reverted or stashed. No branch was created or switched. No `.env` file and no `data/runs.db` content was opened. No live provider call was made.

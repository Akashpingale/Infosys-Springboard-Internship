# T14 report: Strategy tab, states, SWOT and Risks (R1 UI)

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T14 (line ~1254), with Sections 14.4 (header, SWOT, Risks, states), 14.8, 14.9, 14.10, 17.4, 17.5 and 20.4. Nothing from T15 or later was built: no MVP or GTM section, no Overview tile, no Advisor screen, no print change.

No backend file changed, so the backend suite was not re-run (brief: frontend tasks run it only when a backend file changed). No backend server was started.

## Files

| File | Status | Size / diff | Purpose |
|---|---|---|---|
| `web/src/features/strategy/StrategyTab.tsx` | new | 283 lines | Header block: "Built from: …" with "Not used: …" (from `quality.inputs_used/inputs_missing`), "{n} of {m} points are linked to a finding from your analysis." (from `grounded_share` × the `basis_counts` total, never a percentage), "Assumed: team of 2" / "Assumed: 3 months" chips, the caveat, and "Change resources and regenerate". That button opens the constraints panel on the stored values, then a confirm dialog (Cancel "Keep it" focused) says all three parts will be replaced, then sends `mode: all`. Below the header: the sticky section list (SWOT, Risks) and the sections |
| `web/src/features/strategy/StrategyStates.tsx` | new | 224 lines | `partState` (ready, loading, failed, skipped, missing, from the result, `errors`, notices and the run's `stages`); empty state with the 14.10 copy, the constraints panel (closed unless prefilled) and "Generate strategy" (`mode: missing`); failed state "This part could not be completed. {reason} The rest of the strategy is below." with "Try again" (`mode: missing`); skipped state with the reason; loading skeleton; `ResourcesForm`, which reuses T13's `ConstraintsPanel` and `constraintsFormSchema` |
| `web/src/features/strategy/SwotSection.tsx` | new | 94 lines | 2 by 2 grid on `lg`, stacked below. Each quadrant has a count and its points as claim rows: text, "why it matters" in muted text, basis chip and citation chips. Ends with the summary labelled "AI interpretation" |
| `web/src/features/strategy/RisksSection.tsx` | new | 306 lines | Summary "{n} risks: {h} high, {m} medium, {l} low"; five coverage chips, and for a gap "{Category}: None found in this run. Not checked is not the same as safe."; sort select (Severity default, which is the backend order, or Category); register as a table (Risk, Category, Likelihood, Impact, Severity, Mitigation) with expandable detail (description with citations, early-warning signal, confidence, basis). Below 1024 px it is cards, chosen with `useMediaQuery(NARROW)`, so only one layout is in the DOM. Severity chip is icon plus word with existing status tokens (danger, warning, info) |
| `web/src/lib/results.ts` | changed | +72 −3 | `StrategySourceKey`, `SWOT_QUADRANTS`, `strategySourceKeys`, `resolveStrategySources`; `Claim.analysis` gains `'strategy'`; `collectClaims(result, { strategy: true })` appends the SWOT items (`where` "SWOT: Strengths" …) and risks (`where` "Risks"). Without the option the output is unchanged, so the evidence mix and Sources tab stay as before (Section 14.5) |
| `web/src/features/run/RunPage.tsx` | changed | T14 part: +4 −1 (file total vs HEAD +15 −3 including T13) | Strategy tab renders `StrategyTab` instead of the T13 placeholder; the source drawer uses `collectClaims(result, { strategy: true })`, so it lists the strategy claims for a source. Print stays at `PRINTED_TABS` (T18) |
| `web/src/features/strategy/StrategyTab.test.tsx` | new | 19 tests | |
| `web/src/features/strategy/RisksSection.test.tsx` | new | 9 tests | |
| `web/src/features/strategy/SwotSection.test.tsx` | new | 6 tests | |
| `web/src/lib/strategyClaims.test.ts` | new | 5 tests | |
| `web/src/features/run/strategyRun.test.tsx` | existing (T13) test edited | 4 hunks | Approved by the orchestrator; see below |
| `web/src/features/run/RunPage.test.tsx` | existing test edited | 2 hunks on top of T13's | Approved by the orchestrator; see below |

`hashes.py check` against the start-of-task baseline (67 uncommitted files) lists only the files above. `results.ts` shows as "new" there only because it was a clean tracked file at the start. No backend, Streamlit or T1–T13 file outside this list changed. New files have no comments or docstrings and no `dangerouslySetInnerHTML`. Helper files are all in this folder: `hashes.py`, `baseline_hashes.json`, `undo_check.py`, `*.orig`, `*.log`.

## Requirement mapping

| T14 requirement | Where |
|---|---|
| 14.4 header block | `StrategyTab.tsx` (`basisLine`, `grounding`, `assumedChips`, `CAVEAT`, regenerate) |
| Section navigation | `StrategyTab.tsx` `SECTIONS` and `jump` (same pattern as the Market tab, moves focus to the heading, respects reduced motion) |
| Empty/loading/failed/skipped states | `StrategyStates.tsx` |
| SWOT grid | `SwotSection.tsx` |
| Risks: coverage chips and register (table or cards) | `RisksSection.tsx` |
| Claims through `Claim` | `StrategyClaim` uses the same `data-claim` row, `BasisChip` and `Citations` as `ClaimItem`. `ClaimItem` itself takes one `analysis` and `source_ids`, while strategy items carry `{analysis, id}` pairs that can cite both analyses, so a sibling component was needed (see the points below) |
| `collectClaims` extended for SWOT and risks | `results.ts` |
| Source drawer lists strategy claims for a source | `RunPage.tsx` `citing` |
| Generate and retry buttons call the retro endpoint | `useGenerateStrategy` (T13): Generate and Try again send `mode: missing`; regenerate sends `mode: all` |

Copy used: 14.10 "No strategy yet. Generate a SWOT and risk review, an MVP plan and a go-to-market plan from these results. This uses 3 AI requests.", "Generate strategy", "Change resources and regenerate", "This part could not be completed. The rest of the strategy is below."; 14.4 "These are AI interpretations of your results, not predictions.", "None found in this run. Not checked is not the same as safe."; 12.4 "There is no market or competitor analysis to build a strategy on." for a run that has no market or competitor analysis.

## Tests (39 new)

`StrategyTab.test.tsx` (19): `says what the strategy was built from, how much of it is linked, and that it is an interpretation` (also asserts no `%` anywhere); `names an analysis that was not used`; `shows a chip for each assumed constraint, with the value the plan used`; `shows no assumption chips when the founder gave the resources`; `has a section list that moves focus to the section chosen`; `explains what generating does and costs, and sends the request when asked` (body exactly `{mode:'missing'}`); `sends only the resources that were filled in` (exact body); `shows the backend’s reason when the request is refused`; `offers nothing to generate when there is no analysis to build on`; `offers no button when the backend cannot run strategy`; `says the SWOT part could not be completed, why, and offers one retry for the missing part` (partial run, exact body); `gives the reason a part was skipped`; `shows a placeholder while the part is still being prepared`; `opens the resources on the stored values, confirms that all three parts are replaced, and sends mode all` (exact body); `sends nothing when the confirmation is declined`; `shows no ids, refs or field names on a wide screen`; `shows none on a narrow screen either` (all details expanded; regex for SW/R/F/CH/S ids, IDEA./MKT./CMP./RSK./CON./MVP. refs and snake_case names); `opens a SWOT point’s source in the drawer, which lists that point among what cites it`; `lists a risk in the drawer of the source it cites`.

`RisksSection.test.tsx` (9): `counts the risks by severity`; `shows one coverage chip per category, with its count`; `says plainly when a category has no risk, and that this is not the same as safe`; `is a table on a wide screen with the planned columns, and no cards`; `shows severity as an icon and a word, never colour alone`; `becomes cards below 1024 px, with only one layout in the page`; `sorts by severity by default, and by category on request`; `opens the detail of a risk: description, early warning sign, confidence, basis and sources`; `opens the same detail from a card`.

`SwotSection.test.tsx` (6): `shows the four quadrants in the planned order, each with its count`; `keeps each point as the agent wrote it, with why it matters below`; `gives every point exactly one basis chip, in words`; `numbers the citations and opens the source each one names, across both analyses`; `ends with the summary, labelled as an AI interpretation`; `says so when a quadrant has nothing`.

`strategyClaims.test.ts` (5): `leaves the two analyses alone unless strategy is asked for, so the evidence mix is unchanged`; `adds every SWOT point and every risk, after the analyses`; `lists a strategy point among the claims citing its source, from either analysis`; `adds nothing for a result without SWOT`; `resolves strategy sources by analysis, once each, skipping any the result does not list`.

## Existing-test edits (all approved by the orchestrator; no assertion removed or loosened)

1. `web/src/features/run/strategyRun.test.tsx` (T13 test), approved as edit A. T14 replaces the placeholder the test asserted.

| Before | After |
|---|---|
| `it('opens a placeholder for the Strategy and Advisor tabs', async () => {` | `it('opens the Strategy tab and a placeholder for the Advisor tab', async () => {` |
| `expect(screen.getByRole('tabpanel')).toHaveTextContent('The strategy for this validation will be shown here.');` | `expect(screen.getByRole('tabpanel')).toHaveTextContent('No strategy yet.');` |

The Advisor assertion is unchanged.

2. Setup only: a GET `/api/meta` handler for tests that now open the Strategy tab, which reads `/api/meta` to decide whether to offer Generate or Regenerate. Without it MSW printed "unhandled request" errors (`onUnhandledRequest: 'error'`) while the tests still passed.

| File / test | Before | After |
|---|---|---|
| `RunPage.test.tsx` imports | `import { renderWithApp } from '@/test/render';` | `import { META } from '@/test/fixtures';` added above it |
| `RunPage.test.tsx` `moves between tabs with the arrow keys` | `server.use(show(DONE));` | ``server.use(show(DONE), http.get(`${API_URL}/api/meta`, () => HttpResponse.json(META)));`` |
| `strategyRun.test.tsx` imports | `  runUrl,` / `  strategyOk,` | `  metaWithStrategy,` added before them |
| `strategyRun.test.tsx` `moves through all seven with the arrow keys, wrapping at both ends, with one tab tabbable` | `server.use(show(DONE));` | `server.use(show(DONE), metaWithStrategy());` |
| `strategyRun.test.tsx` `opens the Strategy tab and a placeholder for the Advisor tab` (approved separately) | `server.use(show(DONE));` | `server.use(show(DONE), metaWithStrategy());` |

No other existing test needed a missing handler: the final `npm test` log has 0 lines matching `unhandled`, `onUnhandledRequest` or `MSW]`.

Undo proof (`undo_check.py`): it reverses exactly these hunks on the current files and hashes the result against copies taken before T14's test edits.

| File | Current SHA-256 | Reverted | Pre-edit copy | Match |
|---|---|---|---|---|
| `RunPage.test.tsx` | 0CC78DA7…69F1B03 | 921E1F9A2539DFD3104B97BB03108EF177FADDC644DB8CE030D3B92BE657160E | 921E1F9A…657160E | True |
| `strategyRun.test.tsx` | DA5D11D3…762FFDB48 | 2E0F3DFA27790DA049B486B4E5E6CD2EF2EDB17E81DFCE92EFEA6A3A7133128E | 2E0F3DFA…7133128E | True |

T13's own `RunPage.test.tsx` hunks (seven tabs) are unchanged and still documented in the T13 report.

## Plan-vs-code points and decisions

1. **`ClaimItem` cannot render a strategy item.** It takes one `analysis` and `source_ids`, and strategy items cite `{analysis, id}` pairs across both analyses. `StrategyClaim` copies its markup (same `data-claim` row, `BasisChip`, `Citations`) over `resolveStrategySources`. `Claim.tsx` was not edited.
2. **`collectClaims` takes an opt-in option.** Adding strategy claims to the default output would change the Overview evidence mix and Sources "cited by" counts, which Section 14.5 keeps unchanged. Only the drawer uses `{ strategy: true }`. The plan also names `claimsCiting`. It needed no change, because it filters whatever list it is given.
3. **Risk claims in the drawer show the risk title**, which is the register's row label.
4. **Assumed-constraint values.** The chip uses `mvp.constraints_used` when an MVP result exists. Otherwise it uses the plan's defaults (team of 2, 3 months; the backend's `CONSTRAINT_DEFAULTS`), because `/api/meta` does not publish defaults. T13 made the same choice for the review-step copy.
5. **Grounding count** is `round(grounded_share × points)` summed over the parts that have a `quality` block, with points from `basis_counts`. The backend stores a share, not a count. On the synthetic fixture this gives "32 of 37".
6. **Retry placement.** A failed SWOT stage shows the failed message in both SWOT and Risks, which come from one stage, but only one "Try again" button. That avoids two controls for one request.
7. **Generate and Regenerate need `/api/meta`.** They are offered only when `meta.strategy.available`, the same rule as the review-step switch. The empty-state text still shows without it.
8. **"Ask the advisor about this"** (14.4, every section) is not built. It switches to the Advisor tab, which T17 builds.
9. **Loading state.** Section 14.3 says strategy sections not yet done show skeletons while stages 5 to 7 run. The run page shows only the Overview while a run is active (existing behaviour), so the loading state appears when a part is waiting or running on a run the page shows as finished-tabs, such as a poll that lands mid-job. It is covered by a test. The run page itself was not changed for this.

## Commands run and results

| Command | Result |
|---|---|
| `python .agents\tasks\m3-t14\hashes.py save` | 67 uncommitted files hashed |
| `Get-FileHash` / `Get-Item data\runs.db` (start) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z |
| `npm run typecheck` (before edits) | Clean |
| `npx vitest run src/features/strategy src/lib/strategyClaims.test.ts` (first) | 4 failed / 35 passed: two accessible-name queries in my new tests, and one test that read the panel before `/api/meta` loaded. Fixed in the new tests |
| Same (second, third) | 1 failed (a row lookup in a new test), then 39 passed |
| `npm test` (first full) | 372 passed, 1 failed: T13's placeholder test (stop condition raised, edit A approved), plus MSW unhandled `/api/meta` lines (setup handlers approved) |
| `npm test` after the approved edits | 373 passed; 2 unhandled lines left. One was my own typo in the RunPage handler URL, fixed. The other was the renamed test, whose fix was approved separately |
| `npx vitest run src/features/run` | 48 passed, 1 unhandled line (the renamed test), then fixed |
| `npm run typecheck` (final) | Clean (exit 0) |
| `npm test` (final) | **28 files, 373 passed** (334 after T13 + 39 new); **0** lines matching `unhandled`, `onUnhandledRequest` or `MSW]` |
| `npm run build` (final) | Built. Entry chunk `index-pC6MYD47.js` **268.79 kB / 85.55 kB gzip** (baseline 268.78 / 85.54, +0.01 kB from the shared `results.ts` change); RunPage chunk 103.83 kB / 25.61 kB gzip (T13: 82.71 kB) |
| `python .agents\tasks\m3-t14\undo_check.py` | Both files match their pre-edit hashes (table above) |
| `python .agents\tasks\m3-t14\hashes.py check` (end) | Only the files listed in Files |
| `Get-FileHash` / `Get-Item data\runs.db` (end) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z (unchanged) |

Playwright was not run, because T19 owns the new browser specs, and the brief's frontend gate for T14 is typecheck, `npm test` and build. The ui_v2 screenshots spec was not run. Nothing was committed, pushed, reset, reverted or stashed. No branch was created or switched. No `.env` file and no `data/runs.db` content was opened. No live provider call was made.

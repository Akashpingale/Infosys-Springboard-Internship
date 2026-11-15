# M3-T7 coder notes

## Iteration 1 (no review.json existed, so this is the first implementation)

Review findings fixed this iteration: none. No review had run yet.

### Files changed or created

| File | State | Purpose |
|---|---|---|
| `agents/gtm_agent.py` | new, 648 lines, SHA-256 `427DD016EBA9F660A3359C70162FEE36D70242ADEC27363796A2324C89D9EE4F` | Stage 7 `GtmAgent` (name `go_to_market`). It holds one constants block, `build_prompt(digest) -> (system, user)` (A.0 + A.3), a single `call_structured(system, user, GtmDraft, caller=generate_json)`, `build_result`, and `plan_go_to_market(idea, constraints, market, competitors, swot=None, mvp=None)`. The file has no comments and no docstrings (§0.5). |
| `tests/test_m3_gtm_agent.py` | new, 1065 lines, SHA-256 `9F734D47C7DD9599E0CB5E151FFB803B01FC58D39B025C2431597CF5AC64B336` | 72 T7 tests, using fake replies only |
| `orchestrator.py` | modified (registration only) | Imports `GtmAgent` (line 25), updates the `PendingStrategyAgent` docstring (line 164), and replaces `PendingStrategyAgent(STAGE_GTM)` with `GtmAgent()` (line 217) |
| `tests/test_m3_orchestrator.py` | allowed edit 2 | +1 line |
| `tests/test_m3_swot_agent.py` | allowed edits 1 and 3 | 1 line changed, +1 line |
| `tests/test_m3_mvp_agent.py` | allowed edits 1 and 3 | 1 line changed, +1 line |

Helper scripts (all under `.agents/tasks/m3-t7/`):
- `probe_digest.py` prints the fake-run digest with RSK and MVP facts. It is read-only and fake-backed.
- `check_test_edits.py` is the hash-restoration proof.
- `verify.py` checks the protected-file fingerprints and runs the secret scan.

### Existing-test edits (before -> after)

1. `tests/test_m3_swot_agent.py::test_the_real_agent_is_registered_for_stage_five`, line 528:
   ```python
   # before
       assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["MvpAgent", "PendingStrategyAgent"]
   # after
       assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["MvpAgent", "GtmAgent"]
   ```
2. `tests/test_m3_mvp_agent.py::test_the_real_agent_is_registered_for_stage_six`, line 712:
   ```python
   # before
       assert type(STRATEGY_ONLY_STAGES[2].agent).__name__ == "PendingStrategyAgent"
   # after
       assert type(STRATEGY_ONLY_STAGES[2].agent).__name__ == "GtmAgent"
   ```
3. `tests/test_m3_orchestrator.py::test_without_a_registered_agent_a_strategy_stage_fails_plainly`. One line was added at line 140, after the existing `[1]` line. No assertion changed.
   ```python
       monkeypatch.setattr(STRATEGY_ONLY_STAGES[2], "agent", orchestrator.PendingStrategyAgent(STAGE_GTM))
   ```
4. `tests/test_m3_swot_agent.py::test_a_seven_stage_run_stores_the_swot_and_its_risks_join_the_digest`. The same line was added at line 534, after the existing `[1]` line. No assertion changed.
5. `tests/test_m3_mvp_agent.py::test_a_seven_stage_run_stores_the_mvp_built_on_the_swot_risks`. The same line was added at line 717, after `use_full_pipeline(monkeypatch)`. No assertion changed.

Both registry assertions remain exact comparisons against the real registry, so no assertion was weakened. No other existing test failed or needed a change.

### Hash-restoration proof (`check_test_edits.py`)

```
orchestrator.py: edited line at [25] / [164] / [217] (occurrences 1 each)
orchestrator.py: current 3A2F41C4ABB03CA4184E9BD8FCEBBA8736251B107FA0044925B48C73F5CED0A2
orchestrator.py: with the edits undone A87005B4E3AA6ED7793299B4A583ECA3F34541FEBC247DF587C138F92612D7FC
orchestrator.py: matches baseline True
tests/test_m3_orchestrator.py: edited line at [140]
tests/test_m3_orchestrator.py: current F4F7F3AE417B069F23588160C91B10C1481C464C6BA98CBEEA8739B4C20B590F
tests/test_m3_orchestrator.py: with the edits undone 9B9747559EADDBC2629AD132D1A26B7FD389032BF8ACF98DF5A58A45F842A81A
tests/test_m3_orchestrator.py: matches baseline True
tests/test_m3_swot_agent.py: edited line at [528] and [534]
tests/test_m3_swot_agent.py: current A4801EAF7677CDE02C5379F2B06F120C7B338D143374CC782213BD1653C52461
tests/test_m3_swot_agent.py: with the edits undone DCFFC7893966913F7B9D488B42658CDE76EA380E0A524AA87D9842DD80EAB8FE
tests/test_m3_swot_agent.py: matches baseline True
tests/test_m3_mvp_agent.py: edited line at [712] and [717]
tests/test_m3_mvp_agent.py: current 514F3A3A8DF74C2CA2CECEBF3B3D377DEB8E63E3B4B6AB14D6B204F16EB5891E
tests/test_m3_mvp_agent.py: with the edits undone FD9CF11821C773B8AD87B64BB2A9796FB9FB17267EC254DA7F39B88FB45459B7
tests/test_m3_mvp_agent.py: matches baseline True
```

### Commands run and results

Every command ran with `$env:PYTHONIOENCODING="utf-8"` and `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE`.

| Command | Result |
|---|---|
| `... tests/test_m3_gtm_agent.py` (first run) | 5 failed, 67 passed. All five were fixture mistakes in the new test file: added items with `ai_interpretation` and no refs, an appended channel that ranked 7th and was cut, and an MKT ref renumbered once the segments were removed. I fixed the tests. The agent was not changed. |
| `... tests/test_m3_gtm_agent.py` | **72 passed**, 0 failed, 1 warning |
| `... tests/test_m3_mvp_agent.py tests/test_m3_swot_agent.py tests/test_m3_orchestrator.py tests/test_m3_digest.py tests/test_m3_checks.py tests/test_m3_strict_schema.py` | **268 passed**, 0 failed, 1 warning |
| Full suite with an extra `-p no:logging` flag I added by mistake | 2020 passed, 92 errors. The flag removes pytest's `caplog` fixture, so every test that uses `caplog` errored at setup. This was not a code failure. I reran without the flag. |
| Full suite `... -rfE` (brief's flags) | **2112 passed** (2040 baseline + 72 new), 0 failed, 1 warning (StarletteDeprecationWarning, httpx with starlette.testclient) |
| `... tests/test_m3_orchestrator.py -k "existing_stage_sets_are_unchanged or full_stages_run_is_identical or default_background_run_is_identical or sends_the_same_requests_as_before or without_a_registered_agent"` | **5 passed** (M1/M2 equivalence, default run, M2 provider-request pin, placeholder path) |

### Fingerprints

- `data/runs.db`, read via `Get-FileHash` and `Get-Item` only: `00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D`, 311296 bytes, `2026-11-08T15:31:17Z`. This is identical to the baseline.
- `verify.py` found 26 protected files unchanged and 4 changed, all expected: `orchestrator.py`, `tests/test_m3_orchestrator.py`, `tests/test_m3_swot_agent.py` and `tests/test_m3_mvp_agent.py`. There were no unexpected changes.
- `git status --porcelain` shows the baseline 31 lines plus `?? agents/gtm_agent.py` and `?? tests/test_m3_gtm_agent.py`. Branch `main`, HEAD `a098aef0` unchanged.
- The secret scan of the 6 changed and new files found 0 hits. The planted keys in the tests are built from string parts.
- `gtm_agent.py` has 0 comment lines and 0 docstrings.

### Design decisions and plan-vs-code notes (for the reviewer)

1. **Positioning check 3.**
   - With segment data, the allowed target names are the priority segment plus the market segment names. The match ignores case and whitespace, and the stored segment name is kept. Without segment data (no market, or a market with no segments), the allowed names are the founder's `target_customers`.
   - A name that does not match is replaced with the priority segment, or with the founder's first customer, and a warning is added.
   - Without segment data, the positioning basis is forced to `assumption` and `NO_SEGMENTS` is added (9.6).
2. **The audience must name the segment (A-R3 item 1).** The sentence form only carries `{for_whom}`. If `for_whom` does not contain every token of the target segment (`tokens()` from T3), it is replaced by the target segment, and the `AUDIENCE_REPLACED` warning is added. This guarantees that the statement names the segment.
3. **Unusable positioning fails the stage.** An empty problem, category, key_benefit, alternative or differentiator, or a positioning that is removed by the figure or overclaim check, raises `LLMInvalidResponseError(MSG_NO_POSITIONING)` (`llm_invalid_response`). `GtmResult.positioning` is required, so it cannot be dropped the way list items are.
4. **Statement form.** It follows the plan verbatim: `"For {for_whom} who {problem}, {product} is a {category} that {key_benefit}. Unlike {alternative}, {differentiator}."`.
   - `{product}` is the idea title.
   - Each part has its whitespace collapsed and trailing " .;," stripped before assembly, so the stored parts reassemble to the identical statement.
   - The article stays "a" even before a vowel. The template is the plan's, and no a/an logic was added.
5. **Differentiator status.** It is `hypothesis` if any cited fact is a `gap`, or if no cited fact is a `competitor_feature` or `pricing` fact. Otherwise it is `supported`. The draft has no separate refs for the differentiator, so this uses the positioning's `based_on`.
6. **Channel ids and ranking.**
   - Channels go through the checks first. Then they are sorted by `(-audience_fit, cost low<medium<high, speed days<weeks<months, order returned)`.
   - The list is cut to 6 from the bottom of the ranking.
   - `CH{n}` is then numbered by the order returned among the kept channels (A.5: the order returned), so the ids are always CH1..CHk.
   - `priority` is the rank, and `start_here` is set for priority 1 only.
   - `audience_fit` is clamped to 1..5, with a warning. This is not listed in 9.5, but the `Channel` model requires 1..5.
7. **Budget conflict.** A channel gets `budget_conflict = True` when `constraints.budget_level == "bootstrapped"` and `cost_level == "high"`. The channel is kept, and a plain warning "N channel(s) may be above a bootstrapped budget (names)" is added. 9.5 does not ask for a warning, but nothing is changed silently.
8. **Cross-references.** `uses_features` must be `MVP.n` refs present in the digest and become `F{n}`. `addresses_risks` must be `RSK.n` refs and become `R{n}`. Anything else, including bare `F2` or `R1`, is removed with a warning. This mirrors T6's risk-link rule.
9. **Launch phases.**
   - A valid phase has a goal and at least one action that survives the checks. Overclaims and unsupported figures are checked against the whole digest, because phases carry no refs.
   - A repeated phase name keeps the first valid one and counts as a duplicate.
   - Phases are ordered Before launch, Launch, First 90 days. A missing phase is not invented: a warning names it.
   - Fewer than 2 valid phases raises `LLMInvalidResponseError(MSG_TOO_FEW_PHASES)`.
   - Actions are cut at 4. Fewer than 2 actions gives a shortfall warning.
10. **Key messages.** They have no basis or refs, so the overclaim and figure checks run against the whole digest. Duplicates are compared on the message text, and the list is cut at 4.
11. **Early customers.** These use `check_items` (duplicates by `tactic`), are cut at 5, and give a shortfall warning below 3.
12. **Pricing.** No code builds prices. The prompt says "Do not recommend prices. Do not give budgets in money." A money figure survives only when a cited fact contains it (`test_a_money_figure_stays_only_when_a_cited_finding_states_it`).
13. **Quality.** `basis_counts` and `grounded_share` count the positioning, the channels and the early-customer tactics, the items that carry a basis. Constraint provided/assumed comes from `apply_constraint_defaults`, as in T5. GTM adds no "assumed team or months" warning, because it does not use capacity.
14. **Helpers copied from `mvp_agent.py`.** `_complete`, `_counted`, `_clean_text`, `_summary`, `_limitations` and the `_linked` pattern were copied rather than imported, following the accepted T5/T6 convention for private helpers.
15. **Warnings are plain strings.** The notice templates belong to T9.

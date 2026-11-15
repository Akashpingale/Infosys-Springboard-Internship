# M3-T7 review (iteration 1)

Verdict: APPROVED. No blockers.

## Evidence checked

- `git status --porcelain`: the baseline 31 lines plus `?? agents/gtm_agent.py` and `?? tests/test_m3_gtm_agent.py`. Nothing new in routes/, frontend/, web/, docs/, models/, the plan or KIRO_*.md.
- Fingerprints (read-only reruns of the coder's `verify.py` and `check_test_edits.py`): 26 protected files unchanged; 4 changed, all expected (`orchestrator.py`, `tests/test_m3_orchestrator.py`, `tests/test_m3_swot_agent.py`, `tests/test_m3_mvp_agent.py`). Undoing the listed edits restores every baseline hash (True for all four). `data/runs.db` is 00A4F859...337D, 311296 bytes, 2026-11-08T15:31:17Z, which matches the baseline. Secret scan: 0 hits. `gtm_agent.py` has 0 comments and 0 docstrings.
- Registration (`orchestrator.py`): the import is at line 25, the `PendingStrategyAgent` docstring changed at lines 165-166, and `StrategyStage(GtmAgent(), ...)` is at line 217. The class is kept.
- Test edits: the 5 lines match the brief's allowed edits 1-3. Both registry assertions remain exact comparisons, and no assertion was weakened.
- Recorded verification in `coder-notes.md`: T7 72 passed; T3-T6 regression 268 passed; full suite 2112 passed (2040 + 72), 0 failed, 1 known warning; M1/M2 equivalence, default run, provider-request pin and placeholder path 5 passed. The coder's mistaken `-p no:logging` run was explained and rerun with the brief's flags.

## Requirements against code (agents/gtm_agent.py)

- 9.3 flow: `plan_go_to_market` raises `StrategyNotReadyError` before any call when there is no idea or no analysis (lines 617-618). It calls `build_digest(..., swot=, mvp=)` (620) and makes one `call_structured(..., GtmDraft, caller=generate_json)` (624). `build_result`, then `ensure_no_secrets`. `run` writes `context.gtm` and prefixes warnings with "Planning go-to-market".
- A.0/A.3: `SHARED_RULES` is A.0 verbatim and `ROLE` is A.3. The user part follows A.3, including "Do not recommend prices. Do not give budgets in money." The `<facts>` delimiters come from the digest, as in T5/T6. Tests cover the delimiters and the MVP/RSK lines.
- 9.4 statement: `STATEMENT` is the plan's sentence, assembled in code from the stored, shortened parts with `{product}` = idea title. The tests rebuild it with an independent template.
- Differentiator: `hypothesis` if any cited fact is a `gap` or none is a `competitor_feature`/`pricing` fact (lines 343-347). This is tested.
- Ranking: `(-audience_fit, cost, speed, order returned)`. The cut to 6 removes from the bottom. `priority` is the rank and `start_here` is priority 1 only. This is tested, including ties.
- 9.5 check 1: `check_item`/`check_items`/`shorten_fields`/`cut_to_limit`/`remove_duplicates` are used, and `Repairs.warnings()`.
- Check 2: `_linked` keeps only resolvable `MVP.n`/`RSK.n` refs, converts them to `F{n}`/`R{n}` (the digest numbers come from the stored ids, `strategy_context.py` 357/372), and removes the rest with a warning. This is tested.
- Check 3: empty or non-matching segment is replaced with the priority segment (or the founder's customer) with a warning. An empty required part fails with `llm_invalid_response`.
- Check 4: a high-cost channel on a bootstrapped budget is kept with `budget_conflict` set. This is tested across all budgets.
- Check 5: duplicates by name are removed; fewer than 3 channels fails. This is tested.
- Phases: fixed order, a missing phase is not invented and gets a warning, fewer than 2 fails. This is tested.
- 9.6: missing MVP and missing SWOT give plain warnings and the stage still runs. With no market, or a market with no segments, the positioning uses the founder's customers, the basis is `assumption`, and a notice is added. All of these are tested, including in seven-stage runs where MVP or SWOT failed.
- Seven-stage fake run ends `complete` with swot, mvp and gtm stored. The prompt contains every stored MVP.n and RSK.n line (`test_a_seven_stage_run_completes_with_every_strategy_result`).

## Non-blocking notes for the final report

- Plan-internal conflict to record: 9.5 check 3 accepts any market segment name, so a reply that names a non-priority segment keeps it (`test_another_market_segment_is_kept_with_its_stored_name`). A-R3 item 1 says the statement names the priority segment. The prompt asks for the priority segment, and the fake run and the A-R3 test name it. The code follows the more specific check 3. The final report should state this conflict.
- The coder made judgment calls that 9.5 does not spell out: the budget-conflict warning string, the audience replacement, and checking figures in phases and key messages against the whole digest. They are recorded in coder-notes and are consistent with the plan.

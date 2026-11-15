# T9 report: derived fields, notices and Markdown export

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T9 (requirements 11.3, 11.4, 12.5, D-14; `evidence_strength` untouched).
Nothing committed. No existing test edited. No live call. data/runs.db never opened.

## Files changed

| File | Status | Diff vs HEAD (+/-) | Purpose |
|---|---|---|---|
| `agents/derived.py` | modified (was at HEAD before T9) | +120 / -3 | `strategy_summary` (3 lines appended to `executive_summary`), `strategy_verify_next` (appended to `verify_next`), `strategy_sources`, `top_risk`, `first_release`, `start_channel`, `strategy_inputs_missing`; `with_derived_fields` passes the inputs-missing map to `build_notices`. `evidence_strength` not touched. |
| `agents/notices.py` | modified (T4 had added 12 lines) | +254 / -8 vs HEAD | Section 11.3 codes and messages, `STRATEGY_RULES`, per-code-per-stage aggregation in `build_notices`, strategy areas for the fallback, strategy titles for skip/error messages (`TITLES`). `STAGE_TITLES` unchanged. |
| `frontend/analysis_views.py` | modified (was at HEAD before T9) | +237 / -0 | `report_markdown` gains `if full and has_strategy(result): lines += strategy_markdown(result)`; new `swot_markdown`, `mvp_markdown`, `gtm_markdown`, `strategy_markdown`, helpers and copy constants. No existing line removed or changed. |
| `tests/test_m3_derived_notices.py` | new | 396 lines | 23 test functions, 42 test cases |
| `tests/test_m3_report.py` | new | 236 lines | 12 tests |

Hash check (`.agents/tasks/m3-t9/hashes.py compare` against the start-of-task baseline of all 39 uncommitted files): only the five files above differ. No T1-T8 file, no Streamlit file (`frontend/app.py` unchanged), no existing test changed.

## Requirement mapping

- **12.5 executive_summary**: when strategy exists, up to three lines are appended after the M2 lines: `top_risk` ("Main risk (high severity, market): ..."; highest severity, then impact, first listed on a tie), `mvp_scope` (top three in-scope features by backend rank, with the count), `start_channel` (the `start_here` channel). Text comes only from stored fields. Each line carries inherited sources (see conflict 1). Nothing is added without strategy, so existing results and `test_derived_fields.py` are unchanged.
- **12.5 verify_next**: appended `risk` items (every high-severity risk with low confidence, with its early-warning signal), one `constraints` item (team size and/or timeline the MVP plan assumed, values from `constraints_used`), one `channel` item (start-here channel's first experiment).
- **12.5 evidence_strength**: unchanged code; test proves equal values with and without strategy.
- **11.3 notices**: every listed code with its specified message and severity: `strategy_ref_removed`, `strategy_basis_adjusted` ("N points have no supporting finding..."), `strategy_figure_removed`, `strategy_overclaim_removed`, `strategy_duplicate_removed`, `strategy_inputs_missing` (from the agents' no-SWOT/no-MVP warnings and from each result's `quality.inputs_missing`, named "the market analysis / competitor analysis / risk analysis / feature plan"), `mvp_constraints_assumed`, `mvp_over_capacity`, `gtm_budget_conflict`, `strategy_stage_skipped`. Also `strategy_items_cut` and `strategy_text_shortened` (T3 codes, brief) and `gtm_segments_missing` (brief: segment notice). Technical text stays in `detail`.
- **11.4 one notice per code per stage**: in a strategy stage, warnings with the same code are merged into one notice; counts are added up ("3 points were removed ..."), all source warnings kept in `detail` joined by newlines. M1/M2 warnings still get one notice each (test_notices.py "nothing is dropped" still holds).
- **Fallback**: an unknown strategy warning gets "A quality check adjusted part of {the strengths and risks / the MVP plan / the go-to-market plan}. Open the details to see what changed." Any message that would trip `leaks()` falls back too. Strategy rules apply only under a strategy stage label, so `tests/test_m3_checks.py::test_existing_notices_turn_every_strategy_warning_into_a_plain_message` (pins fallback for unlabelled/other-labelled text) passes unchanged.
- **D-14 Markdown**: strategy sections ("## SWOT and risks" with "### Risks (n)", "## MVP recommendation", "## Go-to-market plan") only on `full=True` and only when a strategy part exists; missing parts are stated. Feature/risk ids are shown as names; sources as "market S3"/"competitors S1". No Advisor content is part of a result, so it is never exported (route test stores a chat thread and checks the download).
- **Integration**: `routes/run_routes.py` still calls `report_markdown(run.result, full=True)` (unchanged). Streamlit uses the default path, which is byte-identical.

## Byte-identity proof

- `tests/test_m3_report.py::SNAPSHOT_SHA256 = 3f7005f1...aefe33` is the SHA-256 of the default report produced by the pre-T9 `analysis_views.py` (copy `pre_t9_analysis_views.py.txt`, hash 4B86F798... = `git show HEAD:frontend/analysis_views.py`) for a seven-stage fake result; output saved in `pre_t9_default.md` (same hash).
- `verify_default.py` imports the HEAD version of `analysis_views.py` beside the current one and compares output on: default with strategy, default without strategy, full without strategy, default and full with no analysis (M1 only), default with assumed constraints, and `report_file_name`. All 7 identical (`verify_default.json`).

## Tests

- `tests/test_m3_derived_notices.py` (42 cases): summary lines only with strategy and in order; exact wording; inherited sources resolve to listed sources; mixed-analysis rule; short first release; per-part lines; verify-next entries (risk, constraints both/one assumed, channel); `evidence_strength` equal before/after; result without strategy gets the same derived fields; each 11.3 code's exact message and severity (15 cases); founder basis part; one notice per code per stage with summed counts and merged detail; M2 still one per warning; no field path/id/code in any strategy notice for every agent warning under all three labels; unknown-warning fallback per stage; rules only under strategy labels; strategy error/skip/cancel messages name the stage; clean run has no strategy notice; inputs-missing from the quality block (market failed); missing SWOT gives one notice per stage keeping the warning; two missing inputs named in one notice; assumed resources notice.
- `tests/test_m3_report.py` (12): default byte-identical to the stored snapshot; default never carries strategy; full without strategy unchanged; strategy sections appended after the analyses with one H1; SWOT, MVP (backend rank order, tiers, capacity, deferred reasons) and GTM (positioning, single Start here, launch plan numbered, feature names) coverage; no backend id or key; assumed resources marked; budget conflict noted; missing part stated; `report.md` route exports strategy and no Advisor conversation.

## Commands run and results

| Command | Result |
|---|---|
| `.\.venv\Scripts\python.exe -B .agents\tasks\m3-t9\hashes.py save` (start) | 39 uncommitted files hashed |
| `Get-FileHash`/`Get-Item data\runs.db` (start and end) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z, unchanged |
| `python -B -m pytest -q -p no:cacheprovider -rfE tests` (before T9 code) | 2195 passed, 1 warning |
| `python -B -m pytest -q -p no:cacheprovider -rfE -p no:logging tests\test_m3_derived_notices.py tests\test_m3_report.py` | 54 passed, 1 warning |
| `python -B .agents\tasks\m3-t9\verify_default.py` | 7 of 7 identical to HEAD `analysis_views.py` |
| `python -B -m pytest -q -p no:cacheprovider -rfE tests` (full backend, final) | 2249 passed, 1 warning (Starlette/httpx deprecation, as baseline); 2195 + 54 new |
| `python -B .agents\tasks\m3-t9\hashes.py compare` | only the five T9 files differ |

## Existing-test edits

None.

## Plan-vs-code conflicts and choices

1. `SummaryLine` and `VerifyItem` (KIRO UI upgrade models) carry one `analysis` and plain `source_ids`, while strategy items inherit `analysis:id` keys from both analyses. Changing those models would alter an existing response field (stop condition), so each strategy line carries the sources of the analysis most of its inherited sources come from (first named on a tie). The other analysis's sources stay on the item itself (Strategy tab, Markdown).
2. 11.3 lists no code for some agent warnings (ratings clamped, empty parts removed, confidence lowered, fewer points than asked, founder feature added, metric target removed, segment/audience replaced, launch phases missing). They get the plain fallback message, as 11.3 requires for unrecognised strings. `gtm_segments_missing` (info) was added for the no-segments warning the brief names; `strategy_items_cut`/`strategy_text_shortened` use T3's codes.
3. 11.3 message for assumed constraints is "Your team size and timeline were not given, so the plan assumes {X}." When only one is assumed the message names that one ("Your team size was not given, ...").
4. "One notice per code per stage" (11.4) is applied to strategy stages only; M1/M2 notices remain one per warning because `tests/test_notices.py` pins that and Section 4 keeps M2 behaviour.
5. `strategy_inputs_missing` takes the missing inputs from each stored result's `quality.inputs_missing` (so a SWOT written without the market analysis gets a notice) and merges them with the agents' own no-SWOT/no-MVP warnings into one notice per stage.
6. New code in existing files follows those files' style (module docstrings and comments exist there); the two new test files have no comments or docstrings (plan 0.5).

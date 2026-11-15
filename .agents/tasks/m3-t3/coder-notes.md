# M3-T3 coder notes

## Iteration 1 (initial implementation; no review.json existed)

### Files added (only these five; nothing else in the repository changed)
- `agents/strategy_context.py`: the findings digest (Section 5.3).
- `agents/strategy_checks.py`: checks 1 to 8 and 10 of Section 7.5, source inheritance, warning builders.
- `tests/test_m3_digest.py` (31 tests), `tests/test_m3_checks.py` (69 tests), `tests/test_m3_strict_schema.py` (20 tests).

Helper scripts used only for verification, kept in this folder: `smoke.py` (digest sizes of the live fixtures),
`unused.py` (unused-import check), `secret_scan.py` (secret scan of the new files).

### What was built
`strategy_context`:
- `build_facts(idea, constraints, market, competitors, *, swot=None, mvp=None)` returns a flat list of `Fact(ref, kind, text, basis, sources)`.
  It reads the typed models through the same accessors the pipeline uses (`PipelineResult.idea/.constraints/.market/.competitors`,
  `AgentContext.market/.competitors`), passed in as typed `ExtractedIdea`, `StrategyConstraints`, `MarketOpportunityResult`,
  `CompetitorAnalysisResult`, `SwotRiskResult`, `MvpResult`.
- Refs: `IDEA.n`, `CON.n`, `MKT.n`, `CMP.n` numbered from 1 in a fixed traversal order; `RSK.n` and `MVP.n` reuse the stored
  number of `R{n}` / `F{n}` (Appendix A.5). Same input gives byte-identical output (tested).
- Sources: `analysis:id` strings (`market:S3`, `competitors:S1`), only ids listed in that analysis's own `sources`, upper-cased,
  de-duplicated, in item order. `S0` and unknown ids are never inherited. Market and competitor numbering stay separate.
- `apply_constraint_defaults` (team 2, months 3; other fields stay null) returns used / provided / assumed field names; provided
  constraints become `user_provided` CON facts, defaults become `assumption` CON facts.
- `build_digest(..., max_chars=None)` renders `<facts>` ... `</facts>`, one line per fact `[REF] (kind) text`, and trims to
  `get_settings().strategy_digest_max_chars` (24000) when `max_chars` is not given.
- Trim order (`TRIM_ORDER`): `broader_market` rows, then trends after the first `TRENDS_KEPT=3`, then competitor `queries_used`,
  then demand items after the first `DEMAND_KEPT=3`; within each tier the last-listed fact goes first. Kept facts keep their refs;
  a dropped ref is no longer valid (`Digest.fact` returns None, so check 1 removes it).
- Text placed in the block goes through `evidence.clean_prompt_text` plus removal of the `facts` tag in every form (same pattern
  builder as evidence.py), repeated until stable. Evidence ids that analyses wrote into their prose ("(S12)", "(S1, S2, S3)",
  "sources S2 and S3") are removed from MKT and CMP texts, so the model never sees a source id; other words are kept.

`strategy_checks`:
- Check 1 `split_refs` (normalises `mkt.1`, `[MKT.1]`, spaces; de-duplicates; reports unknown refs).
- Checks 2 and 3 `adjusted_basis`: no valid ref and `ai_interpretation`/`user_provided` becomes `assumption`;
  `user_provided` without an `IDEA.*`/`CON.*` ref becomes `ai_interpretation`.
- Source inheritance `inherited_sources` returns `StrategySourceKey` models (union of valid refs' sources, in order).
- Check 4 reuses `figures.check_claim` against the texts of the cited facts: `NOT_FOUND` or `UNCLEAR` removes the item
  (currency, percent and million/billion amounts; plain counts and years are not figures, as in Milestone 2).
  `figure_supported` exposes the same rule for one text (for MVP `suggested_target`, T6).
- Check 5 `OVERCLAIM_PHRASES` (exact plan list), case-insensitive, word-bounded, hyphen/space and straight/curly apostrophe variants.
- Check 6 `remove_duplicates`: tokens = lower-case words minus `figures.STOP_WORDS`, singularised with `figures.singular`;
  overlap = shared tokens / tokens of the longer text; >= 0.8 removes the later item.
- Check 7 `cut_to_limit` keeps the first `maximum` items (callers sort first, e.g. risks by severity in T5).
- Check 8 `shorten` / `shorten_fields`: cut at a word boundary with "..." and never above the limit.
- `check_item` / `check_items` run 1 to 5 per item, then 6, 7, 8.
- Check 10 `secret_findings` / `ensure_no_secrets`: configured key values (LLM, Tavily, Groq; at least 8 characters) and
  key-shaped patterns, over every string and map key of a model or value; returns labels only, never the value.
- Warning builders: `Repairs.warnings()` returns at most one plain warning per code, counts aggregated, in `WARNING_CODES` order.

### Plan-vs-code conflicts and decisions
1. Notices (11.3) vs T3: the plan assigns new notice codes to `agents/notices.py` in the derived/notices task (17.2 and the
   task with `tests/test_m3_derived_notices.py`), not T3. `notices.py` is unchanged. Warning builders live in
   `strategy_checks.py` and produce warnings in the existing style (11.4). Test
   `test_existing_notices_turn_every_strategy_warning_into_a_plain_message` proves the existing fallback turns each one, bare,
   with a stage prefix or with a field path, into `quality_adjusted` with a message that does not leak.
2. Codes for checks 7 and 8: the plan names none. Added `strategy_items_cut` and `strategy_text_shortened` as warning codes in
   `WARNING_CODES` (no notice mapping yet; the later notices task can map them).
3. Check 10 error: 12.4 has no secret-specific code and `utils/errors.py` is protected, so `ensure_no_secrets` raises the base
   `AppError` (`internal_error`, generic message, no secret in the message).
4. 5.3 rule 1 ("refs and texts only") vs A.2 ("IDEA facts of kind key_feature"): the line shows the kind as well as ref and text.
   Basis and sources are never shown.
5. "Older demand items" has no date in the model: interpreted as demand items after the first three, dropped last-listed first.
   "Extra trends" interpreted the same way (after the first three).
6. Facts without their own basis (segments, coverage rows, figures, prices, overviews, queries, data quality, caveats) are
   `sourced` only when they inherit at least one valid source (figures and prices also need status `sourced`), otherwise
   `ai_interpretation`. IDEA facts are `user_provided`.
7. 15.1.2 says the digest never reads settings: the content is built only from the typed results; only the size cap is read from
   `STRATEGY_DIGEST_MAX_CHARS`, as 5.3 and 12.6 require.
8. If the never-dropped facts alone exceed the cap, the digest is returned over the cap with `Digest.fits == False` and nothing
   protected is cut; the agent task (T5) decides what to do. With the live fixtures this does not happen.
9. `_tag_pattern` is a private helper of `agents/evidence.py`; it is imported (not copied) so the digest uses the exact tag
   matching of Milestone 2. `evidence.py` is unchanged.
10. Overclaim matching follows the list literally, so a negated use ("not guaranteed") is also removed. Deliberately not
    special-cased.

### Verification (commands run, results)
1. `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_digest.py tests/test_m3_checks.py tests/test_m3_strict_schema.py`
   -> **120 passed**, 1 warning (Starlette/httpx deprecation), 0 failed.
2. `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -rfE` -> **1892 passed**, 1 warning, 0 failed
   (1772 baseline + 120 new).
3. Determinism: tested (byte-identical text and identical facts for both live fixtures). Digest sizes at the default cap 24000:
   **agritech 10,666 chars (66 facts)**, **fintech 15,038 chars (88 facts)**, nothing dropped. The three docs/test_runs_m2
   results also fit (tested).
4. `.\.venv\Scripts\python.exe -B -c "import agents.strategy_context, agents.strategy_checks"` -> ok; importing
   `agents.strategy_checks` alone -> ok (no cycle).
5. `data/runs.db`: SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes,
   LastWriteTimeUtc 2026-11-08T15:31:17Z: identical to baseline.md. All 12 T1/T2 file hashes and the 4 helper hashes
   (evidence, figures, integrity, notices) are identical to baseline.md.
6. `git status --porcelain`: baseline entries unchanged plus exactly the five new files
   (`agents/strategy_checks.py`, `agents/strategy_context.py`, `tests/test_m3_checks.py`, `tests/test_m3_digest.py`,
   `tests/test_m3_strict_schema.py`) and `.agents/`. Branch `main`. No commit, push, stash or branch change.
7. Secret scan of the five new files (AIza, gsk_, tvly-, sk-, Bearer token, PRIVATE KEY): **0 hits**. Fake keys in tests are
   built from string parts.
8. New files carry no comments or docstrings (Plan 0.5); no unused imports.

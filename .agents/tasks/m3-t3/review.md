# M3-T3 review (findings digest and shared checks)

Verdict: APPROVED. No blockers.

## Scope and protected files
- `git status --porcelain` shows the baseline entries plus exactly the five new files and `.agents/`. `git diff --stat` covers only the seven T1/T2 tracked files already listed in baseline.md.
- Get-FileHash of all 12 T1/T2 files and of evidence.py, figures.py, integrity.py and notices.py matches baseline.md exactly. `data/runs.db` and `.env` were not opened; the coder recorded an unchanged runs.db hash.
- No T4+ work: no agents, prompts, orchestrator, run_manager, routes, React or notices.py changes, and no LLM calls.

## Section 5.3 (strategy_context.py)
- Facts: `Fact(ref, kind, text, basis, sources)`. Kinds cover the plan list (idea_problem, demand, market_size, trend, segment, opportunity, limitation, competitor, gap, differentiation, coverage, risk, feature).
- Refs: IDEA/CON/MKT/CMP are numbered from 1 in a fixed traversal order. RSK/MVP refs are added only when `swot`/`mvp` are passed (rule 4) and reuse the stored R{n}/F{n} numbers.
- Sources: each fact gets `analysis:id` keys, using only ids listed in that analysis's own `sources`. Keys are upper-cased and de-duplicated, and S0/unknown ids are never inherited.
- Rule 1: source ids written into MKT/CMP prose are stripped by `without_source_ids`. The tests assert that no `S\d+` id, URL or `analysis:` key appears in the rendered text of either live fixture.
- Budget: the cap comes from `get_settings().strategy_digest_max_chars`. The trim order is `TRIM_ORDER` = broader_market, trends after the first 3, query_used, demand after the first 3. Protected kinds are never in the queue.
- Delimiters: the digest is wrapped in `<facts>` … `</facts>`. Fact text goes through `evidence.clean_prompt_text` plus repeated removal of the facts tag. An injection test covers closing, attributed, split, zero-width and full-width tag variants.

## Section 7.5 (strategy_checks.py)
- Check 1: `split_refs` normalises refs and removes unknown ones (`strategy_ref_removed`).
- Checks 2 and 3: `adjusted_basis` turns an item with no valid ref into an assumption. A `user_provided` item without an IDEA/CON ref becomes `ai_interpretation`. Counts are aggregated into one warning. The draft basis enum excludes `sourced` (STRATEGY_BASES), so a sourced item with no refs cannot occur.
- Check 4: reuses `figures.check_claim` against the cited fact texts. NOT_FOUND and UNCLEAR remove the item.
- Check 5: `OVERCLAIM_PHRASES` holds exactly the plan list. Matching is word-bounded and accepts hyphen/space and apostrophe variants.
- Check 6: token overlap is computed as shared tokens divided by the token count of the longer text. At 0.8 or more, the first item is kept.
- Check 7: `cut_to_limit` keeps the first N items.
- Check 8: `shorten` cuts at a word boundary and stays within the limit.
- Check 10: `secret_findings` scans for configured key values and key-shaped patterns across all strings and map keys. `ensure_no_secrets` raises `AppError` with a generic message.
- Check 9 is not implemented, as required.
- Warning builders: `Repairs.warnings()` gives one lower-case warning per code, matching the existing style (11.4). A test shows the unchanged notices.py fallback turns each warning into a plain `quality_adjusted` message that does not leak, with or without a prefix.

## Tests and evidence
- Every T3 test bullet has a test: ref determinism, analysis:id mapping, both live fixtures under the cap, trimming order, invalid ref removal, basis adjustment, planted figures (supported and unsupported), overclaim list, duplicates, secret scan, and the strict-schema validator (`groq_client.strict_schema` with Draft202012Validator) on all four drafts.
- Tests use fixtures and fakes only: no network, no LLM calls. Fake keys are built from string parts, and conftest replaces the env keys.
- The new files contain no comments or docstrings.
- coder-notes.md records: 120 passed for the T3 files; full suite 1892 passed, 0 failed (1772 + 120). Digest sizes: agritech 10,666 chars and fintech 15,038 chars, both under the 24000 cap.

## Recorded plan-vs-code decisions (accepted)
- Fact lines also show the kind (A.2 relies on kinds).
- Codes `strategy_items_cut` and `strategy_text_shortened` were added for checks 7 and 8, as required by 7.5 #7 and 6.6.3.
- Check 10 raises the base `AppError` because utils/errors.py is protected.
- The digest reads only the size cap from settings (15.1.2 vs 5.3/12.6).
- When protected facts alone exceed the cap, the digest is returned with `fits == False`.
- `_tag_pattern` is imported from evidence.py, which is unchanged.

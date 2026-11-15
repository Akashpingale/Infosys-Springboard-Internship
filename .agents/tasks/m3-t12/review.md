# T12 review: Backend consolidation checkpoint

Verdict: **APPROVED**. No blockers.

## What I checked and ran myself

| Check | Result |
|---|---|
| `pytest tests/test_m3_no_secrets.py` | 52 passed, 1 warning (existing Starlette/httpx deprecation) |
| Full backend suite `python -B -m pytest -q -p no:cacheprovider -rfE` | 2416 passed, 1 warning (T11 baseline 2364 + 52 new) |
| `npm run typecheck` (web/) | Clean, both `tsc --noEmit` passes |
| OpenAPI regeneration | Dumped `app.openapi()` to a `%TEMP%` file with `RUNS_DB_PATH` on a temp path that was never created: 11 paths, 79 schemas. `npx openapi-typescript` on it produced SHA-256 A03D7C42…CF7C9, identical to the current `web/src/api/types.gen.ts` (git-ignored per `.gitignore:31`). Temp folder removed |
| Secret scan (coder's `secret_scan.py`, read-only, prints labels/counts only) | 508 listed, 413 scanned, 95 binary, 0 hits |
| `data/runs.db` (Get-FileHash/Get-Item, before and after my test runs) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes, 2026-11-08T15:31:17Z: matches the brief |
| Changed files vs. start baseline (`hashes.py check`, 47 files hashed at 14:21, after the T11 review at 14:20) | Only `new scripts/check_m3_contracts.py` and `new tests/test_m3_no_secrets.py`. No project file other than these and the git-ignored `types.gen.ts` was written after 14:00. `types.gen.ts` is the output that the required `api:types` step writes (same handling as T1 and T8) |
| Existing-test edits | None |
| Git | `main`, HEAD `a098aef`, nothing committed, staged or stashed |

## Requirement mapping (Section 18 T12)

- Full suite: passes (above).
- `scripts/check_m3_contracts.py` is offline. It loads the file as `PipelineResult`, rebuilds each stage's untrimmed digest, and checks the 7.5, 8.4/8.5 and 9.4/9.5 rules. Before relying on it, I compared it with the agents. Ref numbering is assigned before trimming in `build_digest` (strategy_context.py:436-444), so the untrimmed digest is a superset and produces no false `ref_unknown`. The rank key matches `mvp_agent._rank_key` (mvp_agent.py:209-212). Tiers come from the same `assign_tiers` in the same order. Segment selection matches `gtm_agent._segment_choices` and `_positioning` (gtm_agent.py:322-375), including the priority-segment rule. `budget_conflict` matches gtm_agent.py:408/423. List maxima and length limits are left to the schema validation.
- Synthetic pass and planted violations: 36 parametrised cases cover every rule code except `schema`, `unreadable` and `secret`, and those three have dedicated tests. Each case asserts the rule, exit code 1 and the summary line. The secret test confirms that values are never printed.
- Planted keys never leave the process: three configured keys plus key-shaped text are built from string parts. The test asserts the store path is the temp DB before any run starts. It checks prompts to every fake model, responses, the run list and detail, report.md, `/api/meta`, the raw `runs.db*` bytes and DEBUG logs. It covers a 7-stage run, the Advisor, a strategy re-run, a key in a strategy reply (fails only that stage), the retro job, provider errors that quote the keys, and a key typed into a question (redacted in the saved thread).
- Route table and settings: listed in the report. They match the regenerated schema (16 operations) and Section 12.6 (eight M3 settings).

## Non-blocking notes (no change requested)

- The contract script may flag a correct result in two rare cases. A market segment name over 160 characters gets shortened in `Positioning.target_segment`. A founder key feature name gets truncated by the feature length limit. Both are edge cases of an offline checker and do not affect runtime behaviour.
- Coder's open item 3 (Advisor reply has no secret scan) belongs to T10/T11 behaviour. It was correctly recorded and not changed in T12. It should carry into the final report.
- `# noqa: E402` on imports follows the existing `scripts/*.py` convention. There are no comments or docstrings otherwise.

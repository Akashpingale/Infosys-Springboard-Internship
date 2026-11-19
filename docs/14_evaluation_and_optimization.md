# 14. Evaluation and optimisation (Milestone 4, requirement R3)

Status: **method and tooling ready; no comparison executed.** Every result cell below says "not executed". No live provider call was made while preparing this document, and no improvement is claimed. The default profiles stay `v1`.

Source of the requirements: `MILESTONE_4_MASTER_IMPLEMENTATION_PLAN (1).md`, Section 3 (scope decisions), Section 9.4 (metrics), 9.6 (candidate profiles), 9.7 (adoption rule, as revised by Section 3), 9.8 (rubric), 9.10 (accuracy hardening) and Appendices A.2 and A.3.

## 1. What this milestone optimises

Requirement R3 names four areas. Each one has a switch, so `v1` stays the reference and the rollback.

| Area | What was built | Switch | Default |
|---|---|---|---|
| Web search query design | Query profile `v2` (Q-1 to Q-6) and parallel search | `QUERY_PROFILE`, `SEARCH_MAX_PARALLEL` | `v1`, `1` |
| Prompt engineering | Prompt profile `v2` (P-1, P-2, P-4, P-5) | `PROMPT_PROFILE` | `v1` |
| Agent reasoning quality | Digest de-duplication (P-6); self-check line for SWOT, MVP and go-to-market (P-5) | `PROMPT_PROFILE` | `v1` |
| Output accuracy | Matrix consistency check with the notice `competitor_feature_mismatch` (9.10 step 1) | `PROMPT_PROFILE` | `v1` |

`v1` is today's behaviour, byte for byte. `tests/test_m4_profiles_v1_snapshots.py` renders every v1 prompt, query set and reply schema on fixed fixtures and compares them with the snapshots taken in T1 (`tests/snapshots/m4_v1_profiles.json`). `tests/test_m4_matrix_consistency.py` compares the existing integrity, relevance and competitor checks on every stored result fixture with a snapshot taken before any T6 change (`tests/snapshots/m4_v1_checks.json`).

## 2. Method: the three-idea manual pilot (Section 3)

Section 3 replaces the original evaluation package, recording and replay, the resumable runner, the blind packs and the automated adoption evaluator with a small manual comparison. This is a limited pilot, **not** the original six-idea benchmark, and it cannot support a claim of general accuracy improvement.

| Item | Decision |
|---|---|
| Ideas | The three Milestone 2 ideas, with their fixed submissions in `data/test_ideas/`: `agritech.json`, `fintech_cashflow.json`, `foodtech_surplus.json` |
| Runner | The existing `scripts/run_m3_live.py` (seven stages; saves the full `PipelineResult`, including `market_search`, `competitor_candidates` and `competitor_search`, plus `usage` and `versions`) |
| Variants | Baseline (`QUERY_PROFILE=v1`, `PROMPT_PROFILE=v1`); query candidate (`QUERY_PROFILE=v2`, `PROMPT_PROFILE=v1`); prompt candidate (`QUERY_PROFILE=v1`, `PROMPT_PROFILE=v2`) |
| Order | The baseline is captured first, before any default changes |
| Same evidence for prompt comparisons | Not feasible with the existing runner: each run searches again, so the evidence can differ between the baseline and the prompt candidate. This is a confounding factor and must be stated next to every prompt-candidate result |
| Recall | Needs verified reference competitor names for each idea: `[FOUNDER TO FILL]`. Without them, competitor recall is "not measured" |
| Rubric | Scored by people (Section 9.8), never by a model. The blind pack script is out of scope, so the scorer compares the saved Markdown files without knowing the variant where possible; how the blinding was done is recorded |
| Search workers | Keep `SEARCH_MAX_PARALLEL=1` for these runs. The Milestone 3 runner's `Meter` is not lock-protected, so its own search counts can be off with more than one worker. `usage` is exact either way |

### 2.1 Steps for the user (not run by Kiro)

Preconditions: exposed keys rotated (T0 report Section 8), `.env` filled by you, credit use approved. Run from the repository root with the virtual environment active. Each run of three ideas makes about 3 × 7 AI requests and up to about 3 × 12 searches (`docs/test_runs_m3/README.md`), so the three variants make about 63 AI requests and up to about 108 searches. The query candidate adds at most 1 search and 3 credits per idea (Section 4.1).

PowerShell:

```powershell
$env:SEARCH_MAX_PARALLEL = "1"
$env:QUERY_PROFILE = "v1"; $env:PROMPT_PROFILE = "v1"
python scripts/run_m3_live.py --yes --out docs/test_runs_m4/baseline
$env:QUERY_PROFILE = "v2"; $env:PROMPT_PROFILE = "v1"
python scripts/run_m3_live.py --yes --out docs/test_runs_m4/query_v2
$env:QUERY_PROFILE = "v1"; $env:PROMPT_PROFILE = "v2"
python scripts/run_m3_live.py --yes --out docs/test_runs_m4/prompt_v2
```

POSIX shell:

```sh
SEARCH_MAX_PARALLEL=1 QUERY_PROFILE=v1 PROMPT_PROFILE=v1 python scripts/run_m3_live.py --yes --out docs/test_runs_m4/baseline
SEARCH_MAX_PARALLEL=1 QUERY_PROFILE=v2 PROMPT_PROFILE=v1 python scripts/run_m3_live.py --yes --out docs/test_runs_m4/query_v2
SEARCH_MAX_PARALLEL=1 QUERY_PROFILE=v1 PROMPT_PROFILE=v2 python scripts/run_m3_live.py --yes --out docs/test_runs_m4/prompt_v2
```

Environment variables that are already set win over `.env`, so the profile values above apply to that shell only. Check `versions.query_profile` and `versions.prompt_profile` in each saved result to confirm which variant ran. Then fill the tables in Section 5 from the saved JSON files, by hand, and apply the rule in Section 3.

## 3. Metrics (Section 9.4) and the adoption rule (Section 9.7, revised by Section 3)

### 3.1 Metrics

Guard metrics must not worsen. Target metrics are what the candidates try to improve. Each value is read from the stored result JSON; nothing new is instrumented except `usage` and `versions` (T1).

| Metric | Definition | Kind | Better | Where to read it |
|---|---|---|---|---|
| Completion rate | runs with status `complete` ÷ runs attempted | Guard | higher | `status` |
| Stage failure rate | failed or skipped stages ÷ stages attempted | Guard | lower | `errors`, warnings starting "skipped because" |
| Invalid-output rate | stages failing with `llm_invalid_response` ÷ LLM stages | Guard | lower | `errors[].code` |
| Integrity violations | count from the existing integrity checks on the stored result | Guard | zero | `agents/integrity.py` (needs the stored targeted bundles) |
| Unsupported figures | figures in labelled text that no cited source states | Guard | zero | `figure_unmatched` notices; strategy `FIGURE_REMOVED` |
| Competitor recall | reference `must_find` names matched ÷ `must_find` size | Target | higher | `competitors.competitors[].name` against `[FOUNDER TO FILL]` |
| Competitors with a sourced offering | competitors with basis `sourced` and an offering ÷ competitors found | Target | higher | `competitors.competitors[]` |
| Market-size availability | share of TAM, SAM, SOM with status `sourced` and a value | Target | higher | `market.market_size` |
| Source diversity | distinct domains cited across market and competitors | Target | higher | `market.sources`, `competitors.sources` |
| Sourced share | labelled market and competitor items with basis `sourced` ÷ labelled items | Target | higher | every `basis` field |
| Repair warnings per run | code-side repairs per run, by notice code | Target | lower | `notices[].code` |
| Grounded share (strategy) | from the Milestone 3 quality block | Target | higher | `swot/mvp/gtm.quality.grounded_share` |
| Matrix consistency | competitors whose key features conflict with the matrix ÷ competitors | Target | lower | `competitors` against `comparison.rows` |
| Seconds per stage and total | stored timings | Target | lower | `timings` |
| AI requests and searches per run | `usage` totals and per stage | Cost | lower | `usage` |

`usage.search_calls` counts requests, not credits. The query candidate's deeper market-size searches cost 2 credits each instead of 1 (Section 4.1), so the credit difference does not show in `usage` and must be added by hand.

Aggregation per variant: mean, minimum and maximum across the three ideas, plus the per-idea table. With three ideas no significance claim is possible, and none is made.

### 3.2 Adoption rule

The thresholds below were fixed before any data was seen. Changing them after seeing the data is not allowed.

A candidate profile becomes the default only if **all** of these hold, checked by hand from the Section 5 tables:

1. Every guard metric is equal or better than the baseline, and no single idea is worse by more than one run on any guard.
2. At least one target improves by its threshold: competitor recall +0.10 absolute, or repair warnings per run −25 percent, or total seconds −15 percent, or market-size availability +0.15.
3. No other target worsens beyond its tolerance: recall −0.05, sourced share −0.05, availability −0.10, total seconds +10 percent, searches per run more than +2.
4. The rubric means (Section 3.3) do not fall by more than 0.2 on any dimension.
5. **Revised by Section 3:** the comparison used the three pilot ideas (instead of at least six), each run in every variant. A failed or partial run caused by a provider quota is a valid, documented result, not an exclusion.

Otherwise `v1` stays the default and the candidate stays available through its setting. Even if every condition holds, the default changes only after your explicit approval (Section 5, T6 prompt), and the result is described as a three-idea pilot.

Parallel search follows a simpler rule (9.7): unchanged outputs on fakes (met in T5: `tests/test_m4_parallel_search.py`) and a measured reduction in search-stage seconds on the baseline ideas (not executed). The default stays `1` until the timing is measured and you decide (T5 decision, pending).

### 3.3 Reasoning-quality rubric (Section 9.8)

Scored by you, and by one teammate if available, on a 1 to 5 scale. Scores are never produced by a model.

| Dimension | Score 1 | Score 3 | Score 5 |
|---|---|---|---|
| Specificity | Could describe any startup | Mixes idea-specific and generic points | Nearly every point is about this idea's facts |
| Groundedness | Claims with no visible basis | Some links to evidence | Each key point visibly rests on cited findings or is labelled assumption |
| Actionability | Vague advice | Some concrete steps | Concrete first experiments, features and channels the founder could act on this week |
| Coherence | Sections contradict each other | Minor mismatches | Risks, MVP, channels and positioning agree |
| Honesty about uncertainty | Overconfident | Some caveats | Gaps, assumptions and unknowns are plain |

## 4. Candidate profiles

### 4.1 Query profile `v2` (T5)

Built and tested offline in T5 (`agents/query_profile.py`, `tests/test_m4_profiles_v2.py`, 43 tests). Each flag can be switched off on its own inside `v2`.

| ID | Change | Status |
|---|---|---|
| Q-1 | Extraction also returns 3 to 5 `search_terms`; queries use them | In `v2`. The React flow reviews the idea first and starts the run with the reviewed idea, so it has no terms and falls back to today's text; the existing runners extract the idea themselves, so Q-1 applies there |
| Q-2 | Launch region in demand and competitor queries; current year in recency queries | In `v2`. The region comes only from strategy constraints |
| Q-3 | News topic and a one-year window for the funding and news query | In `v2`; support confirmed from Tavily's public API reference without a key or an API call (T5) |
| Q-4 | At most 2 results per domain; snippets under 40 characters dropped | In `v2` |
| Q-5 | Two competitor-discovery phrasings | In `v2`; at most +1 search per run, never above `COMPETITOR_MAX_EXTRA_QUERIES` |
| Q-6 | Market-size queries with unit synonym, region and the deeper search level | In `v2` only, never a default; +2 credits per run |
| Q-7 | 400-character competitor snippets | Left out, not applicable: no snippet-length setting exists (`SNIPPET_MAX = 300` is a schema constant) |

Cost of `v2` per run: at most +1 search (the 9.7 tolerance is +2) and at most +3 credits.

### 4.2 Prompt profile `v2` (T6)

Built in `agents/prompt_profile.py`. The rule text is the A.2 wording. `v1` text is untouched; v2 adds lines to the user part of each prompt, and every system prompt stays as in v1. Tests: `tests/test_m4_prompt_profile_v2.py`.

| ID | Agent | Added instruction | Position | Status |
|---|---|---|---|---|
| P-1 | Market, competitor (phase C) | Copy units and magnitudes exactly; never use a number cut off in the snippet; no conclusions the source does not state; pain points about this idea's problem only; report both figures when sources disagree | Before the facts | In `v2` |
| P-2 | Extraction, market, competitor (phase C), SWOT, MVP, go-to-market | Keep each field to the stated length; prefer fewer, stronger points | Before the facts | In `v2` |
| P-3 | Market, competitor, SWOT, MVP, go-to-market | The three most repaired rules restated after the facts | After the facts | **Deferred**: A.2 chooses them from the baseline repair counts, and no baseline exists |
| P-4 | Competitor (phase C) | Key features come from the competitor's own cited text; the comparison table uses the same wording | Before the facts | In `v2` |
| P-5 | SWOT, MVP, go-to-market | Check that each point names something specific from this idea's facts; remove points that would fit any startup | After the facts (last line) | In `v2` |
| P-6 | Strategy digest | Duplicate facts (same text, ignoring case and spacing) removed before rendering and before trimming to the digest limit; refs of the kept facts are unchanged | Code | In `v2` |

Scope notes:
- Competitor phase A (the candidate list) is not in A.2's agent list, so its prompt is the same in both profiles. The Advisor and the report narrative are also outside A.2 and unchanged.
- Prompt version strings: each agent records `<agent>-v2` under `PROMPT_PROFILE=v2` (for example `market-v2`), and `-v1` otherwise. Extraction records `extraction-v2+search-terms` when both profiles are `v2`.
- Length: each v2 prompt is at most 700 characters longer than its v1 prompt on the test fixtures.
- Reply schemas are unchanged in both profiles, so the strict-schema tests still pass.

### 4.3 Accuracy hardening (Section 9.10)

**Step 1, matrix consistency (built).** A competitor may not list a feature as a key feature while the comparison matrix marks that feature `unclear` or `no_evidence_found` for it. How both are produced: the model writes each competitor's `key_features` and the matrix cells in the same phase C reply, and `build_comparison` keeps the matrix features that a competitor lists or the idea names. The repair, in `agents/competitor_checks.py` `align_key_features`, runs after the matrix is built:

- If a source the competitor cites names the competitor and contains every word of the feature, the cell becomes `evidence_found` with those sources, and the warning says "so the table was corrected".
- Otherwise the feature is removed from the key features, `info_completeness` is recounted, and the warning says "so the feature was removed".
- The search summary `S0` never counts as a source. Features outside the matrix are left alone. `feature_coverage` is recounted from the rows.
- Both warnings become the notice `competitor_feature_mismatch` (Section 11.4), with the plain messages "A competitor's listed feature did not match the comparison table, so the table was corrected." and "…so the feature was removed." Neither names a field.

The check runs only under `PROMPT_PROFILE=v2`, because it changes stored analysis results and the brief keeps every such change behind the v2 switch until there is evidence. Under `v1` the competitor guards produce exactly what they produced before T6 on every stored fixture.

Re-check of the stored fixtures with the v2 guards (code only, no model; `t6\matrix-conflicts.log` in the task bookkeeping). These are fixture observations, not a measured improvement:

| Fixture | Competitors | Listed key features | Conflicts in the stored result | v2 re-check |
|---|---:|---:|---:|---|
| `docs/test_runs_m2/agritech.json` | 1 | 3 | 2 | the guards stop with "no competitor confirmed" in both profiles, because the stored file has no targeted search bundle |
| `docs/test_runs_m2/fintech_cashflow.json` | 5 | 13 | 2 | 3 notices: 3 features removed |
| `docs/test_runs_m2/foodtech_surplus.json` | 4 | 9 | 4 | 4 notices: 1 table cell corrected, 3 features removed |
| `web/src/test/strategyFixture.synthetic.json` (synthetic) | 5 | 8 | 1 | 1 notice: 1 table cell corrected |

`web/src/test/liveAgritech.json` and `liveFintech.json` hold the same results as the Milestone 2 agritech and fintech files and give the same numbers. The notice count need not equal the stored conflict count: the re-check runs every competitor guard again on the stored output and checks the matrix those guards rebuild, not the stored matrix.

**Step 2, baseline-driven fixes (deferred, needs approval).** 9.10 asks for the most frequent repair warnings across the baseline, with examples, and a proposal for at most five fixes that you approve before they are built. No baseline exists, so no fix was proposed for building. For orientation only, the repairs already stored in the three committed Milestone 2 results (27 Oct, before Milestone 3, so they are not the baseline):

| Notice code | Count (3 ideas) | Example (stored warning) |
|---|---:|---|
| `competitor_removed` | 4 | agritech: a competitor was removed because the founder did not name it in the submission |
| `figure_unmatched` | 3 | fintech_cashflow: a figure in a sourced demand claim did not appear with the same magnitude and unit in its cited source |
| `off_topic_removed` | 2 | agritech: a customer problem was not about the problem the idea solves |
| `candidates_failed` | 1 | agritech: phase A failed because the AI service was busy, so only generic competitor searches ran |
| `claim_removed` | 1 | agritech: a competitor strength had no valid source |

After the baseline is captured, Kiro ranks the repair codes across it, proposes at most five fixes with a planted-offender test each, and builds only the ones you approve. P-3's three restated rules are chosen from the same counts.

**Step 3, no regression (built).** `tests/test_m4_matrix_consistency.py` re-runs the market and competitor guards and the integrity checks on all six stored result fixtures and compares the outcome with `tests/snapshots/m4_v1_checks.json`, taken before any T6 change. Under v1 the outcome is identical. Under v2 the only differences are the added `competitor_feature_mismatch` warnings, and no integrity violation appears.

## 5. Comparison tables

Fill these from the saved results in `docs/test_runs_m4/`. Until then every result cell is "not executed".

### 5.1 Per idea

| Idea | Variant | Status | Total seconds | AI requests | Searches | Credits | Recall | Sourced offering share | Market-size availability | Source diversity | Sourced share | Repairs | Grounded share | Matrix conflicts | Integrity violations | Unsupported figures |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agritech | baseline | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed |
| agritech | query v2 | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed |
| agritech | prompt v2 | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed |
| fintech_cashflow | baseline | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed |
| fintech_cashflow | query v2 | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed |
| fintech_cashflow | prompt v2 | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed |
| foodtech_surplus | baseline | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed |
| foodtech_surplus | query v2 | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed |
| foodtech_surplus | prompt v2 | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed | not executed |

### 5.2 Per variant (mean, minimum, maximum across the three ideas)

| Metric | Baseline | Query v2 | Prompt v2 |
|---|---|---|---|
| Completion rate | not executed | not executed | not executed |
| Stage failure rate | not executed | not executed | not executed |
| Invalid-output rate | not executed | not executed | not executed |
| Integrity violations | not executed | not executed | not executed |
| Unsupported figures | not executed | not executed | not executed |
| Competitor recall | not executed | not executed | not executed |
| Competitors with a sourced offering | not executed | not executed | not executed |
| Market-size availability | not executed | not executed | not executed |
| Source diversity | not executed | not executed | not executed |
| Sourced share | not executed | not executed | not executed |
| Repair warnings per run | not executed | not executed | not executed |
| Grounded share (strategy) | not executed | not executed | not executed |
| Matrix consistency | not executed | not executed | not executed |
| Total seconds | not executed | not executed | not executed |
| Search-stage seconds | not executed | not executed | not executed |
| AI requests per run | not executed | not executed | not executed |
| Searches per run | not executed | not executed | not executed |

### 5.3 Rubric means

| Dimension | Baseline | Query v2 | Prompt v2 |
|---|---|---|---|
| Specificity | not executed | not executed | not executed |
| Groundedness | not executed | not executed | not executed |
| Actionability | not executed | not executed | not executed |
| Coherence | not executed | not executed | not executed |
| Honesty about uncertainty | not executed | not executed | not executed |
| Scorers and spread | not executed | not executed | not executed |

### 5.4 Adoption check

| Condition (Section 3.2) | Query v2 | Prompt v2 |
|---|---|---|
| 1. Guards equal or better; no idea worse by more than one run | not executed | not executed |
| 2. One target past its threshold | not executed | not executed |
| 3. No other target past its tolerance | not executed | not executed |
| 4. Rubric means within 0.2 | not executed | not executed |
| 5. Three pilot ideas, each in every variant | not executed | not executed |
| Same evidence as the baseline | no: each run searches again | no: each run searches again (confounding factor) |
| Result | not executed | not executed |

## 6. Default decisions

| Setting | Default now | Why | What would change it |
|---|---|---|---|
| `QUERY_PROFILE` | `v1` | No comparable baseline (T0 report Section 11.2), so no comparison has run | Section 3.2 met on the pilot, and your approval |
| `PROMPT_PROFILE` | `v1` | Same; the matrix consistency check stays behind it for the same reason | Same |
| `SEARCH_MAX_PARALLEL` | `1` (plan 12.3 says 3) | 9.7 asks for measured search-stage seconds on the baseline ideas first | Measured saving with no live rate-limit errors, and your decision (pending from T5) |
| Rate-limit retry in the search pool | not built (pool pauses only) | Section 3: no increase in retry budgets without approval | Your approval (pending from T5) |

## 7. Limitations

- No live comparison has run, so no metric value exists for any variant. Every result above is "not executed".
- Three ideas are a pilot, not the original six-idea benchmark; even a clear result would not show a general improvement.
- Prompt candidates cannot be compared on the same evidence with the existing runner, because each run searches again.
- Competitor recall needs reference names you supply (`[FOUNDER TO FILL]`).
- `usage` counts requests, not credits; Q-6's extra credits must be added by hand.
- P-3 and the 9.10 step 2 fixes wait for the baseline and your approval.
- The matrix consistency figures in Section 4.3 come from re-running code on stored fixtures. They show that the check works on real outputs, not that live outputs improve.
- Fake-backed tests prove the code paths, not live model or search behaviour.

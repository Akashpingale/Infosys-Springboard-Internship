# Milestone 2 Agents

**Project:** Development of AI Based Startup Idea Validator with Market Analysis Assistance

**Scope:** the Milestone 2 analysis agents and how they run in the pipeline. This document covers
the shared evidence rules, the Competitor Analysis Agent (Task 2), the sequential orchestration
with its UI (Task 3) and the Task 1 bug-fix phase (section 5). Validation across domains (Task 4)
and its live runs are reported in [docs/09](09_milestone2_test_report.md).

---

## 1. Status

| Agent or task | Code | Status |
|:---|:---|:---|
| Market Opportunity Agent (Task 1) | `agents/market_opportunity_agent.py`, `agents/market_size.py`, `agents/market_claims.py` | Tested with fakes, one standalone live run (`docs/test_runs_m2/dev_market_agritech_v2.txt`). Stage 3 of the full pipeline. The quality problems that run showed are fixed (section 5), and it then ran live as stage 3 of the three Task 4 runs on 2026-10-27 ([docs/09](09_milestone2_test_report.md)) |
| Competitor Analysis Agent (Task 2) | `agents/competitor_analysis_agent.py`, `agents/competitor_checks.py` | Tested with fakes. Stage 4 of the full pipeline. Ran live as stage 4 of the three Task 4 runs on 2026-10-27 ([docs/09](09_milestone2_test_report.md)) |
| Sequential orchestration and UI (Task 3) | `orchestrator.py`, `routes/idea_routes.py`, `frontend/` | Tested with fakes (section 4). `POST /api/validate?include_analysis=true` runs all four stages and the UI always asks for them. The Task 4 live runs went through these stages with `scripts/run_live_m2.py`, which calls `run_pipeline` directly; no live run through the API route or the UI with the analysis stages is recorded |
| Validation across domains (Task 4) | `data/test_ideas/`, `tests/domain_fakes.py`, `tests/test_m2_domains.py`, `scripts/run_live_m2.py`, `scripts/make_m2_report.py` | Three domains run through the integrated pipeline with fakes (92 tests), then live once each on 2026-10-27: 3 of 3 `complete`, with no integrity violations ([docs/09](09_milestone2_test_report.md)) |

---

## 2. Shared evidence rules

Both agents follow the same rules, implemented in code rather than left to the prompt.

- **Numbered evidence.** Search results become evidence items `S1`, `S2`, ... with a title, URL
  and snippet of at most 300 characters (`agents/evidence.py`). Tavily's own summary becomes `S0`.
  It has no URL, so it can support an AI interpretation but never a sourced claim.
- **Basis labels.** Every claim is `sourced`, `assumption`, `ai_interpretation` or `user_provided`.
- **Citations.** The LLM cites ids only. Code drops unknown ids, and a `sourced` claim needs at
  least one real source other than `S0`; otherwise it is downgraded.
- **Figures.** An amount counts as sourced only if a cited snippet states it with the same value,
  magnitude and unit (`agents/figures.py`). "USD 1.8 million" never matches "USD 1.8 billion".
  A count keeps its metric: "downloaded 10 million times" counts downloads, so it supports
  "10 million downloads" but never "10 million users" or "10 million farmers". A number whose
  unit word a short snippet cut off ("10 million farm...") supports nothing.
- **Untrusted text.** Idea text, the founder's words and snippets go into delimited prompt blocks
  with any prompt tags removed, and the prompt says they are data, not instructions.
- **Repair, not reject.** Each repair adds a warning. A result that still fails the integrity
  checker (`agents/integrity.py`) after every repair is rejected as a stage error.

---

## 3. Competitor Analysis Agent (Task 2)

### 3.1 Responsibilities and boundaries

The agent identifies direct, indirect and emerging competitors of the submitted idea, describes
each one from the evidence, compares them feature by feature with the idea, and proposes market
gaps and differentiation opportunities as hypotheses. It reuses the shared LLM client, structured
output helper, search function (`run_queries`), evidence builder and integrity checker. It does
not scrape pages, add a search client or change the UI, the API or the orchestrator.

### 3.2 Inputs

| Input | Source | Use |
|:---|:---|:---|
| `ExtractedIdea` | `context.idea` | Title, problem, solution, industry, customers and key features |
| `SearchBundle` | `context.search` | The four standard Milestone 1 searches |
| `IdeaSubmission` | `context.submission` | Founder-named competitors, read only from `idea_description` and `relevant_details` |
| Market result (optional) | `context.market` | Reduced by `market_context_for_competitors()` to the category, segment names, priority segment with its rationale, and trend titles |

### 3.3 Workflow

1. **Input checks.** A missing or thin idea raises `InputValidationError`. With no usable search
   result, the agent raises `InsufficientEvidenceError`. Neither case makes an LLM call or a search.
2. **Phase A, candidates.** One LLM call lists up to 8 competitors or alternatives named in the
   evidence, with evidence ids and a type, plus any the founder names (basis `user_provided`).
   Code keeps a sourced candidate only if a cited snippet or title names it, and a founder-named
   one only if the name appears in the submission text. If the call fails or its reply is
   unusable, the agent warns and runs the generic searches only. A missing LLM configuration
   stops the agent before any search credit is spent.
3. **Phase B, targeted searches.** At most `COMPETITOR_MAX_EXTRA_QUERIES` searches (default 5),
   each with `COMPETITOR_RESULTS_PER_QUERY` results (default 3):
   - `"<name> pricing features"` for the top candidates. Founder-named ones come first, then
     direct, emerging and indirect.
   - Up to two generic searches built from the solution, industry and first target customer:
     alternatives and substitutes, and emerging approaches. With candidates, they take at most
     half the room, so the default split is 3 + 2.

   A failed or empty search adds a warning. If every search fails, the agent warns once and
   continues with the original evidence.
4. **Merging.** The evidence is re-numbered `S1`, `S2`, ... and capped at `EVIDENCE_MAX_ITEMS`
   (default 12), in this order:
   - the original items that name the kept candidates;
   - the targeted results, taken in turn from each search;
   - the remaining original items.

   A page already in the evidence is not added twice, and `S0` stays the original summary.
5. **Phase C, analysis.** One LLM call writes the analysis from the idea, the compact market
   context (or "none"), the kept candidates and the merged evidence. An unusable reply is retried
   once (`utils/structured.py`); a second failure raises `LLMInvalidResponseError`.
6. **Checks in code** (section 3.5), then the integrity check.

### 3.4 Output: `CompetitorAnalysisResult`

| Field | Contents | Set by |
|:---|:---|:---|
| `competitors` | At least one `Competitor` (below) | LLM, checked in code |
| `comparison.features` | The idea's key features, then features named in competitors' key features, up to 8 | Code |
| `comparison.rows` | One row per competitor, one cell per feature: `evidence_found`, `no_evidence_found` or `unclear`, with `source_ids` | LLM, checked in code |
| `comparison.feature_coverage` | Per feature, how many competitors have `evidence_found` | Code |
| `market_gaps` | `description`, `related_features`, `basis`, `source_ids`, `confidence` (`low` or `medium`), `caveat` | LLM, checked in code |
| `differentiation_opportunities` | Labelled items | LLM, checked in code |
| `queries_used` | Every targeted query sent to the search API | Code |
| `sources` | The cited evidence items only, never `S0` | Code |
| `data_quality` | `evidence_level` and `notes` | LLM, capped in code |
| `caveats` | Always "Absence from search results does not prove a competitor or a gap does not exist." | Code |

A `Competitor` has `name` and `type` (`direct`, `indirect` or `emerging`), plus:

- `relevance_note`, and `website` (null unless the evidence supports it);
- `source_ids`, `offering`, `target_segment`, `key_features`, `value_proposition`;
- `pricing_model`, the shared `QuantEstimate`: a value or null, with a status;
- `strengths` and `weaknesses` (labelled items, each needing a source);
- `positioning` and `differentiation_vs_startup`;
- `info_completeness` (`complete`, `partial` or `minimal`), computed in code;
- `basis` (`sourced` or `user_provided`).

Schemas are in `models/schemas.py`. The LLM's reply is validated against draft models first; the
draft lacks the fields that only code sets.

### 3.5 Checks in code

- **Grounding.** A sourced competitor needs a real cited source that names it; otherwise it is
  removed. A founder-named competitor must appear in the submission text.
- **Irrelevant entries.** A competitor with no type or an empty relevance note is dropped, and a
  warning gives the count.
- **Websites.** A website is kept only if a source the competitor cites is on that domain and the
  domain carries the competitor's name, so a directory page such as an "alternatives" list is
  never taken as a company's site. The shared rule (an http or https URL on an evidence domain)
  runs first.
- **Pricing.** A sourced price must be stated in its cited snippets: the amount with the same
  value and unit, or for a price in words such as "Free", its distinctive words. Otherwise it
  becomes `estimate_needs_verification`. A price citing nothing becomes `unavailable`.
- **Duplicates.** Competitors with the same normalised name (lower case, no suffixes such as Inc,
  Ltd, Pvt or app, no spaces) or the same website domain are merged. Lists and sources are unioned,
  and the comparison rows follow the merge.
- **Strengths and weaknesses** without a real source are removed. A sourced claim whose money,
  percent or magnitude figure is not in its snippet becomes an AI interpretation.
- **Matrix.** A missing cell is `unclear`. An `evidence_found` cell without a cited source naming
  that competitor becomes `unclear`. Coverage is counted from the rows.
- **Gaps.** Confidence above `medium` is lowered, and every gap gets the fixed caveat. Related
  features not in the comparison are removed. A gap whose related features each have evidence for
  more than half of the competitors contradicts the matrix and is removed.
- **Evidence level.** With 1 or 2 usable evidence items, or only founder-named competitors, the
  level is at most `limited`, with a note.
- **No survivors.** If no competitor survives, the agent raises `InsufficientEvidenceError`.

### 3.6 Failure behaviour

| Situation | Behaviour |
|:---|:---|
| Thin or missing idea | `InputValidationError`, no calls |
| No usable search result | `InsufficientEvidenceError`, no calls |
| LLM not configured | `LLMConfigError` before any targeted search |
| Phase A fails or is unusable | Warning; generic searches only; Phase C still runs |
| A targeted search fails or finds nothing | Warning; the agent continues |
| Every targeted search fails | One warning; original evidence used |
| Phase C unusable twice | `LLMInvalidResponseError` |
| Phase C API or configuration error | The same error, unchanged |
| No competitor survives the checks | `InsufficientEvidenceError` |
| Result still fails the integrity check | `LLMInvalidResponseError` |

On any error, the agent writes nothing to the context.

### 3.7 Configuration

| Setting | Default | Used for |
|:---|:---:|:---|
| `COMPETITOR_MAX_EXTRA_QUERIES` | 5 | Most targeted searches per run |
| `COMPETITOR_RESULTS_PER_QUERY` | 3 | Results per targeted search |
| `EVIDENCE_MAX_ITEMS` | 12 | Evidence cap, shared with the market agent |
| `LLM_TIMEOUT_S` | 30 | Seconds per LLM call. A longer value, such as 90, is advisable for live runs: the market call took about 110 seconds in its live run |

Bad or non-positive values fall back to the defaults (`config.py`).

### 3.8 Running it standalone

The development script makes real API calls and needs real keys in the project root `.env`:

```powershell
python scripts/run_agent.py competitor --idea data/test_ideas/agritech.json
python scripts/run_agent.py competitor --idea data/test_ideas/agritech.json --with-market
```

It prints the following, but never keys or settings:

- the extracted idea, the standard searches, and the Phase A candidates kept (with the pages
  that name them) and dropped (with the reason);
- every targeted search with its outcome, and the merged evidence with ids, URLs and snippets;
- the JSON result, the warnings and the integrity check.

`--with-market` runs the market agent first and passes its compact context. If the market agent
fails, the competitor agent runs without it. Exit code 0 means a clean result; 1 means the run
stopped or the integrity check found violations.

A run without `--with-market` makes 3 Gemini calls (extraction, Phase A, Phase C) plus any retries,
and up to 9 Tavily searches (4 standard and up to 5 targeted).

### 3.9 Tests

```powershell
python -m pytest tests/test_competitor_analysis_agent.py tests/test_competitor_checks.py
python -m pytest
```

All tests use fakes. A fixture blocks any non-local network access, so no test calls the LLM or
Tavily. The agent's tests are in `tests/test_competitor_analysis_agent.py` and
`tests/test_competitor_checks.py`. Further tests are in `tests/test_integrity.py`,
`tests/test_m2_schemas.py` and `tests/test_run_agent.py`.

### 3.10 Known limitations

- **Live behaviour is unknown.** The agent has not run against the live APIs, so its real output
  quality is not yet known.
- **Matching is literal.** It works on words and domains, not meaning:
  - a competitor named only by a nickname is dropped;
  - a website on a domain that doesn't contain the company's name (for example a parent company's
    site) is removed;
  - a third-party snippet that describes a feature without naming the competitor leaves that cell
    `unclear`. A page on the competitor's own domain does count as naming it (section 3.11).
- **Snippets are short.** The cap is 300 characters, as Section 5.1 of the build specification
  sets. The targeted competitor searches now choose which sentences to keep (section 3.11), but
  the four standard searches still keep the first 300 characters, so a detail later on the page is
  lost there. Pages are never fetched (out of scope, Section 17).
- **Founder-named competitors** get little information unless a targeted search finds them.
- **Some prompt rules aren't enforced.** Code cannot check the competitor type, whether a
  strength's wording stays within its snippet, or which competitors are most relevant.
- **Failed Phase C still costs credits.** A rejected key or a busy provider fails Phase A and
  Phase C, but the targeted searches in between still run and use credits.

### 3.11 Bug-review phase

Reviewing the implementation found five defects, each reproduced with fakes before any change.
No competitor, fact, source or figure is invented by these fixes.

| Defect | Root cause | Fix |
|:---|:---|:---|
| Invented competitors named after an ordinary word ("Crop App", "AI") passed the grounding check, with no warning | Section 8.3's suffix list was applied when matching a name in text, so "Crop App" became "crop" and matched any snippet about crops. A two-character name also matched too easily | That suffix list governs de-duplication, so `name_key` still strips "app". When matching a name in text, only corporate suffixes are stripped, and a product word is dropped only when what remains is at least 5 characters, so "Plantix App" is still Plantix. A name needs 3 characters |
| A competitor whose only cited source was its own website was dropped as "not named in its cited sources" | Only the title and snippet were read, and a 300-character snippet often does not repeat the brand | A cited source whose domain label is the competitor's name counts as naming it. The label must equal the name, so `cropinsight.example` is not the site of a "Crop App" |
| A comparison cell citing the competitor's own page was demoted to `unclear` | The same title-and-snippet limitation | Fixed by the rule above |
| A price stated past the first 300 characters of a pricing page was downgraded to `estimate_needs_verification` | The targeted searches used the Milestone 1 snippet, which keeps the first characters | They now pass `focused_snippet`, the shared builder the market agent uses, which keeps whole sentences and prefers those stating an amount |
| A feature only a competitor has was left out of the comparison, leaving that competitor's row entirely `unclear` | Only features the model listed were added | Section 8.3 counts "features seen in competitor data", so the remaining competitor key features are appended, still capped at 8 |

`focused_snippet` moved from `agents/market_size.py` to `agents/evidence.py` so both agents share
one builder. The code is unchanged, so Task 1 behaviour is the same.

Two checks are deliberately strict and can still drop a legitimate competitor: a name matched only
by a nickname, and a website whose domain does not carry the company's name. Conflicting figures
for one competitor, such as two sources giving different prices, are not detected; Section 8 does
not ask for it, and the agent keeps the figure the model cited.

### 3.12 Integration point

The agent follows the existing `Agent` protocol (`name = "competitor_analysis"`, with
`run(context)` returning the context).

- **Writes:** `context.competitors`, plus `context.competitor_candidates` and
  `context.competitor_search`, which let the evidence be rebuilt for auditing.
- **Warnings** are prefixed `Competitor analysis:`.
- **Errors** are `AppError` subclasses, which the orchestrator records as stage errors.

Task 3 runs it as the last stage of the full pipeline, adds `competitors` to `PipelineResult` and
shows it in the UI (section 4).

---

## 4. Sequential orchestration and context passing (Task 3)

### 4.1 Stages

`orchestrator.py` keeps the Milestone 1 list `STAGES` unchanged and adds `FULL_STAGES`, the same
two stages followed by the two analysis stages. The pipeline is still one plain loop.

| # | Stage and timing key | Reads | Writes |
|:---:|:---|:---|:---|
| 1 | `extraction` | `submission` | `idea` |
| 2 | `search` | `idea` | `search` |
| 3 | `market_opportunity` | `idea`, `search` | `market` (and `market_search`) |
| 4 | `competitor_analysis` | `idea`, `search`, `submission`, compact market context | `competitors` (and the candidates and targeted searches) |

Each stage is timed under its name, plus `total`, as in Milestone 1. A skipped stage has no timing.

### 4.2 Which pipeline runs

| Call | Stages |
|:---|:---|
| `POST /api/validate` | 1 and 2, exactly as in Milestone 1 |
| `POST /api/validate?include_analysis=true` | 1 to 4. The Streamlit UI always sends this |

The full pipeline is opt-in so that existing clients, and the Milestone 1 tests that the build
specification requires to pass unmodified, still see the two-stage pipeline. Those tests check the
exact stage list, the exact warnings, four search calls per request, the timing keys and a
`complete` status with fakes that only cover extraction. Making the full pipeline the default for
every client is left for the final integration, because it changes what those tests check.

### 4.3 Context passing

The competitor stage gets the extracted idea, the standard search bundle, the submission and a
compact market context built by `market_context_for_competitors(market)`: the market category,
segment names, priority segment with its rationale, and trend titles. The full market result never
reaches the competitor prompt. When the market stage failed or was skipped, the prompt says
`Market context: none`.

### 4.4 Skip and failure rules

- **No search bundle, or no usable evidence** (no result with a URL; the search summary `S0` does
  not count): both analysis stages are skipped, each with its own warning, for example
  `Market opportunity: skipped because the web search found no usable results.` No LLM call or
  search is made.
- **The market stage fails:** the error is recorded and the competitor stage runs without market
  context.
- **The competitor stage fails:** the error is recorded and the market result is kept.
- **An unexpected exception in an analysis stage** becomes a stage error with code
  `internal_error` and the generic message "Something went wrong. Please try again." The details
  go to the server log only. In the Milestone 1 stages it is still left to the application's error
  handler, which returns 500, as before.
- Every new warning starts with its stage (`Market opportunity:` or `Competitor analysis:`), and
  every error carries its `stage`. The two Milestone 1 warnings keep their original wording.
- A failed or skipped stage leaves its field `null`. Nothing is filled in.

### 4.5 Status rules

| Situation | Status | Kept in the result |
|:---|:---:|:---|
| All four stages succeed | `complete` | everything |
| Analysis stages succeed with repair warnings | `complete` | everything, warnings listed |
| Extraction fails | `failed` | errors only |
| Search fails completely | `partial` | idea; both analysis stages skipped with warnings |
| Search runs but finds no usable evidence | `partial` | idea and search; both analysis stages skipped with warnings |
| Some standard searches fail | `partial` | everything that ran (the Milestone 1 rule) |
| Market fails, competitor succeeds | `partial` | idea, search, competitors |
| Competitor fails, market succeeds | `partial` | idea, search, market |
| Both analysis stages fail | `partial` | idea, search |

The build specification does not list the "no usable evidence" row. It is `partial` because the
analyses did not run (Section 11 of the specification gives `partial` for zero usable evidence).
The Milestone 1 pipeline still reports `complete` for searches that find nothing.

### 4.6 UI

Two sections follow the Milestone 1 sections, which are unchanged:

- **Market opportunity:** evidence level and notes, industry overview, customer demand, a market
  size table (TAM, SAM, SOM with value, status, sources and note, plus any broader-market figures
  labelled as context only), trends, segments with pain points, the priority segment and its
  risks, opportunities and limitations, sources as links, and the caveat.
- **Competitors:** evidence level and notes, competitors grouped as direct, indirect and emerging,
  a comparison table with each cell's status in words, feature coverage, gaps with their
  confidence, basis and caveat, differentiation opportunities, the targeted searches run, sources
  as links, and the caveat.

Every basis is written as text (Sourced, Assumption, AI interpretation, User provided), never shown
by colour alone. A missing section shows a short message instead. Stage errors and warnings appear
at the top, as in Milestone 1. The analysis stage names in errors and timings are shown as
"market opportunity" and "competitor analysis". The UI waits `PIPELINE_TIMEOUT_S` (default 180
seconds) for the full pipeline. The display rules live in `frontend/analysis_views.py`, which has
no Streamlit import.

### 4.7 Cost of one full run

| Service | Calls |
|:---|:---|
| Gemini | 4: extraction, market, competitor candidates and competitor analysis, plus any retries |
| Tavily | Up to 11: 4 standard, 2 market-size and up to 5 competitor searches |

The full pipeline has not run against the live APIs, so its real duration is unknown. In the one
live market run, the market call alone took about 110 seconds.

### 4.8 Tests

```powershell
python -m pytest tests/test_m2_orchestrator.py tests/test_m2_validate_route.py tests/test_m2_ui.py
```

85 tests, all with fakes (`tests/pipeline_fakes.py`):

- `test_m2_orchestrator.py`: execution order with a call spy, context passing, every status rule,
  skip rules, timings, unexpected exceptions, and runs of the real agents with clean integrity
  checks.
- `test_m2_validate_route.py`: the API with and without `include_analysis`, a bad parameter value,
  the OpenAPI schema, and URL tracing.
- `test_m2_ui.py`: the display helpers, the backend call and its timeout, and the Streamlit page
  rendered headless with Streamlit's `AppTest`, for a full, a partial, a failed and a Milestone 1
  result.

### 4.9 Known limitations

- **Live runs.** The full pipeline ran live once per Task 4 idea on 2026-10-27 with
  `gemini-3-flash-preview`: all three `complete`, 102.5 s to 159.3 s each, and no integrity
  violations in either analysis ([docs/09](09_milestone2_test_report.md), `docs/test_runs_m2/`).
  They went through `scripts/run_live_m2.py`, not the API or the UI, and were made before the
  Markdown report, the API audit fields and the backend time limit were added. Their cost was not
  recorded, and the human review checklists in docs/09 section 4 are not filled in yet.
- **The timeouts may be too short.** A full run makes four LLM calls in a row, and the default
  `LLM_TIMEOUT_S` of 30 seconds was too short for the market call in its live run. A run through
  `/api/validate?include_analysis=true` stops at 90% of `PIPELINE_TIMEOUT_S`, the time the UI
  waits: later calls get only the time left, later stages are skipped with a warning, and the
  stages that finished are returned as a `partial` result (`utils/deadline.py`). No LLM call is
  sent with less than 10 seconds left, because Gemini answers a deadline under 10 s with
  HTTP 400 `INVALID_ARGUMENT`; the step fails with the time-limit message instead.
- **Opt-in.** Clients that do not send `include_analysis=true` get the Milestone 1 result.
- **Groq fallback.** With `GROQ_API_KEY` set, one Groq attempt (`openai/gpt-oss-120b`,
  `utils/groq_client.py`) answers a Gemini rate limit or quota error, a 5xx or a timeout, under the
  same time limit and 10-second minimum; its reply goes through the same validation and checks.
  Groq is sent the strict JSON schema of the model that validates the reply (Structured Outputs),
  so it cannot answer with invalid JSON, a missing key, a null where text is required or a value
  outside an enum; lengths, counts and the "sourced needs a source" rule are still checked by
  Pydantic. Within one structured call, the repair retry after a Gemini failure goes to Groq only.
  The localhost run of 2026-10-28 showed why: in JSON object mode Groq's competitor reply broke the
  model three times, and the retry waited 28.8 s for a second Gemini 504 before Groq rejected its
  own output as invalid JSON. The fix is tested with fakes only, not yet in a live run, and Groq's
  own rate limits (8,000 tokens per minute on the base plan) may be too low for a whole run.
- **Auditing.** `PipelineResult` returns `market_search`, `competitor_candidates` and
  `competitor_search`, so the evidence each agent saw can be rebuilt from an API response alone
  with `market_evidence` and `competitor_evidence` and checked again with the integrity checkers.
  This is tested with fakes only (`tests/test_m2_audit_fields.py`). The saved live results predate
  these fields, and `scripts/run_live_m2.py` still rebuilds the evidence from the pipeline's
  context with a capture stage.
---

## 5. Task 1 bug-fix phase

The one live market run, `docs/test_runs_m2/dev_market_agritech_v2.txt`, showed seven problems.
Each was reproduced from that saved output before anything was changed; five were code defects.
No market figure, source or estimate is invented by any of these fixes.

### 5.1 What was fixed

| Problem in the live run | Root cause | Fix |
|:---|:---|:---|
| "Over 10 million downloads" was downgraded although its source says "downloaded over 10 million times" | The figure reader counted "times", not downloads, so the two could never match | `agents/figures.py` reads "downloaded / installed N times" as downloads and installs. They never equal users, customers or farmers |
| The same claim rested on a snippet ending "...10 million time..." | A unit word cut off by the 300-character snippet was read as a whole word | A clipped unit word makes the number unclear, so it supports nothing |
| A limitation was labelled sourced but added "which may conflict with or reduce the perceived need for AI suggestions" | Only amounts in sourced claims were checked, so added conclusions passed | `agents/market_claims.py` relabels a sourced claim that uses a hedge or conclusion word (may, could, likely, suggests, indicates...) none of its cited sources uses |
| A cooperatives pain point was about market access and intermediaries, not crop disease | Nothing in code checked relevance | A customer problem or pain point resting on a cited source must share a word root with the idea's title, problem, solution or features, in its own text or in that source. An off-topic one is removed |
| Plantix was credited with both 135 million and over 10 million downloads, merged into "millions of active users" | The sources disagree, and the false downgrade above hid it | Both claims keep their own figure and source, and a data-quality note lists the differing figures. Code never picks between them |
| Targeted search snippets cut off the market figures and ended mid-word | The Milestone 1 snippet keeps the first 297 characters | For the market agent's own targeted searches only, `focused_snippet` keeps whole sentences, preferring those that state an amount and use the query's market words, with `...` where text was left out |

The 300-character snippet cap itself is unchanged, as Section 5.1 of the build specification sets
it, and so are the standard searches, the Competitor Analysis Agent and the orchestrator.

### 5.2 New warnings and notes

Every repair still adds one warning, and nothing is changed silently:

- `limitations[0]: this sourced claim adds a conclusion ('may') that its cited sources do not
  state, so it is now an AI interpretation`
- `segments[1].pain_points[0]: it is not about the problem this idea solves, so it was removed`
- `data_quality: Sources give different figures for Plantix downloads: 135 million (S11), 10
  million (S9). They may differ in date or definition, so check the sources before using either.`

A segment left with no pain point gets the note "No pain point about the problem this idea solves
was found for the segment <name>", and a source cited only by a removed pain point is dropped from
that segment's citations.

### 5.3 What these checks cannot do

They compare words, not meaning, so each one errs towards caution:

- **Relevance** is judged by shared word roots. A pain point worded entirely differently from the
  idea can be removed, and only items resting on a cited source are judged at all: the founder's
  words and labelled assumptions are kept as they are.
- **Added conclusions** are found by a fixed word list. A claim that overstates its source without
  using one of those words still passes.
- **Conflicting counts** are only found when two claims name the same product and count the same
  thing. Figures in different units, or for a product named only in a snippet with no claim
  repeating the name, are not compared.
- **Focused snippets** help only the two targeted market-size searches. The standard searches still
  use the Milestone 1 snippet, so a figure beyond 300 characters there is still lost.

### 5.4 Still open

- **TAM, SAM and SOM were all unavailable** in the live run, and no cited snippet stated a figure
  for this idea's own market. Focused snippets may surface one, but that needs a live run to know.
  Section 7.2 forbids deriving or rescaling a figure, so nothing is estimated in code.
- **The run took about 110 seconds.** The targeted searches took 9.5 s of that; the first market
  LLM call hung for 89.5 s and returned HTTP 504, and the retry succeeded in 17.7 s. That is a
  provider stall against the 90-second timeout used for that session, not a code defect, so no
  change was made. A shorter `LLM_TIMEOUT_S` would fail sooner but also cut off slow healthy calls.

### 5.5 Tests

```powershell
python -m pytest tests/test_market_opportunity_agent.py tests/test_market_claims.py tests/test_figures.py tests/test_run_queries.py
```

324 tests, all with fakes. The regression tests for this phase replay the live run's own evidence
and claims from `tests/m2_fakes.py` (`LIVE_V2_*`), so each defect is pinned to the output that
showed it. Each fix was also checked by breaking it on purpose and confirming the tests fail.

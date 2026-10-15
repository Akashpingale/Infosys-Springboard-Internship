# Task 5: Integration and Pipeline Test Report

**Project:** Development of AI Based Startup Idea Validator with Market Analysis Assistance

**Scope:** Milestone 1 end-to-end flow: idea submission, LLM extraction, Tavily web search,
orchestration, and the Streamlit UI.

**Model used:** `gemini-3-flash-preview` (from `LLM_MODEL`) · **Search:** Tavily, basic depth,
3 results per query

**Run date:** 14 October 2026

---

## 1. Live runs against the real APIs

Command: `python scripts/run_live_ideas.py`. Raw evidence for each run is saved in
[`test_runs/`](test_runs) as a `.json` and a `.md` file.

| Idea | Industry | Status | Extraction OK? | Queries run | Results found | Duration | Observations |
|:---|:---|:---:|:---:|:---:|:---:|---:|:---|
| `agritech` | Agriculture / AgriTech | complete | Yes | 4 | 10 | 25.4s | Slowest run. The "Customer demand" section kept only 1 result because its other hits were duplicates already shown in earlier sections |
| `healthtech` | Healthcare / HealthTech | complete | Yes | 4 | 12 | 18.8s | Clean run, 3 results in every section |
| `fintech` | Finance / FinTech | complete | Yes | 4 | 12 | 18.2s | Fastest run. Strong, specific sources on gig-worker lending |
| `foodtech` (extra) | Food & Beverage | complete | Yes | 4 | 12 | 19.4s | Clean run. Results were broader and less specific than the other three |

**Totals:** 4 ideas, 4 industries, 4 `complete`, 0 `partial`, 0 `failed`, 0 failed queries out of 16.

Every run produced the five required extracted fields plus a title, 2 or 3 target customers and 5
key features, and a Tavily summary in all 4 sections. Across the 46 results collected there were no
duplicate URLs within a run, no entry missing a link or text, and no snippet over the 300-character
limit.

### Per-stage timings

| Idea | Extraction | Search | Total |
|:---|---:|---:|---:|
| `agritech` | 7.5s | 17.9s | 25.4s |
| `healthtech` | 5.4s | 13.4s | 18.8s |
| `fintech` | 5.8s | 12.4s | 18.2s |
| `foodtech` | 6.0s | 13.5s | 19.4s |

Search costs roughly twice as much time as extraction, because four Tavily calls run one after the
other. A typical run is about 20 seconds, which the UI covers with a spinner inside its 90-second
timeout.

---

## 2. Automated tests

Command: `python -m pytest`. Result: **293 passed, 1 warning** in 3.5 seconds.

| File | Tests | What it covers |
|:---|:---:|:---|
| `test_integration.py` | 20 | Each test idea through `POST /api/validate` with the LLM and Tavily mocked; four distinct queries per idea; the response always validating as `PipelineResult` |
| `test_failure_modes.py` | 31 | One test per row of the error-handling matrix, plus the hardening checks in section 4 below |
| `test_frontend_helpers.py` | 34 | Form validation, the "Other" industry, and all nine backend outcomes the UI must explain |
| `test_validate_route.py` | 13 | The pipeline route: complete, partial, failed, invalid input, generic 500 |
| `test_orchestrator.py` | 17 | Status rules, per-stage timings, context hand-off, extensibility |
| `test_web_search_agent.py` | 26 | Query generation, normalization, de-duplication, partial failure |
| `test_search_client.py` | 20 | Tavily request shape and 11 failure modes |
| `test_extraction_agent.py` | 19 | Valid, fenced, invalid-then-valid, invalid twice, prompt injection |
| `test_llm_client.py` | 44 | Error translation, bounded retry, client lifecycle |
| `test_schemas.py` | 22 | Limits, trimming, extra keys, boundary lengths |
| Others | 47 | Config, errors, app error handling, routes, fixtures |

No test touches the network: a fixture blocks any non-local socket, and every test runs with fake
keys. The one warning is Starlette reporting that its test client will want `httpx2` in future; it
does not affect the application.

---

## 3. Failure modes verified

Each row of the error-handling matrix has a test in `tests/test_failure_modes.py`.

| Situation | User sees | Pipeline status | Verified |
|:---|:---|:---:|:---:|
| Empty or whitespace-only field | "Please enter your idea description." | not run | Yes |
| Description too short or too long | "Please use at least 30 characters…" / "…2000 characters or fewer" | not run | Yes |
| Industry "Other" without detail | "Please type the industry you mean." | not run | Yes |
| Missing `LLM_API_KEY` or `LLM_MODEL` | "The AI service is not configured." | failed | Yes |
| LLM timeout | "The AI service took too long to reply." | failed | Yes |
| LLM 429 | "…rate limit or quota was reached." | failed | Yes |
| LLM 401 | "…rejected the API key. Check LLM_API_KEY in .env." | failed | Yes |
| LLM 5xx | "The AI service is busy right now." | failed | Yes |
| LLM returns non-JSON | "Could not understand the AI reply." | failed | Yes |
| LLM returns JSON with a missing field or an extra key | same | failed | Yes |
| LLM returns an empty string | same | failed | Yes |
| Missing `TAVILY_API_KEY` | "Web search is not configured: TAVILY_API_KEY is not set." | partial | Yes |
| Tavily 401 / 429 / timeout / 5xx / unreachable | A different readable message for each | partial | Yes |
| Tavily returns a non-JSON body | "…sent a reply that could not be read." | partial | Yes |
| Tavily returns no results | "No live results found for this query." | complete, section empty | Yes |
| One of four queries fails | That section only shows the reason | partial | Yes |
| Backend not running | "Cannot reach the server. Start it with `python app.py`…" | n/a | Yes |
| Unexpected exception anywhere | "Something went wrong. Please try again." | failed | Yes |

A stack trace never reaches the user. Every test asserts the response contains no traceback and no
key value.

---

## 4. Hardening review

| Check | Result |
|:---|:---|
| Very long but legal input (2000-character description, 1500-character details) | Accepted, `complete`. Verified live with a maximum-length description: 21.7s, 12 results |
| Non-English input (Hindi) | Accepted live. The LLM returned a correct English structured idea and all 4 searches succeeded |
| Emoji and special characters | Accepted. Emoji, quotes, angle brackets and a `<script>` tag are treated as data; punctuation noise is stripped before queries are built |
| A search returning zero results | Each section reports "No live results found for this query." instead of failing |
| An LLM returning an empty string | Retried once, then reported as an unreadable reply |
| Queries never sent empty | Verified with a punctuation-only extracted idea; all 4 queries were still non-empty |
| Repeated submission | A second submission starts from a clean context and inherits nothing from the first |

**Duplicate submit while a run is in progress:** Streamlit runs one script per session at a time, so
pressing the button again restarts the script and the earlier HTTP response is discarded rather than
being shown. The result lives in `st.session_state`, which is cleared before each attempt, so a
stale result is never mixed with a new one. This was verified by two sequential submissions in an
automated check; the race of clicking mid-request was reasoned about rather than measured, and is
the one item here not covered by a test.

---

## 5. Problems found during testing and what was fixed

| Problem | Where it came from | Fix |
|:---|:---|:---|
| Every real LLM call failed with "Cannot send a request, as the client has been closed" | The Gemini client was created inline, so Python collected it mid-request and closed its connection | The client is held in a variable for the whole call and closed explicitly afterwards. Three regression tests use a weak reference plus a forced garbage collection to reproduce the original failure |
| A real 503 was reported as a vague "AI service is having problems" with no diagnosable cause | The error handler logged nothing about the provider's reply | The cause is now logged as class plus HTTP status, and each cause has its own message. A connection check script was added |
| `gemini-3.6-flash` returned 503 on every attempt | Provider capacity, not the code | `LLM_MODEL` was changed to `gemini-3-flash-preview`. A short bounded retry (two retries, 1s then 3s) now recovers from transient 5xx. This fired during a live run and the retry succeeded |
| Documents referenced `.gitignore`, `.env.example` and `05_sample_output.md`, none of which existed | Week 1 documentation ran ahead of the repository | All three were created, and the paths in doc 05 were corrected |
| Agile documents pointed at `scripts/web_search/` and `docs/task4_wireframe.png` | The folder layout was tidied after those documents were written | Paths corrected to `src/web_search/` and `docs/assets/` |

---

## 6. Honest limitations

- **The agritech run returned 10 results, not 12.** De-duplication dropped two hits from the
  "Customer demand" section because the same URLs had already appeared earlier. That is the intended
  behaviour, but it means a narrow idea can leave one section thin.
- **One query repeats words.** The demand query is built as
  `{target customer} {short problem} …`, so when both begin with the same phrase the query reads
  "Small farmers in India Small farmers in India lose crops…". Results were still good, and the
  template matches the specification, so it was left alone.
- **The `foodtech` results were noticeably broader** than the other three. A generic consumer idea
  pulls generic market pages, where the fintech idea pulled specific lending sources.
- **Search quality is not scored.** The pipeline reports how many results it found, not how useful
  they are. Judging usefulness is still a human step.
- **One provider, one model.** All live runs used a single Gemini model. A different model may parse
  the prompt differently, though the schema check would catch an unusable reply.
- **Timings were measured on one machine and one network** on a single day, so treat the 20-second
  figure as indicative.
- **The UI was verified structurally, not visually.** An automated check drove the real Streamlit
  script and confirmed the form, the validation messages, the status banner, four research expanders
  and two download buttons. Screenshots and the look on a narrow window remain a manual step.

---

## 7. Reproducing this report

```bash
python -m pytest                      # 293 automated tests, no network
python scripts/run_live_ideas.py      # 4 live runs, needs real keys in .env
```

The live runner prints one line per idea and writes the JSON and Markdown evidence into
[`test_runs/`](test_runs). Those files were scanned for secrets before being saved; they contain no
key, no key name and no authorization header.

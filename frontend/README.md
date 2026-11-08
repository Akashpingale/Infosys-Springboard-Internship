# Idea Submission UI (Streamlit)

The founder-facing form for the AI Startup Idea Validator. It collects a startup idea, checks the
input, sends it to the FastAPI backend, and shows the structured idea plus the market and
competitor research, followed by the Milestone 2 market opportunity and competitor analysis.

## Files

| File | Purpose |
|---|---|
| `app.py` | The Streamlit page: form, field errors, spinner, result display |
| `api_client.py` | Pure helpers with no Streamlit import: form validation and the backend call |
| `analysis_views.py` | Milestone 2: pure helpers that turn the market and competitor results into labelled lines and table rows |

Validation limits and the industry list are imported from `models/schemas.py`, so no number or
option is repeated here. The Markdown download reuses `render_markdown` from the Web Search Agent,
so the UI and the reports share one format.

## Running it

Two terminals, both from the **project root** with the virtual environment active.

Terminal 1, the backend:

```bash
python app.py
```

Terminal 2, the UI:

```bash
streamlit run frontend/app.py
```

Then open <http://localhost:8501>. The backend must be running first; the UI reads its address from
`BACKEND_URL` in `.env` and falls back to `http://localhost:8000`.

Keys live only in the project root `.env` and are read by the backend. The UI never displays them.

## Using the form

| Field | Required | Notes |
|---|:---:|---|
| Your startup idea | Yes | Two or three lines. Must meet the shared length and word minimums |
| Industry | Yes | Chosen from the shared list |
| If Other, specify | Only when `Other` is chosen | Always visible, because a dropdown inside a form does not update until you submit |
| Who are your target customers? | Yes | A short phrase |
| Anything else we should know? | No | Location, stage, budget, competitors you know of |

Press **Validate my idea**. Problems are listed under the form in plain language and nothing is
sent to the server until they are fixed. **Clear form** empties the fields and the last result.

## Reading the result

A banner shows the outcome as an icon **and** words, never colour alone:

| Status | Meaning |
|---|---|
| Complete | The idea was structured, all four searches worked, and both analyses ran |
| Partial | The idea is ready, but some of the research or an analysis is missing. A warning or error explains what |
| Failed | The idea could not be structured, so there is nothing to research |

Below the banner: the structured idea, then one expander per research section with the summary and
numbered links. Then two Milestone 2 sections:

- **Market opportunity:** industry overview, customer demand, a market size table with each
  figure's status in words, trends, segments with pain points, the priority segment, opportunities
  and limitations, and the cited sources as links.
- **Competitors:** direct, indirect and emerging competitors, a feature comparison table, possible
  market gaps with their caveat, differentiation opportunities, the searches run, and the cited
  sources as links.

Every claim shows its basis in words (Sourced, Assumption, AI interpretation, User provided). If an
analysis did not run or failed, its section says so instead. Last comes an expander holding the
raw JSON and two download buttons: the JSON, and a Markdown report. The report is
`validation_report.md`, covering the idea, the research and both analyses, when at least one
analysis produced a result; otherwise it is the Milestone 1 research report, `market_research.md`.

The UI asks the backend for the full pipeline (`include_analysis=true`) and waits up to
`PIPELINE_TIMEOUT_S` (180 seconds by default) for it.

## Troubleshooting

| Message | What to do |
|---|---|
| Cannot reach the server. Start it with `python app.py` | Start the backend in another terminal |
| The server took too long to reply | The AI or search service is slow, or the run took longer than `PIPELINE_TIMEOUT_S`. Try again, or raise `PIPELINE_TIMEOUT_S` in the root `.env` |
| The AI service is not configured | Set `LLM_API_KEY` and `LLM_MODEL` in the root `.env` |
| The AI service is busy right now | Gemini returned a temporary error. Wait a minute and retry |
| Web search is not configured | Set `TAVILY_API_KEY` in the root `.env` |

## Tests

The pure helpers are covered by `tests/test_frontend_helpers.py` and, for Milestone 2,
`tests/test_m2_ui.py`:

```bash
python -m pytest tests/test_frontend_helpers.py tests/test_m2_ui.py
```

`tests/test_m2_ui.py` also renders the page headless with Streamlit's `AppTest` for a full, a
partial, a failed and a Milestone 1 result, so the two new sections are checked automatically. The
rest of the page is still checked by hand.

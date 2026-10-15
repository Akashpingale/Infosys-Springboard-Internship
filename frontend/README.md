# Idea Submission UI (Streamlit)

The founder-facing form for the AI Startup Idea Validator. It collects a startup idea, checks the
input, sends it to the FastAPI backend, and shows the structured idea plus the market and
competitor research.

## Files

| File | Purpose |
|---|---|
| `app.py` | The Streamlit page: form, field errors, spinner, result display |
| `api_client.py` | Pure helpers with no Streamlit import: form validation and the backend call |

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
| Complete | The idea was structured and all four searches returned results |
| Partial | The idea is ready, but some or all of the research is missing. A warning explains what |
| Failed | The idea could not be structured, so there is nothing to research |

Below the banner: the structured idea, then one expander per research section with the summary and
numbered links, then an expander holding the raw JSON and two download buttons (JSON and a Markdown
report).

## Troubleshooting

| Message | What to do |
|---|---|
| Cannot reach the server. Start it with `python app.py` | Start the backend in another terminal |
| The server took too long to reply | The AI or search service is slow. Try again |
| The AI service is not configured | Set `LLM_API_KEY` and `LLM_MODEL` in the root `.env` |
| The AI service is busy right now | Gemini returned a temporary error. Wait a minute and retry |
| Web search is not configured | Set `TAVILY_API_KEY` in the root `.env` |

## Tests

The pure helpers are covered by `tests/test_frontend_helpers.py`:

```bash
python -m pytest tests/test_frontend_helpers.py
```

The page itself is checked by hand, as the test strategy in the build specification requires.

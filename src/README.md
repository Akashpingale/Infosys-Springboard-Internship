# AI Startup Idea Validator: Source Code

This folder holds the source code for the project. Each module lives in its own sub-folder.

## Modules

| Folder | Task | Status |
|---|---|---|
| `web_search/` | Task 5: Web Search API integration (Tavily) | Done |

## Task 5: Quick Start

```bash
cd src/web_search
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python search_test.py
```

On macOS or Linux, use `source venv/bin/activate` and `cp .env.example .env`.

Open `.env` and replace the placeholder with your Tavily API key.

Run with your own idea:

```bash
python search_test.py --idea "AI resume analyzer for college students"
```

Options:

| Option | Default | Meaning |
|---|---|---|
| `--idea` | AI crop disease detection app | Startup idea to research |
| `--max-results` | 3 | Results per query |
| `--depth` | basic | `basic` or `advanced` search |

Results are printed in the terminal and saved to `web_search/output/`.

Full documentation: [docs/05_web_search_api.md](../docs/05_web_search_api.md)

# Task 5: Explore Web Search API Integration

**Project:** AI Startup Idea Validator

**Milestone:** 1

**Author:** Akash Pingale

**Code location:** `src/web_search/`

---

## 1. Objective

Learn how a web search API works and use it to get live market and competitor information for a startup idea.

| Requirement | Where it is covered |
|---|---|
| Understand the purpose of a web search API | Section 2 |
| Explore Tavily or an equivalent API | Sections 3 and 4 |
| Get an API key and make a test request | Sections 5 and 6 |
| Show sample results for one startup idea in a readable format | Sections 7 and 8 |

---

## 2. Purpose of a Web Search API

A web search API lets a program search the internet and get results as structured data (JSON). The program does not need to open a browser or scrape pages.

### Why this project needs it

A Large Language Model (LLM) only knows what it learned during training. It does not know today's market size, new competitors, or recent funding. If the validator uses only the LLM, its answers can be old or invented.

A web search API fixes this:

- The **Web Search Agent** searches the web for the startup idea.
- The search results are passed to the other agents as context.
- The Market Analysis, Competitor Analysis, and SWOT agents then reason over real, current data.

This approach is called **grounding**. It makes the final validation report more accurate and traceable, because every claim can point to a source URL.

### Where it fits in the pipeline

```
Founder idea (2-3 lines)
        |
        v
Web Search Agent  <-- Task 5 (this task)
        |
        v
Market Analysis Agent -> Competitor Agent -> SWOT and Risk Agent -> MVP Agent -> Report Agent
```

---

## 3. About Tavily

Tavily is a search API built for AI agents and LLM applications. A normal search engine returns links meant for humans. Tavily returns clean text snippets, a relevance score, and an optional short AI answer, which are easy for an LLM to use.

### Main features used in this task

| Feature | What it does |
|---|---|
| `query` | The search text |
| `search_depth` | `basic` is faster. `advanced` gives deeper results and uses more credits |
| `max_results` | Number of results to return |
| `include_answer` | Adds a short AI-written summary of the results |

### Response structure

```json
{
  "query": "...",
  "answer": "short summary",
  "results": [
    {
      "title": "Page title",
      "url": "https://...",
      "content": "Relevant text from the page",
      "score": 0.87
    }
  ],
  "response_time": 1.2
}
```

---

## 4. Comparison with Other Search APIs

| API | Built for AI agents | Returns page content | Notes |
|---|---|---|---|
| **Tavily** | Yes | Yes (clean snippets) | Simple API, free tier, easy LangGraph integration |
| SerpAPI / Serper | No | No (links and snippets) | Returns Google results as JSON |
| Brave Search API | No | Snippets | Independent search index |
| Exa | Yes | Yes | Semantic (meaning-based) search |

**Choice: Tavily.** It returns ready-to-use content, needs only one HTTP request, and works well with the multi-agent tools planned for this project. Pricing and free-tier limits change, so check the Tavily pricing page before relying on a limit.

---

## 5. Getting an API Key

1. Go to [tavily.com](https://tavily.com) and click **Sign Up** (or open [app.tavily.com](https://app.tavily.com)).
2. Create an account with email or Google.
3. Open the dashboard. Your API key is shown there. It starts with `tvly-`.
4. Copy the key.

### Keeping the key safe

- Save it only in a `.env` file.
- `.env` is listed in `.gitignore`, so it is never pushed to GitHub.
- The repository contains `.env.example`, which has a placeholder, not the real key.
- If a key is ever pushed by mistake, delete it in the dashboard and create a new one.

---

## 6. Project Setup

### Folder structure

```
Infosys-Springboard-Internship/
|-- .gitignore
|-- docs/
|   |-- 05_web_search_api.md
|   `-- 05_sample_output.md
`-- src/
    |-- README.md
    `-- web_search/
        |-- .env.example
        |-- requirements.txt
        |-- search_test.py
        `-- output/
            |-- search_results.json
            |-- search_results.md
            `-- screenshots/
```

### File roles

| File | Purpose |
|---|---|
| `search_test.py` | Runs the test: sends requests, prints and saves results |
| `requirements.txt` | Python packages needed |
| `.env.example` | Template showing where to put the API key |
| `.gitignore` | Stops `.env`, `venv/`, and output files from being pushed |
| `src/README.md` | Quick-start instructions |
| `docs/05_web_search_api.md` | This document |

### Installation

Windows:

```bash
cd src/web_search
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

macOS or Linux:

```bash
cd src/web_search
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set:

```
TAVILY_API_KEY=your_tavily_api_key_here
```

### Packages

| Package | Why |
|---|---|
| `requests` | Sends the HTTP request to Tavily |
| `python-dotenv` | Loads the API key from `.env` |

---

## 7. How the Code Works

`search_test.py` follows these steps:

1. Load the API key from `.env`. Stop with a clear message if it is missing.
2. Take the startup idea from the `--idea` option, or use the default idea.
3. Build three queries from the idea:
   - **Market size and trends:** how big the market is and where it is going
   - **Competitors:** who already offers something similar
   - **Customer demand:** what problems customers have
4. Send each query to `https://api.tavily.com/search` as a POST request. The API key goes in the `Authorization: Bearer` header.
5. Format the answer and results into readable text.
6. Print the text and save it to `output/search_results.md`. The raw JSON is saved to `output/search_results.json`.

### Basic test request

This is the core of the integration. The same request works from any language.

```python
import requests

response = requests.post(
    "https://api.tavily.com/search",
    headers={"Authorization": "Bearer tvly-your-key"},
    json={"query": "AI crop disease detection market size", "max_results": 3, "include_answer": True},
    timeout=30,
)
print(response.json())
```

### Error handling

| Situation | What the script does |
|---|---|
| Missing key | Exits with a message to create `.env` |
| HTTP 401 | Exits with an "invalid API key" message |
| HTTP 429 | Exits with a rate-limit or credit-limit message |
| Other errors | Raises the HTTP error |

---

## 8. Running the Test

```bash
python search_test.py
```

With another idea:

```bash
python search_test.py --idea "AI resume analyzer for college students"
```

With deeper search and more results:

```bash
python search_test.py --depth advanced --max-results 5
```

### Sample output

This is real output from running `python search_test.py` with the default idea: **AI crop disease detection app for farmers in India**. The full file is saved as [05_sample_output.md](05_sample_output.md).

```
# Web Search Results: AI crop disease detection app for farmers in India
Generated: 2026-10-11 22:16

## Market size and trends
Query: AI crop disease detection app for farmers in India market size growth trends

Summary: The AI crop disease detection app market in India is projected to grow significantly, with a Compound AnnualGrowth Rate (CAGR) of 20.4% through 2036, driven by government digital agriculture programs and smallholder farmer productivity improvement initiatives. The market is expanding due to the deployment of AI-based crop monitoring and disease detection technologies, supported by India's...

1. AI-Based Crop Disease Detection Market Size, Share & Forecast Report 2025 to 2034 | Dataintelo (relevance 0.89)
   https://dataintelo.com/report/ai-based-crop-disease-detection-market
   Asia Pacific commanded the largest revenue share of the global AI-based crop disease detection market in 2025, accounting for $651.6 million, equivalent to a 36.2% share, reflecting the region's vast agricultural...

2. Explore the Global Ai In Agriculture Market — analysis of key trends, regional growth, top players, and a 10-year forecast from 2026 to 2036. (relevance 0.84)
   https://www.futuremarketinsights.com/reports/ai-in-agriculture-market
   India is growing at 20.4% CAGR through 2036, driven by government digital agriculture programs reaching millions of smallholder farmers. Mobile-first AI advisory services are adapting precision agriculture concepts to...

3. AI Crop Disease Detection App Development Guide 2026 (relevance 0.76)
   https://technobrains.io/crop-disease-detection-app-development-guide
   Farmers need better ways to identify crop diseases, pests, and nutrient deficiencies because their current methodsfail to detect problems until they spread. This app helps farmers minimize crop losses while enabling...

## Competitors
Query: AI crop disease detection app for farmers in India competitors alternatives startups

Summary: The sources mention several AI crop disease detection app competitors and alternatives for farmers in India.Key competitors to Agrio include Plantix, Doktar, and Fermata. DeHaat's top competitors are Grand Farm, BigHaat, and WeGro. Other notable startups using AI for crop disease detection include Map My Crop, FarmAir, Cropin, and AgriDoot. These companies leverage AI, image recognition,...

1. How Indian agritech startups use AI to fight crop diseases | Pooja Malik posted on the topic | LinkedIn (relevance0.72)
   https://www.linkedin.com/posts/pooja-malik-9bb6751a0_these-agri-startups-are-using-ai-to-predict-activity-7371899268699193345-kM_M
   advancements in agricultural automation. 𝐊𝐞𝐲-𝐩𝐥𝐚𝐲𝐞𝐫𝐬: John Deere | Trimble Inc. | AGCO Corporation | CNH | Kubota Corporation | Yanmar | CLAAS | Topcon | Raven Industries | AgJunction | John Deere | Ag Leader...

2. Top Agrio Alternatives, Competitors (relevance 0.67)
   https://www.cbinsights.com/company/agrio/alternatives-competitors
   Map My Crop specializes in agricultural technology, focusing on precision agriculture through advanced geospatial analytics. The company offers a suite of products, including a crop monitoring platform that utilizes...

3. Top DeHaat Alternatives, Competitors (relevance 0.67)
   https://www.cbinsights.com/company/dehaat/alternatives-competitors
   Technology Vendors Recent Research Newsletter Media Support Login CB Insights DeHaat company logo # DeHaat agrevolution.in ## DeHaat's alternatives and competitors See how DeHaatcompares to similar products. DeHaat's...

## Customer demand
Query: AI crop disease detection app for farmers in India customer problems demand

Summary: Farmers in India demand better ways to identify crop diseases, pests, and nutrient deficiencies due to the failure of current methods to detect problems early. The 2026 report projects a significant expansion in the global AI in agriculture market, highlighting the growing demand for AI-based agricultural technology. Plantix, which has been downloaded 135 million times worldwide and serves...

1. AI Crop Disease Detection App Development Guide 2026 (relevance 0.70)
   https://technobrains.io/crop-disease-detection-app-development-guide
   Farmers need better ways to identify crop diseases, pests, and nutrient deficiencies because their current methodsfail to detect problems until they spread. This app helps farmers minimize crop losses while enabling...

2. Detecting and managing crop pests and diseases with AI: Insights from Plantix | Mobile for Development (relevance 0.67)
   https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/programme/agritech/detecting-and-managing-crop-pests-and-diseases-with-ai-insights-from-plantix
   Plantix has been downloaded 135 million times worldwide and is serving nearly 10 million farmers annually. While India has been the primary focus, Plantix is planning to expand further into African and Southeast Asian...

3. AI-Based Crop Disease Detection Market Size, Share & Forecast Report 2025 to 2034 | Dataintelo (relevance 0.66)
   https://dataintelo.com/report/ai-based-crop-disease-detection-market
   China's Ministry of Agriculture and Rural Affairs having incorporated AI diagnostics into its Smart Agriculture 2025 action plan, while India's government has rolled out the Digital Agriculture Mission with AI-based...
```

### What the results show

| Query | What it returned |
|---|---|
| Market size and trends | Reports saying the Indian market is growing at about 20.4% CAGR through 2036, and Asia Pacific holding the largest share of the global market in 2025 |
| Competitors | Existing players such as Plantix, Agrio, DeHaat, Map My Crop and Cropin |
| Customer demand | Farmers need earlier detection of diseases and pests, and Plantix reports 135 million downloads worldwide |

### Observations

- Relevance scores range from 0.66 to 0.89, so the top results match the idea well.
- Each result has a source URL, so every claim can be traced back and cited in the final report.
- Some results are weaker. For example, one LinkedIn post lists farm machinery makers, which is not a direct competitor. Later agents should use the relevance score to filter results.
- The figures come from third-party market reports. They must be checked against the original source before they go into a final report.

---

## 9. What I Learned

- A web search API gives an AI system live data, so its answers are not limited to training data.
- Tavily returns clean content and relevance scores, which is better suited to LLM agents than plain links.
- A search call is one authenticated POST request with a JSON body.
- API keys belong in `.env`, never in the code or in GitHub.
- Query wording matters. Separate queries for market, competitors, and demand give more focused results than one broad query.

---

## 10. How This Connects to Later Tasks

| Later task | Use of this work |
|---|---|
| Web Search Agent | Wrap `search()` as an agent tool, so the agent can run queries automatically |
| Market Analysis Agent | Receives the "Market size and trends" results as context |
| Competitor Analysis Agent | Receives the "Competitors" results as context |
| Report Generation Agent | Uses source URLs as references in the final report |

Planned improvements: let an LLM write the search queries from the founder's idea, remove duplicate results, and limit results to recent dates.

---

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `TAVILY_API_KEY not found` | Create `.env` from `.env.example` and add the key |
| `Invalid API key` | Copy the key again from the dashboard. Check for extra spaces |
| `Rate limit or credit limit reached` | Wait, or check your remaining credits in the dashboard |
| `ModuleNotFoundError` | Activate the virtual environment and run `pip install -r requirements.txt` |
| Timeout | Check your internet connection and run again |

---

## 12. Task Checklist

- [x] Understood the purpose of a web search API
- [x] Explored Tavily and compared it with alternatives
- [x] Documented how to get an API key
- [x] Wrote a basic test request
- [x] Displayed search results for one startup idea in a readable format
- [x] Added documentation, setup files, and key protection
- [x] Ran the script with my own API key and added the real output to Section 8

---

## References

- Tavily documentation: https://docs.tavily.com
- Tavily dashboard: https://app.tavily.com


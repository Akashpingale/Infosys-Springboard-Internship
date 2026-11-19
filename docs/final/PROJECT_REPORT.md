# Project report (source)

**AI Based Startup Idea Validator with Market Analysis Assistance**

Infosys Springboard internship. This Markdown file is the source of the project report. Kiro drafted the factual chapters from the repository and its documents; the founder writes the personal chapters, which are marked `[FOUNDER TO FILL]`, and checks every chapter before submission. Conversion to Word or PDF: `docs/final/DEMO_RUNBOOK.md`, section 5.

Rules followed in this draft: every number is measured and names its source, or says "not executed"; no date, hour, sign-off, feedback or contribution is invented.

---

## Title page

[FOUNDER TO FILL: title page in the institution's format: project title, names, roll numbers, institution, mentor, month and year.]

## Certificate

[FOUNDER TO FILL]

## Acknowledgement

[FOUNDER TO FILL]

## Abstract

Founders often commit time and money to an idea before checking its market, its competitors and its risks. This project builds a multi-agent system that takes a startup idea written in two or three lines and produces a structured, cited validation. An Idea Extraction Agent turns the text into a structured idea that the founder reviews. A Web Search Agent gathers market, competitor, demand and funding evidence through the Tavily API. A Market Opportunity Agent and a Competitor Analysis Agent analyse that evidence and cite numbered sources, and code checks every citation, figure and URL. Three strategy agents build a SWOT and risk register, an MVP feature plan and a go-to-market plan from a numbered digest of the findings. A Startup Advisor answers questions about one finished validation, and a Report Generation Agent compiles everything into a 16-section report with a bibliography, 12 consistency checks and PDF, Markdown and JSON downloads. Every point is labelled Sourced, AI interpretation, From your idea or Assumption, and the system gives no viability score.

The backend is Python with FastAPI and Pydantic, with Gemini as the language model and Groq as a fallback; the interfaces are a Streamlit app and a React application. With fake providers, 2956 backend tests, 552 front-end tests and 369 browser tests passed on 18 November 2026 (`docs/15_final_test_report.md`). The Milestone 4 live checks, the PDF review with the production fonts and the optimisation comparison were not executed, so this report makes no claim about live accuracy or measured improvement.

## 1. Introduction and problem statement

Many people have startup ideas but do not know whether they can become businesses. Before investing, they need to understand customer needs, market demand, competitors, costs and risks (`docs/01_project_understanding.md`, section 1). Startup validation checks whether an idea solves a real problem for real customers; it reduces uncertainty and does not guarantee success (section 3 of the same document).

The project's problem statement: given a startup idea in two or three lines, produce a structured startup validation report using live web search and language-model reasoning (`docs/agile/README.md`, section 1).

## 2. Objectives and scope

Objectives (`docs/01`, section 2): analyse ideas with AI; collect current market and competitor information from the web; identify target customers and opportunities; analyse strengths, weaknesses, opportunities and threats; identify risks; recommend the first product features; suggest a go-to-market strategy; generate a structured validation report.

| Milestone | Scope | Where documented |
|---|---|---|
| M1 (Weeks 1 to 2) | Study of validation frameworks, multi-agent design and search APIs; architecture; idea submission and LLM structuring; Web Search Agent | `docs/01` to `docs/07` |
| M2 | Market Opportunity Agent, Competitor Analysis Agent, sequential orchestration, validation on three domains | `docs/08`, `docs/09` |
| UI upgrade | React interface on additive API routes, with history, citations, sources and accessibility checks | `docs/10` |
| M3 | SWOT and Risk, MVP Recommendation and Go-to-Market agents; strategy on a saved run; Startup Advisor | `docs/11`, `docs/12` |
| M4 | Report Generation Agent; end-to-end testing; optimisation of queries, prompts, reasoning and accuracy; documentation and demonstration | `docs/13` to `docs/15`, `docs/final/` |

Out of scope: user accounts, deployment, a viability score.

**Verified Agile facts** (`docs/agile/`, read only): the internship runs 9 weeks of 5 working days (45 days) in 1-week Scrum sprints. Sprint 1 (Week 1) planned 5 stories and completed 5. Sprint 2 (Week 2) planned 7 stories; its completion is not recorded there. The Agile documents cover Weeks 1 and 2 only; Weeks 3 to 9 say "To be planned". The team members recorded there are Akash Pingale and Prathamesh Shinde, with "add remaining members"; the mentor contact recorded is Subramanyam. The Sprint 1 retrospective lists the action "the committed Tavily key must be revoked and replaced" as Open. Sprints 3 to 9: [FOUNDER TO FILL].

## 3. Study of frameworks and tools

**Startup validation.** The validation concepts used throughout (market demand, target customers, competition, the value proposition, SWOT, risks, the MVP and go-to-market) are set out in `docs/01`, sections 4 to 9, with the worked example "SmartBite".

**Multi-agent systems.** `docs/02` defines AI agents, large language models and multi-agent systems, and assigns six agent roles. Its stated benefits are task specialisation, modularity, evidence-based research and structured reporting. Its stated limitations shaped the design: LLMs can produce unsupported statements, search results can be incomplete or biased, market-size estimates must not be shown as facts without evidence, and the report should support decisions rather than guarantee success (`docs/02`, sections 8 and 9).

**Architecture.** `docs/03` designs the user interface, backend, LLM, web search API, multi-agent pipeline, data storage, information flow, final report and error handling.

**Idea submission and structuring.** `docs/04` specifies the submission wireframe, the input fields and the conversion of free text into a structured object with an LLM, with a sample output.

**Web search API.** `docs/05` compares Tavily, SerpAPI or Serper, Brave Search and Exa, and chooses Tavily because it returns ready-to-use content in one HTTP request and is built for AI agents (`docs/05`, section 4).

**Tools used in the implementation.**

| Layer | Tool | Why |
|---|---|---|
| Backend | Python 3.11, FastAPI, Pydantic 2 | Typed models validate every input and every model reply |
| Language model | Gemini through the `google-genai` SDK; Groq (`openai/gpt-oss-120b`) as fallback over plain HTTPS | Structured JSON replies; a second provider for quota errors |
| Search | Tavily | See above |
| Storage | SQLite, standard library | Local run history with no extra service |
| PDF | ReportLab 5.1.0 | Pure Python, deterministic output (`docs/13`, section 8) |
| Interfaces | Streamlit; React, TypeScript, Vite, TanStack Query, Radix, Tailwind | The original form, and the full interface with history, strategy, Advisor and report |
| Tests | pytest, pypdf; Vitest, Testing Library, MSW; Playwright with axe | Fakes only; no test calls a provider |

## 4. System design

The architecture, the pipeline diagram, the evidence discipline, the run lifecycle and the report pipeline are in `docs/final/TECHNICAL_DOCUMENTATION.md`, section 2. The key design decisions:

1. **One job per agent.** Seven pipeline stages (extraction, web search, market, competitors, SWOT and risk, MVP, go-to-market), the Advisor and the report agent, each with its own input and output model (TECHNICAL_DOCUMENTATION, section 5).
2. **Evidence discipline.** Search results are numbered; the model cites by number; code checks every citation, URL, figure and unit and removes unsupported claims. Every point carries a basis label. Strategy points and the report summary are never labelled Sourced.
3. **Code decides what can be computed.** Severity, scores, ranks, the first-release cut, channel order, the positioning sentence, the bibliography numbering and the 12 report consistency checks are computed in code, not by the model.
4. **Partial results instead of failure.** Only a failed extraction fails a run. A failed later stage is recorded and the run returns what finished as `partial`.
5. **Data models.** Pydantic models for the submission, the extracted idea, search bundles, each analysis, the strategy parts, usage, versions and the report document (TECHNICAL_DOCUMENTATION, section 6).
6. **Switches for optimisation.** Candidate query and prompt behaviour sits behind `QUERY_PROFILE` and `PROMPT_PROFILE`, with `v1` as the default and the rollback (`docs/14`).

## 5. Implementation by milestone

Line counts are of the files as they are on 18 November 2026, after Milestone 4. Where Milestone 4 changed a file, its added and removed lines against the Milestone 3 commit are given (`git diff --numstat`).

### 5.1 Milestone 1: submission, extraction, web search

| File | Lines | Role |
|---|---:|---|
| `agents/extraction_agent.py` | 126 (M4: +65, −4) | Idea Extraction Agent |
| `agents/web_search_agent.py` | 315 (M4: +151, −24) | Web Search Agent: four queries, de-duplication, source URLs |
| `utils/search_client.py` | 99 (M4: +12, −6) | Tavily client and error mapping |
| `utils/llm_client.py` | 445 (M4: +3) | Gemini client, the only file importing the SDK, with the Groq fallback |
| `orchestrator.py` | 534 (M4: +98, −6) | `run_pipeline`: stages, timings, status |
| `app.py` | 109 (M4: +4) | FastAPI factory and error handlers |
| `frontend/app.py` | 719 | Streamlit interface, unchanged since |

Milestone 1 ended with 293 automated tests (README, "Features implemented in Milestone 1"). Live runs of four ideas on 14 October 2026: `docs/07_pipeline_test_report.md`, `docs/test_runs/`.

### 5.2 Milestone 2: market and competitor analysis

| File | Lines | Role |
|---|---:|---|
| `agents/market_opportunity_agent.py` | 556 (M4: +17, −3) | Market Opportunity Agent |
| `agents/market_size.py` | 363 (M4: +19, −6) | Market-size searches, focused snippets, checks |
| `agents/competitor_analysis_agent.py` | 708 (M4: +44, −11) | Competitor Analysis Agent, phases A and C |
| `agents/competitor_checks.py` | 549 (M4: +74) | Competitor checks in code |
| `agents/integrity.py` | 542 | Citation, URL and figure checks |
| `utils/groq_client.py` | 265 | Groq fallback over plain HTTPS |

The whole project had 1,301 passing tests at the end of Milestone 2 (`docs/09`, section 2). The integrated pipeline ran live once per Task 4 idea on 27 October 2026; all three finished `complete` in 102 to 159 seconds with no integrity violations (`docs/09`, README "Testing").

### 5.3 UI upgrade and Milestone 3: React interface, strategy and Advisor

| File | Lines | Role |
|---|---:|---|
| `utils/run_manager.py` | 707 (M4: +62, −2) | Background runs, cancel, history, report status |
| `utils/run_store.py` | 198 (M4: +4) | SQLite history and migration |
| `agents/strategy_context.py` | 460 (M4: +17, −1) | The numbered findings digest |
| `agents/strategy_checks.py` | 353 | Checks on every strategy point |
| `agents/swot_risk_agent.py` | 382 (M4: +9, −3) | SWOT and Risk Agent |
| `agents/mvp_agent.py` | 550 (M4: +9, −3) | MVP Recommendation Agent |
| `agents/gtm_agent.py` | 662 (M4: +9, −3) | Go-to-Market Agent |
| `agents/advisor_agent.py` | 716 | Startup Advisor |
| `web/` | | React interface (`docs/10`) |

Milestone 3 ended with 2,454 backend tests and 477 front-end tests passing; its live checks were not executed (`docs/12`, sections 1 and 4).

### 5.4 Milestone 4: report, testing, optimisation, documentation

| File | Lines | Role |
|---|---:|---|
| `models/report.py` | 196 | Report document models |
| `agents/report_sections.py` | 954 | Section builders |
| `agents/report_bibliography.py` | 133 | Bibliography |
| `agents/report_checks.py` | 328 | 12 consistency checks |
| `agents/report_agent.py` | 451 | Report Generation Agent |
| `utils/report_render_md.py`, `utils/report_render_pdf.py` | 141, 404 | Markdown and PDF renderers |
| `routes/report_routes.py` | 170 | Five report routes |
| `utils/usage.py` | 47 | AI request and search counter |
| `agents/query_profile.py`, `agents/prompt_profile.py` | 38, 51 | Query and prompt profile switches |
| `web/src/features/report/` (9 files) | 1,176 | Report page and its parts |
| `web/src/features/results/UsageTable.tsx`, `VersionsPanel.tsx` | 86, 50 | Run details panels |

Milestone 4 added 502 backend tests in 16 files and 75 front-end tests in 7 files (`docs/15`, section 2).

## 6. Testing and verification

Numbers from `docs/15_final_test_report.md`, measured on 18 November 2026 with fake providers:

| Suite | Result |
|---|---|
| Backend (pytest) | 2956 passed, 0 failed, 1 warning |
| Front end (Vitest) | 552 passed in 42 files, 0 MSW unhandled-request lines |
| TypeScript | clean |
| Build | entry chunk 269.24 kB (85.73 kB gzip); report page a lazy chunk |
| Browser (Playwright, Chromium, 390, 820 and 1440 px) | 369 passed in 7 specs |
| Accessibility (axe) | 0 serious or critical violations on 41 screens at three widths; the report page not checked |
| Coverage | not measured |
| Real-backend browser journeys, failure-injection matrix | not executed |
| Live runs of Milestone 4 | not executed |

The automated tests never call a provider: a fixture blocks every non-local socket in the backend, MSW fails any unmocked request in the front end, and the browser tests answer every API call by route interception. They prove the code paths, not live behaviour. The Milestone 4 end-to-end testing task and the live verification checkpoint were skipped by the user on 18 November 2026, so requirement R2 is not fully evidenced (`docs/15`, section 5).

## 7. Evaluation and optimisation

Four areas were addressed, each behind a switch with `v1` as the default (`docs/14`, section 1): web search query design (query profile `v2` and parallel search), prompt engineering (prompt profile `v2`), agent reasoning quality (digest de-duplication and a self-check line) and output accuracy (a matrix consistency check). The planned method is a three-idea manual pilot with fixed metrics, an adoption rule fixed before any data and a human-scored rubric (`docs/14`, sections 2 and 3).

The comparison has **not been executed**. There is no comparable baseline, and live runs need rotated keys and credit approval. Every result cell in `docs/14`, section 5 reads "not executed", the defaults stay `v1`, and no improvement is claimed.

## 8. Results and screenshots

- The earlier screens at three widths: `docs/assets/ui_v2/` (81 images) and the Milestone 3 screens: `docs/assets/ui_v3/` (42 images). The Milestone 3 images show a synthetic strategy result, not model output (`docs/10`, section 11).
- Saved live results: Milestone 1 in `docs/test_runs/`, Milestone 2 in `docs/test_runs_m2/`.
- No screenshot of the report page and no report generated from a live run exist yet. A synthetic sample of the report's Markdown is `tests/snapshots/m4_report_synthetic.md`; it comes from a synthetic fixture and is not evidence.

[FOUNDER TO FILL: after the rehearsal, add a screenshot of the report page and pages of a real PDF.]

## 9. Challenges and how they were solved

First-hand entries only, from the test reports:

| Milestone | Challenge | How it was solved | Source |
|---|---|---|---|
| M1 | Every real LLM call failed because the Gemini client was closed mid-request; 503 errors gave no diagnosable cause | The client is held for the whole call; causes are logged by class and status; a bounded retry recovers from transient 5xx | `docs/07`, section 5 |
| M2 | One live market run showed seven problems: misread download counts, clipped unit words, added conclusions, an off-topic pain point, conflicting figures merged, cut-off snippets | Code-side checks for figures, units, relevance and added conclusions; conflicting figures kept apart with a note; focused snippets for targeted searches | `docs/08`, section 5 |
| M3 | A strategy job kept stale warnings; positioning could name another segment; a Windows console stopped on "₹" | Seven fixes, each pinned by a test | `docs/12`, section 6 |
| M4 | The report page header would be hidden in print; app code reached the entry chunk | A `div` header; downloads moved into the lazy chunk | `docs/15`, section 7 |
| M4 | The required lazy route grows the entry chunk by 453 bytes above the approved ceiling | Proven to contain no report or app module; the ceiling raised and recorded as a deviation | `docs/15`, section 2.4 |
| All | A Tavily key was committed in Week 1 | `.gitignore` and `.env.example` added; revocation still open | `docs/agile/RETROSPECTIVE_AND_METRICS.md`; T0 audit |

## 10. Limitations and future scope

- No Milestone 4 live check has been executed: the report summary with a real model, the three-idea pilot, Advisor and Groq checks, cancel and limits with real providers.
- The PDF has not been reviewed with the production fonts, which are not installed.
- Real-backend browser journeys, the failure-injection matrix, coverage and the reproducibility check were not executed.
- One browser test is intermittent.
- ReportLab produces untagged PDF.
- Deferred by the plan: the evaluation package, recording and replay, dedicated live scripts, preflight and demo import scripts, traceability scripts, release tagging, the favicon and dependency clean-up.

Future scope: run the pilot and decide the defaults; complete the end-to-end and live checks; then the separate UI and Features plan, accounts and deployment. Full list: TECHNICAL_DOCUMENTATION, section 14.

## 11. Learning outcomes, individual contribution, team roles, mentor interaction

[FOUNDER TO FILL: learning outcomes.]

[FOUNDER TO FILL: individual contribution of each team member.]

[FOUNDER TO FILL: team roles. `docs/agile/README.md` section 5 lists the roles intern team, mentor, product owner and rotating Scrum Master.]

[FOUNDER TO FILL: mentor interaction and feedback. The Agile documents record none yet.]

## 12. Conclusion

The system takes a startup idea from two lines to a structured, cited validation and a downloadable report, with every point labelled by its basis and no viability score. Requirements R1 and R4 are built, R3's four areas are built behind switches, and the automated regression is green. Live behaviour, the PDF with real fonts, the optimisation comparison and the end-to-end journeys are still to be verified, so the milestone is not claimed as fully verified. [FOUNDER TO FILL: edit this conclusion.]

## References

Project documents: `docs/01` to `docs/15`, `docs/final/`, `docs/agile/`. External: the Tavily API documentation and pricing page (`docs/05`, References), the Groq structured outputs documentation (cited in `tests/test_m2_groq_structured.py`), Google AI Studio (README, Prerequisites). [FOUNDER TO FILL: any other source you used.]

## Appendices

- **A. Sample report:** `tests/snapshots/m4_report_synthetic.md` (synthetic). A real sample: [FOUNDER TO FILL after the rehearsal].
- **B. API table:** TECHNICAL_DOCUMENTATION, section 7, and `docs/final/openapi.json`.
- **C. Settings table:** TECHNICAL_DOCUMENTATION, section 4.

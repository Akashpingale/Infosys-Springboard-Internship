# Agile Sprint Plans (Week 01 to Week 09)

## Project Title
**Development of AI Based Startup Idea Validator with Market Analysis Assistance**

---

## Sprint Overview Summary

| Sprint | Week | Milestone | Primary Theme | Stories Planned | Stories Done |
|:---:|:---:|:---:|:---|:---:|:---:|
| **Sprint 1** | Week 1 (Days 01-05) | M1 | Foundations: understanding, agents, architecture, submission design, search test | 5 | 5 |
| **Sprint 2** | Week 2 (Days 06-10) | M1 | Idea submission, LLM extraction, Web Search Agent, orchestration, integration tests | 17 | 14 |
| **Sprint 3** | Week 3 (Days 11-15) | M2 | Market Opportunity Agent | 6 | 6 |
| **Sprint 4** | Week 4 (Days 16-20) | M2 | Competitor Analysis Agent and three-domain validation | 7 | 7 |
| **Sprint 5** | Week 5 (Days 21-25) | M3 | SWOT and Risk Analysis Agent | 5 | 5 |
| **Sprint 6** | Week 6 (Days 26-30) | M3 | MVP Agent, Go-to-Market Agent, Startup Advisor | 12 | 12 |
| **Sprint 7** | Week 7 (Days 31-35) | M3 | React interface and background runs | 14 | 15 |
| **Sprint 8** | Week 8 (Days 36-40) | M4 | Report Generation Agent and optimization | 7 | 8 |
| **Sprint 9** | Week 9 (Days 41-45) | M4 | Final testing, documentation and delivery | 6 | 6 |
| **Total** | **9 Weeks** | **M1-M4** | **End-to-end multi-agent startup validation platform** | **79** | **78** |

Story IDs refer to [`PRODUCT_BACKLOG.md`](./PRODUCT_BACKLOG.md). In Sprint 2, US-SUB-05 was delivered in Sprint 7, US-ORC-03 in Sprint 8, and US-WEB-05 is still in progress; this is why Sprint 7 and Sprint 8 show one more story done than planned. Calendar dates for each sprint are in the mentor's Excel Sprint Backlog. Mentor feedback is not recorded in this repository.

**†** Verified with fake providers only; the live checks for these sprints have not been run.

---

## Sprint 1: Foundations (Tasks 1-5)
**Duration**: Week 1 (Day 01 to Day 05)
**Sprint Goal**: Understand the project and startup validation, define the agents, design the architecture and submission module, and prove that live web search works.

### Committed User Stories
- `US-FND-01`: Project understanding notes with one sample idea.
- `US-FND-02`: Agent roles and responsibilities document.
- `US-FND-03`: System architecture diagram and information flow.
- `US-FND-04`: Submission UI wireframe and sample structured output.
- `US-FND-05`: Working Tavily web search test with sample results.

### Task Breakdown
| Task | Deliverable | Location |
|:---|:---|:---|
| Task 1 | Project understanding and SmartBite validation example | `docs/01_project_understanding.md` |
| Task 2 | AI agents, LLMs, multi-agent systems, six agent roles | `docs/02_multi_agent_system.md` |
| Task 3 | Architecture description and diagram | `docs/03_system_architecture.md` |
| Task 4 | Wireframe, field spec, LLM structuring approach, sample output | `docs/04_startup_idea_submission_module.md`, `docs/assets/task4_wireframe.png` |
| Task 5 | Tavily test script and sample results | `src/web_search/`, `docs/05_web_search_api.md`, `docs/05_sample_output.md` |

Repository set-up (MIT license, Agile documentation, folder layout, `.gitignore`, `.env.example`) was also completed in this sprint.

### Sprint 1 Review & Demo
- **Demoed**: Task documents, wireframe, and a live Tavily run with readable output saved to `src/web_search/output/`.
- **Open item**: the Tavily key committed on 11 Oct 2026 (commit `50ea1ae`) must be revoked and replaced.

---

## Sprint 2: Idea Submission, LLM Extraction & Web Search Agent
**Duration**: Week 2 (Day 06 to Day 10)
**Sprint Goal**: A founder can submit an idea, see it converted to a structured object, and the Web Search Agent returns sourced results for it, with an orchestrator and automated tests around them.

### Committed User Stories
- `US-SUB-01` to `US-SUB-05`: submission form, LLM structured extraction, input and response error handling, UI-to-backend connection, review and edit of the extracted idea.
- `US-WEB-01` to `US-WEB-05`: query generation, Web Search Agent, safe search errors, source URLs, duplicate and low-relevance filtering.
- `US-ORC-01` to `US-ORC-03`: basic orchestration, schemas and component boundaries, full specialist-agent integration.
- `US-TEST-01` to `US-TEST-04`: workflow tests, multi-industry runs, setup documentation, publication to GitHub `main`.

### Task Breakdown
| Task | Deliverable | Location |
|:---|:---|:---|
| Submission form and schema | Form that sends the idea to the backend; validated request model | `frontend/app.py`, `models/schemas.py` |
| LLM extraction | Structured idea with retry on invalid replies and transient 5xx errors | `agents/extraction_agent.py`, `utils/llm_client.py`, `utils/structured.py` |
| Web Search Agent | Four labelled queries, Tavily client, source URLs, safe errors | `agents/web_search_agent.py`, `utils/search_client.py` |
| Orchestration and API | Ordered pipeline with complete, partial and failed status | `orchestrator.py`, `routes/` (`/api/extract`, `/api/search`, `/api/validate`) |
| Automated tests | Success, missing input, API error and unexpected-response tests (293 passing) | `tests/` |
| Live runs | AgriTech, FinTech, FoodTech and HealthTech ideas | `docs/test_runs/`, `docs/07_pipeline_test_report.md` |
| Setup documentation | README with setup, environment variables and run steps | `README.md` |

### Sprint 2 Review & Demo
- **Demoed**: the working solution, recorded and emailed to the mentor, with live runs on four industries.
- **Not finished**: US-SUB-05 (moved to Sprint 7), US-ORC-03 (moved to Sprint 8) and US-WEB-05 (URL de-duplication is done; filtering by relevance score is not built).
- This closes Milestone 1.

---

## Sprint 3: Market Opportunity Agent
**Duration**: Week 3 (Day 11 to Day 15)
**Sprint Goal**: Estimate the market size, growth trends and opportunity score for an idea from live search results, with every claim cited.

### Committed User Stories
- `US-MKT-01`: Market size estimation.
- `US-MKT-02`: Growth trend identification.
- `US-MKT-03`: Opportunity scoring.
- `US-MKT-04`: Numbered market citations.
- `US-MKT-05`: Market-size targeted searches.
- `US-MKT-06`: Market agent test suite.

### Task Breakdown
| Task | Deliverable | Location |
|:---|:---|:---|
| Market Opportunity Agent | Size, trends, segments and scoring, with numbered citations | `agents/market_opportunity_agent.py`, `agents/market_size.py` |
| Evidence preparation | Numbered, de-duplicated evidence from search results | `agents/evidence.py`, `utils/structured.py` |
| Claim and figure checks | Figure reader, claim relabelling, relevance check | `agents/figures.py`, `agents/market_claims.py` |
| Dev script | Run one agent on one idea | `scripts/run_agent.py` |
| Tests | Market agent tests with fake LLM and search | `tests/test_market_opportunity_agent.py`, `tests/test_figures.py`, `tests/test_market_claims.py` |

### Sprint 3 Review & Demo
- **Demoed**: one live standalone market run, saved in `docs/test_runs_m2/dev_market_agritech_v2.txt`.
- **Result**: the run exposed problems with figure reading, added conclusions, off-topic pain points and cut-off snippets; each was fixed and tested (`docs/08_milestone2_agents.md`, section 5).

---

## Sprint 4: Competitor Analysis Agent & Three-Domain Validation
**Duration**: Week 4 (Day 16 to Day 20)
**Sprint Goal**: Identify competitors, compare their features with the proposed solution, enforce evidence integrity, and show market and competitor analysis together.

### Committed User Stories
- `US-COMP-01`: Competitor identification.
- `US-COMP-02`: Feature comparison.
- `US-COMP-03`: Targeted competitor searches.
- `US-COMP-04`: Cited competitor claims.
- `US-COMP-05`: Evidence integrity checks.
- `US-COMP-06`: Analysis display in Streamlit.
- `US-COMP-07`: Multi-domain test coverage.

### Task Breakdown
| Task | Deliverable | Location |
|:---|:---|:---|
| Competitor Analysis Agent | Competitors, feature comparison, citations | `agents/competitor_analysis_agent.py`, `agents/competitor_checks.py` |
| Integrity checks | Missing citations, broken URLs, unreferenced evidence | `agents/integrity.py` |
| Four-stage pipeline and UI | Market and competitor stages in the pipeline and the Streamlit page | `orchestrator.py`, `frontend/analysis_views.py` |
| Three-domain validation | AgriTech, FinTech and FoodTech ideas | `data/test_ideas/`, `tests/test_m2_domains.py`, `scripts/run_live_m2.py` |
| Integration fixes | Markdown report export, API audit fields, backend time limit, Groq structured outputs | `tests/test_m2_report.py`, `tests/test_m2_audit_fields.py`, `tests/test_m2_time_limit.py`, `tests/test_m2_groq_structured.py` |

### Sprint 4 Review & Demo
- **Demoed**: the full pipeline run live on three ideas; all three finished `complete` in 102.5 s to 159.3 s with no integrity violations (`docs/test_runs_m2/`, `docs/09_milestone2_test_report.md`).
- **Result**: 1,301 backend tests passing at the end of Milestone 2. This closes Milestone 2.

---

## Sprint 5: SWOT & Risk Analysis †
**Duration**: Week 5 (Day 21 to Day 25)
**Sprint Goal**: Turn the validation findings into a SWOT analysis and a ranked risk register, working from a numbered digest so every point can be traced.

### Committed User Stories
- `US-SWOT-01`: SWOT quadrants.
- `US-SWOT-02`: SWOT basis labels.
- `US-RISK-01`: Risk identification.
- `US-RISK-02`: Severity scoring.
- `US-STRAT-01`: Numbered findings digest.

### Task Breakdown
| Task | Deliverable | Location |
|:---|:---|:---|
| SWOT and Risk Agent | 3-5 points per quadrant, 6-10 risks, severity from likelihood × impact | `agents/swot_risk_agent.py` |
| Findings digest | Numbered digest the strategy prompts read | `agents/strategy_context.py` |
| Strategy checks | Reference checks and basis labels | `agents/strategy_checks.py` |
| Tests | Digest, checks and SWOT agent tests with fake providers | `tests/test_m3_digest.py`, `tests/test_m3_checks.py`, `tests/test_m3_swot_agent.py` |

### Sprint 5 Review & Demo
- **Demoed**: SWOT and risk results from fake-provider runs and the live-script fake mode (`docs/11_milestone3_strategy_and_advisor.md`).
- **Not run**: the live strategy checks.

---

## Sprint 6: MVP, Go-to-Market & Startup Advisor †
**Duration**: Week 6 (Day 26 to Day 30)
**Sprint Goal**: Recommend what to build first and how to launch, and let the founder ask cited follow-up questions about the validation.

### Committed User Stories
- `US-MVP-01` to `US-MVP-03`: feature ranking, first-release scope, success metrics.
- `US-GTM-01` to `US-GTM-03`: positioning statement, channel ranking, three-phase launch plan.
- `US-ADV-01` to `US-ADV-06`: cited answers, off-topic refusal, question limits, conversation history, suggested questions, clear conversation.

### Task Breakdown
| Task | Deliverable | Location |
|:---|:---|:---|
| MVP Agent | Impact × effort ranking, first-release scope, success metrics | `agents/mvp_agent.py` |
| Go-to-Market Agent | Positioning from the priority segment, channels, launch plan | `agents/gtm_agent.py` |
| Startup Advisor | Question routing, cited answers, limits | `agents/advisor_agent.py`, `models/chat.py` |
| Chat and strategy API | Advisor chat and strategy on a saved run | `routes/chat_routes.py`, `routes/strategy_routes.py`, `utils/chat_store.py` |
| Tests | Agent, API, store migration and no-secrets tests | `tests/test_m3_*.py` |

### Sprint 6 Review & Demo
- **Demoed**: fake-provider runs and the three live-script fake runs; 2,454 backend tests passing at the Milestone 3 report (`docs/12_milestone3_test_report.md`).
- **Result**: seven bugs found and fixed, each with a named test (`docs/12`, section 6). Two items stay open: strategy stage keys in the legacy report's "Time taken" line, and Advisor replies that are not scanned for secrets.
- **Not run**: live checks L-1 to L-5.

---

## Sprint 7: React Interface & Background Runs
**Duration**: Week 7 (Day 31 to Day 35)
**Sprint Goal**: Give founders a browser interface where a validation runs in the background, can be reviewed, cancelled, reopened and exported, and works on a phone, a tablet and a desktop.

### Committed User Stories
- `US-WEB2-01` to `US-WEB2-14`: background runs API, limit-aware form, idea review screen, stage progress and cancel, source drawer, result tabs, export, run history, provider status, responsive design, accessibility, provider-free tests, live parity run, Streamlit retained.
- `US-SUB-05` (planned in Sprint 2): delivered by the review screen.

### Task Breakdown
| Task | Deliverable | Location |
|:---|:---|:---|
| Background runs and history | Start, poll, cancel, list, rename, delete | `routes/run_routes.py`, `routes/meta_routes.py`, `utils/run_manager.py`, `utils/run_store.py` |
| React interface | Form, review screen, progress, tabs, source drawer, export, status screen | `web/src/` |
| Responsive design and accessibility | 390, 820 and 1440 px; 0 serious or critical axe violations | `web/e2e/`, `docs/10_ui_design_system.md` |
| Provider-free tests | Front-end tests (MSW) and browser tests (Playwright) | `web/`, `web/e2e/` |
| Live parity run | Five validations run from the React interface | `docs/10_ui_design_system.md`, section 9 |

### Sprint 7 Review & Demo
- **Demoed**: the React interface running real validations; three of the five live runs finished complete and two partial (one because of a Gemini quota error).
- **Result**: 1,636 backend, 295 front-end and 183 browser tests passing at the end of the interface work. Streamlit is kept until parity is fully confirmed.

---

## Sprint 8: Report Generation & Optimization †
**Duration**: Week 8 (Day 36 to Day 40)
**Sprint Goal**: Produce a shareable validation report in three formats, enforce its consistency, and improve search quality and speed.

### Committed User Stories
- `US-REP-01` to `US-REP-04`: 16-section report (PDF, Markdown, JSON), AI executive summary, 12 consistency checks, download in React.
- `US-OPT-01` to `US-OPT-03`: query profile v2, prompt profile v2, parallel search.
- `US-ORC-03` (planned in Sprint 2): all specialist agents and the report in the orchestrator.

### Task Breakdown
| Task | Deliverable | Location |
|:---|:---|:---|
| Report Generation Agent | Document model, sections, bibliography, 12 checks | `agents/report_agent.py`, `agents/report_sections.py`, `agents/report_bibliography.py`, `agents/report_checks.py`, `models/report.py` |
| Renderers and API | Markdown and PDF output, report routes | `utils/report_render_md.py`, `utils/report_render_pdf.py`, `routes/report_routes.py` |
| Report page | Report page and downloads in the React interface | `web/src/` |
| Profiles v2 | Query profile v2, prompt profile v2, matrix consistency rule | `agents/query_profile.py`, `agents/prompt_profile.py` |
| Parallel search | 1-8 concurrent searches with results equal to sequential search | `agents/web_search_agent.py`, `config.py` |

### Sprint 8 Review & Demo
- **Demoed**: report generation in all three formats with fake providers (`docs/13_report_generation_agent.md`, `docs/14_evaluation_and_optimization.md`).
- **Result**: three problems found and fixed (`docs/15_final_test_report.md`, section 7). One intermittent browser test stays open.
- **Not run**: live report checks and browser tests of the report page.

---

## Sprint 9: Final Testing, Documentation & Delivery
**Duration**: Week 9 (Day 41 to Day 45)
**Sprint Goal**: Measure the whole system, document it for users and reviewers, and list what has not been verified.

### Committed User Stories
- `US-DOC-01`: Technical documentation.
- `US-DOC-02`: User guide and demo runbook.
- `US-DOC-03`: Project report.
- `US-TEST-05`: Backend test suite.
- `US-TEST-06`: Front-end and browser tests.
- `US-TEST-07`: Accessibility testing.

### Task Breakdown
| Task | Deliverable | Location |
|:---|:---|:---|
| Final documentation | Technical documentation, user guide, demo runbook, project report, presentation spec | `docs/final/` |
| Final test run | Backend, front-end, browser, accessibility and secret scan results | `docs/15_final_test_report.md` |
| Backend re-run | 2,961 passed, 4 skipped | `python -m pytest` |

### Sprint 9 Review & Demo
- **Measured**: 2,956 backend, 552 front-end and 369 browser tests passed; 0 serious or critical axe violations on 41 screens; 0 secret-scan hits.
- **Outstanding** (`docs/15`, section 5): live checks L-1 to L-8, code coverage, the report page browser tests, and confirmation that the exposed keys were rotated.

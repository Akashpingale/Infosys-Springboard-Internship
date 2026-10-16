# Agile Product Backlog: Milestone 1

## Project Title
**Development of AI Based Startup Idea Validator with Market Analysis Assistance**

Columns follow the mentor's `Agile_Template_v0.1.xlsx` (Product Backlog sheet): Planned Sprint, Actual Sprint, US ID, User Story, MoSCoW, Dependency, Assignee, Status. This backlog covers Milestone 1 (Weeks 1–2) only.

---

## 1. Product Vision & Target Personas

### Product Vision
To give early-stage founders a fast, evidence-based first opinion on a startup idea. From a short description, the system uses an initial AI workflow to structure the idea, retrieve live market and competitor information, and present the results for review. Milestone 1 establishes the submission interface, LLM-based extraction, Web Search Agent, and basic orchestration needed for later market, competitor, SWOT, risk, MVP, and report-generation modules.

### Target Personas
1. **First-time Founder / Student Entrepreneur**: has an idea and limited time or budget for market research.
2. **Early-stage Founder with a Prototype**: wants to compare the idea against competitors and identify potential gaps.
3. **Mentor / Incubator Reviewer**: wants a consistent, source-backed starting point for reviewing startup ideas.

---

## 2. Definition of Done (DoD)

A story is **Done** only when the applicable criteria are met:

- [ ] **Code complete**: implemented, runs locally, and reviewed according to the team's workflow.
- [ ] **Tests**: relevant automated tests are added with `pytest`; the test suite passes.
- [ ] **Security**: API keys and credentials are not committed.
- [ ] **Documentation**: relevant files in `docs/` and required Agile templates are updated.
- [ ] **Demo-ready**: the increment can be demonstrated during the Sprint Review.

---

## 3. User Stories

Status values: `DONE`, `IN PROGRESS`, `PLANNED`. Statuses reflect the progress discussed and recorded for the project through **2026-10-16**; verify them against the latest repository before formal submission.

### Epic 1: Foundation (SOP Tasks 1–5)

| Planned Sprint | Actual Sprint | US ID | User Story | MoSCoW | Dependency | Assignee | Status |
|:---:|:---:|:---|:---|:---:|:---|:---|:---:|
| 1 | 1 | **US-FND-01** | *As a team member, I want notes on startup validation and one sample idea so that the team shares the same understanding.* (`docs/01_project_understanding.md`) | MUST | - | Anil Kumar | DONE |
| 1 | 1 | **US-FND-02** | *As a team member, I want agent roles and responsibilities defined so that each module has a clear responsibility.* (`docs/02_multi_agent_system.md`) | MUST | US-FND-01 | TBD | DONE |
| 1 | 1 | **US-FND-03** | *As a developer, I want a system architecture and information flow so that implementation follows one design.* (`docs/03_system_architecture.md`) | MUST | US-FND-02 | Kanukula Devi | DONE |
| 1 | 1 | **US-FND-04** | *As a founder, I want a submission-module wireframe and structured output format so that an idea can be represented consistently.* (`docs/04_startup_idea_submission_module.md`) | MUST | US-FND-03 | Chandana B | DONE |
| 1 | 1 | **US-FND-05** | *As a developer, I want a working Tavily web-search test so that the project can retrieve live information.* (`src/web_search/`, `docs/05_web_search_api.md`) | MUST | US-FND-03 | Akash Pingale | DONE |

### Epic 2: Startup Idea Submission & Structured Extraction (Implementation Task 1–2)

| Planned Sprint | Actual Sprint | US ID | User Story | MoSCoW | Dependency | Assignee | Status |
|:---:|:---:|:---|:---|:---:|:---|:---|:---:|
| 2 | 2 | **US-SUB-01** | *As a founder, I want to submit an idea description, industry, target customers, and relevant details through a form so that the backend receives the required input.* | MUST | US-FND-04 | TBD | DONE |
| 2 | 2 | **US-SUB-02** | *As a founder, I want my free-text idea converted by an LLM into a structured object containing the problem, solution, target customers, industry, and key features.* | MUST | US-SUB-01 | TBD | DONE |
| 2 | 2 | **US-SUB-03** | *As a founder, I want missing inputs and invalid LLM responses handled clearly so that failed requests do not break the workflow.* | MUST | US-SUB-02 | TBD | DONE |
| 2 | 2 | **US-SUB-04** | *As a founder, I want the submission interface connected to the backend so that I can run the initial validation workflow from the UI.* | MUST | US-SUB-01, US-SUB-02 | TBD | IN PROGRESS |
| 2 | - | **US-SUB-05** | *As a founder, I want to review and edit the extracted idea before analysis agents run.* | SHOULD | US-SUB-02 | TBD | PLANNED |

### Epic 3: Web Search Agent (Implementation Task 3)

| Planned Sprint | Actual Sprint | US ID | User Story | MoSCoW | Dependency | Assignee | Status |
|:---:|:---:|:---|:---|:---:|:---|:---|:---:|
| 2 | 2 | **US-WEB-01** | *As the pipeline, I want search queries generated from the structured idea so that retrieval is relevant to the startup's market.* | MUST | US-SUB-02 | TBD | DONE |
| 2 | 2 | **US-WEB-02** | *As the pipeline, I want Tavily search wrapped by the Web Search Agent to return readable result information, including titles, snippets, scores, and URLs where available.* | MUST | US-FND-05 | TBD | DONE |
| 2 | 2 | **US-WEB-03** | *As the pipeline, I want API errors and unexpected search responses handled so that search failures are reported safely.* | MUST | US-WEB-02 | TBD | DONE |
| 2 | 2 | **US-WEB-04** | *As a reader, I want search results linked to their source URLs so that I can inspect the original information.* | MUST | US-WEB-02 | TBD | DONE |
| 2 | - | **US-WEB-05** | *As an analyst agent, I want duplicate and low-relevance results filtered so that downstream analysis receives cleaner evidence.* | SHOULD | US-WEB-02 | TBD | PLANNED |

### Epic 4: Multi-Agent Architecture & Orchestration (Implementation Task 4)

| Planned Sprint | Actual Sprint | US ID | User Story | MoSCoW | Dependency | Assignee | Status |
|:---:|:---:|:---|:---|:---:|:---|:---|:---:|
| 2 | 2 | **US-ORC-01** | *As a developer, I want a basic orchestration function to coordinate structured extraction and web search so that the initial workflow can run in sequence.* | MUST | US-SUB-02, US-WEB-02 | TBD | DONE |
| 2 | 2 | **US-ORC-02** | *As a developer, I want defined schemas and component boundaries so that structured ideas and search results can be passed consistently between components.* | MUST | US-ORC-01 | TBD | DONE |
| 2 | - | **US-ORC-03** | *As a developer, I want the Market Analysis, Competitor Analysis, SWOT/Risk, MVP Recommendation, and Report Generation agents integrated into the orchestrator.* | SHOULD | US-ORC-01 | TBD | PLANNED |

### Epic 5: Integration, Testing & Documentation (Implementation Task 5)

| Planned Sprint | Actual Sprint | US ID | User Story | MoSCoW | Dependency | Assignee | Status |
|:---:|:---:|:---|:---|:---:|:---|:---|:---:|
| 2 | 2 | **US-TEST-01** | *As a developer, I want automated tests for successful workflows, missing inputs, API errors, and unexpected responses so that the initial workflow is reliable.* | MUST | US-SUB-02, US-WEB-02, US-ORC-01 | TBD | DONE |
| 2 | 2 | **US-TEST-02** | *As a developer, I want to run the workflow against at least three startup ideas from different industries so that basic integration is verified.* | MUST | US-ORC-01 | TBD | DONE |
| 2 | 2 | **US-TEST-03** | *As a developer, I want setup instructions, dependencies, environment variables, and execution steps documented so that another team member can run the project.* | MUST | US-SUB-01, US-WEB-02 | TBD | IN PROGRESS |
| 2 | 2 | **US-TEST-04** | *As a team member, I want the completed code and documentation published to the team's GitHub `main` branch so that the team has a shared, up-to-date version.* | MUST | US-TEST-01, US-TEST-03 | TBD | IN PROGRESS |

---

## 4. Milestone 1 Progress Snapshot (2026-10-16)

| Area | Progress recorded | Remaining work |
|---|---|---|
| Project foundation and documentation | Initial project notes, agent responsibilities, architecture, wireframe, and web-search exploration documented. | Confirm all documentation and Agile workbook entries are present and current. |
| Startup idea submission | A runnable frontend submission interface exists and has been reviewed. | Finish UI alignment/usability refinements and verify the latest local frontend changes are published. |
| LLM structured extraction | Structured extraction and error handling are implemented and tested. | Re-run final integration checks after the latest changes. |
| Web Search Agent | Tavily integration, test script, and saved sample output/screenshots exist. | Confirm environment-variable setup and source links in the final demo. |
| Orchestration | Basic flow connects extraction and web search. | Full specialist-agent integration is planned for later milestones. |
| Testing | Latest recorded full automated run: **293 passed, 1 deprecation warning**. Live checks covered AgriTech, FinTech, FoodTech, and HealthTech ideas. | Re-run tests on the final merged `main` branch. |
| GitHub publication | Milestone 1 feature work was pushed to a feature branch; latest local `main` has uncommitted frontend/configuration changes. | Review Git status, resolve any merge conflicts carefully, commit intended files only, and verify the final `main` branch on GitHub. |

---

## 5. Notes for Backlog Maintenance

- Replace `TBD` with the actual assignee only after the team confirms ownership.
- Keep a story marked `DONE` only when its Definition of Done is satisfied; otherwise change it to `IN PROGRESS`.
- The progress snapshot reflects the information available through **2026-10-16** and should be checked against the current repository before formal submission.
- Keep all API keys and other secrets in environment variables; do not commit real `.env` files or credentials.
- Later milestones should add their own backlog stories for market analysis, competitor analysis, SWOT/risk analysis, MVP recommendations, go-to-market strategy, conversational advising, and report generation.

# Agile Product Backlog: Milestone 1

## Project Title
**Development of AI Based Startup Idea Validator with Market Analysis Assistance**

Columns follow the mentor's `Agile_Template_v0.1.xlsx` (Product Backlog sheet): Planned Sprint, Actual Sprint, US ID, User Story, MoSCoW, Dependency, Assignee, Status. This backlog covers Milestone 1 (Week 1-2) only.

---

## 1. Product Vision & Target Personas

### Product Vision
To give early-stage founders a fast, evidence-based first opinion on a startup idea. From a 2-3 line description, a pipeline of AI agents retrieves live market data and produces a structured validation report. Milestone 1 builds the foundation: the shared design, the idea submission module, and the Web Search Agent.

### Target Personas
1. **First-time Founder / Student Entrepreneur**: has an idea, little time or money for market research.
2. **Early-stage Founder with a Prototype**: wants to compare against competitors and find gaps.
3. **Mentor / Incubator Reviewer**: wants a consistent, source-backed report to review many ideas.

---

## 2. Definition of Done (DoD)

A story is **Done** only when all of the following are true:

- [ ] **Code complete**: implemented, runs locally, reviewed in a pull request.
- [ ] **Tests**: automated tests added with `pytest`; the whole suite passes.
- [ ] **Security**: no API keys or credentials committed.
- [ ] **Documentation**: relevant file in `docs/` updated; Excel templates updated.
- [ ] **Demo-ready**: the increment can be shown in the Sprint Review.

---

## 3. User Stories

Status values: `DONE`, `PLANNED`.

### Epic 0: Foundation (SOP Tasks 1-5)

| Planned Sprint | Actual Sprint | US ID | User Story | MoSCoW | Dependency | Assignee | Status |
|:---:|:---:|:---|:---|:---:|:---|:---|:---:|
| 1 | 1 | **US-FND-01** | *As a team member, I want notes on startup validation and one sample idea validated so that the team shares the same understanding.* (`docs/01_project_understanding.md`) | MUST | - | Anil Kumar | DONE |
| 1 | 1 | **US-FND-02** | *As a team member, I want agent roles and responsibilities defined so that each module has a clear owner.* (`docs/02_multi_agent_system.md`) | MUST | US-FND-01 |  | DONE |
| 1 | 1 | **US-FND-03** | *As a developer, I want a system architecture and information flow so that implementation follows one design.* (`docs/03_system_architecture.md`) | MUST | US-FND-02 | Kanukula Devi | DONE |
| 1 | 1 | **US-FND-04** | *As a founder, I want a submission form wireframe and a structured output format so that my idea reaches the agents in a usable form.* (`docs/04_startup_idea_submission_module.md`) | MUST | US-FND-03 | Chandana B | DONE |
| 1 | 1 | **US-FND-05** | *As a developer, I want a working Tavily web search test so that agents can use live data.* (`src/web_search/`, `docs/05_web_search_api.md`) | MUST | US-FND-03 | Akash Pingale | DONE |

### Epic 1: Startup Idea Submission (Milestone 1 Module)

| Planned Sprint | Actual Sprint | US ID | User Story | MoSCoW | Dependency | Assignee | Status |
|:---:|:---:|:---|:---|:---:|:---|:---|:---:|
| 2 | - | **US-SUB-01** | *As a founder, I want to submit my idea, target customers, and industry through a simple form.* | MUST | US-FND-04 | TBD | PLANNED |
| 2 | - | **US-SUB-02** | *As a founder, I want my free-text idea converted by an LLM into a validated structured object so that all agents use the same input.* | MUST | US-SUB-01 | TBD | PLANNED |
| 2 | - | **US-SUB-03** | *As a founder, I want to review and edit what the system understood before the agents run.* | SHOULD | US-SUB-02 | TBD | PLANNED |

### Epic 2: Web Search Agent (Milestone 1 Module)

| Planned Sprint | Actual Sprint | US ID | User Story | MoSCoW | Dependency | Assignee | Status |
|:---:|:---:|:---|:---|:---:|:---|:---|:---:|
| 2 | - | **US-WEB-01** | *As the pipeline, I want search queries generated from the structured idea so that retrieval is relevant.* | MUST | US-SUB-02 | TBD | PLANNED |
| 2 | - | **US-WEB-02** | *As the pipeline, I want the Tavily search wrapped as the Web Search Agent returning titles, snippets, scores, and URLs.* | MUST | US-FND-05 | TBD | PLANNED |
| 2 | - | **US-WEB-03** | *As an analyst agent, I want duplicate and low-relevance results removed.* | SHOULD | US-WEB-02 | TBD | PLANNED |
| 2 | - | **US-WEB-04** | *As a reader, I want every result linked to its source URL.* | MUST | US-WEB-02 | TBD | PLANNED |

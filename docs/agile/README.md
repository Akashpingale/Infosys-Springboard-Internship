# 9-Week Agile Internship Framework & Lifecycle

## Project Title

**Development of AI Based Startup Idea Validator with Market Analysis Assistance**

---

## 1. Executive Summary & Internship Context

This repository represents the work of a **9-Week Infosys Springboard Internship** (5 working days per week, totaling **45 working days**). The engineering process is organized under the **Agile Scrum Framework** with **1-week sprint cycles**.

The objective of the project is to engineer a multi-agent platform that takes a startup idea in 2-3 lines and produces a structured startup validation report using live web search and LLM-powered business reasoning.

**Project milestones:**

1. **Milestone 1 (Sprints 1-2):** study startup validation, design the architecture and agent roles, build the idea submission interface, LLM-based structured extraction, the Tavily Web Search Agent and basic orchestration.
2. **Milestone 2 (Sprints 3-4):** Market Opportunity Agent and Competitor Analysis Agent with numbered citations and evidence-integrity checks, tested on three domains.
3. **Milestone 3 (Sprints 5-7):** SWOT and Risk, MVP and Go-to-Market agents, the Startup Advisor, and the React interface with background runs and run history.
4. **Milestone 4 (Sprints 8-9):** Report Generation Agent (PDF, Markdown, JSON), query and prompt profiles v2, parallel search, final testing and documentation.

The repository is licensed under the [MIT License](../../LICENSE). API keys are read from `.env`, which is git-ignored. One key exposed in the early Git history is listed under Open Items in [`PRODUCT_BACKLOG.md`](./PRODUCT_BACKLOG.md).

---

## 2. Agile Internship Cadence & Structure

```
+-----------------------------------------------------------------------------------+
|                       9-WEEK SPRINT CADENCE (45 DAYS)                             |
+-----------------------------------------------------------------------------------+
| Week 1 (Days 01-05) : Sprint 1 - Study, Agent Roles, System Architecture,        |
|                       Submission Design, Tavily Web Search Test                   |
| Week 2 (Days 06-10) : Sprint 2 - Idea Submission, LLM Structuring, Web Search    |
|                       Agent, Orchestration, Integration Tests                     |
| Week 3 (Days 11-15) : Sprint 3 - Market Opportunity Agent                         |
| Week 4 (Days 16-20) : Sprint 4 - Competitor Analysis Agent, Three-Domain Tests    |
| Week 5 (Days 21-25) : Sprint 5 - SWOT and Risk Analysis Agent                      |
| Week 6 (Days 26-30) : Sprint 6 - MVP Agent, Go-to-Market Agent, Startup Advisor   |
| Week 7 (Days 31-35) : Sprint 7 - React Interface and Background Runs              |
| Week 8 (Days 36-40) : Sprint 8 - Report Generation Agent, Optimization            |
| Week 9 (Days 41-45) : Sprint 9 - Final Testing, Documentation and Delivery        |
+-----------------------------------------------------------------------------------+
```

The Sprint 1 foundation tasks were due on **12 October 2026**. Calendar dates for each sprint are recorded in the mentor's Excel Sprint Backlog.

### Daily & Weekly Scrum Ceremonies

- **Daily Standup:** short sync covering:
  - What was accomplished yesterday?
  - What will be accomplished today?
  - What blockers or impediments are present?
  - Technical learnings and discoveries.
- **Sprint Planning** (start of each week): sprint backlog defined from the Product Backlog, task breakdown, capacity planning.
- **Sprint Review & Demo** (end of each week): demonstration of the working increment to the mentor.
- **Sprint Retrospective** (end of each week): retrospective analysis (Start Doing, Stop Doing, Continue Doing, Action taken), as in the Retrospection template.

Meeting days and times are set by the team and recorded in the Excel Stand-up and Sprint Backlog sheets.

---

## 3. Sprint-by-Sprint Milestone Summary

| Sprint | Week | Primary Focus Area | Delivered Features | Stories Done | Status |
|:---:|:---:|:---|:---|:---:|:---:|
| **SP-01** | W1 (Days 01-05) | Understanding & Design Foundations | Project understanding notes with sample idea, six agent roles, architecture diagram, submission wireframe and sample structured output, Tavily search test | 5 | Done |
| **SP-02** | W2 (Days 06-10) | Idea Submission & Web Search (Milestone 1) | Submission form, LLM structuring into a validated idea object, Web Search Agent with query generation and source URLs, orchestrator with complete / partial / failed status, 293 automated tests, live runs on four industries | 14 | Done (US-WEB-05 open) |
| **SP-03** | W3 (Days 11-15) | Market Opportunity Agent (Milestone 2) | Market size estimation, growth trends, opportunity scoring, numbered citations, targeted market searches | 6 | Done |
| **SP-04** | W4 (Days 16-20) | Competitor Analysis Agent (Milestone 2) | Competitor identification, feature comparison, targeted searches, cited claims, integrity checks, Streamlit analysis view, live runs on AgriTech, FinTech and FoodTech | 7 | Done |
| **SP-05** | W5 (Days 21-25) | SWOT & Risk Analysis (Milestone 3) | SWOT agent, risk register with severity from likelihood × impact, numbered findings digest | 5 | Done † |
| **SP-06** | W6 (Days 26-30) | MVP, Go-to-Market & Advisor (Milestone 3) | MVP ranking and first-release scope, positioning and channel plan, three-phase launch plan, Startup Advisor with cited answers and limits | 12 | Done † |
| **SP-07** | W7 (Days 31-35) | React Interface & Background Runs (Milestone 3) | Background runs API, run history, review screen, stage progress and cancel, source drawer, result tabs, export, responsive design, accessibility checks, five live runs from the interface | 15 | Done |
| **SP-08** | W8 (Days 36-40) | Report Generation & Optimization (Milestone 4) | 16-section report in PDF, Markdown and JSON, 12 consistency checks, query profile v2, prompt profile v2, parallel search, full agent integration | 8 | Done † |
| **SP-09** | W9 (Days 41-45) | Testing, Documentation & Delivery (Milestone 4) | Technical documentation, user guide and demo runbook, project report, final test run: 2,956 backend, 552 front-end and 369 browser tests passed, 0 serious or critical axe violations | 6 | Done |
| **TOTAL** | **9 Wks** | **Full Platform Delivery** | Multi-agent validation platform with a Streamlit and a React interface, strategy agents, a cited Startup Advisor and a shareable report | **78 of 79** | **78 done, 1 in progress** |

**†** Verified with fake providers only; the live checks for these sprints have not been run (see Open Items in [`PRODUCT_BACKLOG.md`](./PRODUCT_BACKLOG.md)).

---

## 4. Documentation Index

The Agile documentation suite is organized across the following documents:

| Document | Contents |
|:---|:---|
| [Product Backlog (`PRODUCT_BACKLOG.md`)](./PRODUCT_BACKLOG.md) | Product vision, personas, all 79 user stories in 8 epics with MoSCoW prioritization, Definition of Done (DoD), backlog summary, measured test results and open items. |
| [Sprint Plans (`SPRINT_PLANS_W01_TO_W09.md`)](./SPRINT_PLANS_W01_TO_W09.md) | Sprint goals, committed stories, task breakdowns, sprint reviews, and demo notes for all 9 weeks. |
| [Daily Standup Logs (`DAILY_STANDUP_LOGS_45_DAYS.md`)](./DAILY_STANDUP_LOGS_45_DAYS.md) | Daily log entries documenting tasks, impediments, and action taken. |
| [Agile Metrics & Retrospective (`RETROSPECTIVE_AND_METRICS.md`)](./RETROSPECTIVE_AND_METRICS.md) | Stories planned versus done, test counts, defect summary, and sprint retrospectives. |
| [Mentor Excel Templates (`templates/`)](./templates) | `Agile_Template` (Product Backlog, Sprint Backlog, Stand-up, Retrospection), `Unit_Test_Plan`, and `Defect_Tracker`. |

---

## 5. Team Roles & RACI Matrix

| Role | Responsibility |
|:---|:---|
| **Intern / Development Team** | Design, backend APIs, LLM structuring, Web Search Agent, analysis and strategy agents, React and Streamlit interfaces, report generation, testing, and documentation. Team members: Akash Pingale, Prathamesh Shinde, Anil Kumar, Deepika, Kanukula Devi, Chandana B. |
| **Internship Mentor** | Task assignment, review of deliverables, sprint guidance, and technical obstacle escalation. Mentor contact: Subramanyam. |
| **Product Owner (Mentor / Team)** | User story requirement validation and acceptance of each sprint increment. |
| **Scrum Master (rotating)** | Sprint ceremony facilitation, tracking of stories done, impediment removal, and keeping the Excel sheets and these documents up to date. |

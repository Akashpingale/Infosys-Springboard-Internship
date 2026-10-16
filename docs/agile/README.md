# 9-Week Agile Internship Framework & Lifecycle

## Project Title

**Development of AI Based Startup Idea Validator with Market Analysis Assistance**

---

## 1. Executive Summary & Internship Context

This repository represents the work of a **9-Week Infosys Springboard Internship** (5 working days per week, totaling **45 working days**). The engineering process is organized under the **Agile Scrum Framework** with **1-week sprint cycles**.

The objective of the project is to engineer a multi-agent platform that takes a startup idea in 2-3 lines and produces a structured startup validation report using live web search and LLM-powered business reasoning.

> **Current documentation scope:** Week 1 and Week 2 (Milestone 1). Details for Weeks 3 to 9 are added to these documents as each sprint is planned.

**Milestone 1 (Week 1-2) in the project SOP:**

1. Study startup validation frameworks, multi-agent design patterns, and web search API integration.
2. Design system architecture, agent roles, orchestration flow, and data models.
3. Develop the startup idea submission interface and structured idea extraction using an LLM.
4. Integrate the Web Search Agent using the Tavily API for live market and competitor data.

The repository is licensed under the [MIT License](../../LICENSE). API keys are kept in `.env` and are never committed.

---

## 2. Agile Internship Cadence & Structure

```
+-----------------------------------------------------------------------------------+
|                       9-WEEK SPRINT CADENCE (45 DAYS)                             |
+-----------------------------------------------------------------------------------+
| Week 1 (Days 01-05) : Sprint 1 - Study, Agent Roles, System Architecture,        |
|                       Submission Design, Tavily Web Search Test (Tasks 1 to 5)    |
| Week 2 (Days 06-10) : Sprint 2 - Idea Submission Interface, LLM Structuring,     |
|                       Web Search Agent                                            |
| Week 3 (Days 11-15) : Sprint 3 - To be planned                                    |
| Week 4 (Days 16-20) : Sprint 4 - To be planned                                    |
| Week 5 (Days 21-25) : Sprint 5 - To be planned                                    |
| Week 6 (Days 26-30) : Sprint 6 - To be planned                                    |
| Week 7 (Days 31-35) : Sprint 7 - To be planned                                    |
| Week 8 (Days 36-40) : Sprint 8 - To be planned                                    |
| Week 9 (Days 41-45) : Sprint 9 - To be planned                                    |
+-----------------------------------------------------------------------------------+
```

The Sprint 1 foundation tasks were due on **12 October 2026**. Calendar dates for each sprint are recorded in the mentor's Excel Sprint Backlog.

### Daily & Weekly Scrum Ceremonies

- **Daily Standup:** short sync covering:
  - What was accomplished yesterday?
  - What will be accomplished today?
  - What blockers or impediments are present?
  - Technical learnings and discoveries.
- **Sprint Planning** (start of each week): Sprint backlog definition from the Product Backlog, task breakdown, capacity planning.
- **Sprint Review & Demo** (end of each week): Demonstration of the working increment to the mentor.
- **Sprint Retrospective** (end of each week): Retrospective analysis (Start Doing, Stop Doing, Continue Doing, Action taken), as in the Retrospection template.

Meeting days and times are set by the team and recorded in the Excel Stand-up and Sprint Backlog sheets.

---

## 3. Sprint-by-Sprint Milestone Summary

| Sprint | Week | Primary Focus Area | Planned Features | Stories | Status |
|:---:|:---:|:---|:---|:---:|:---:|
| **SP-01** | W1 (Days 01-05) | Understanding & Design Foundations | Project understanding notes with sample idea, six agent roles, architecture diagram, submission wireframe and sample structured output, Tavily search test | 5 | Done |
| **SP-02** | W2 (Days 06-10) | Idea Submission & Web Search | Submission form, LLM structuring into a validated idea object, review screen, Web Search Agent with query generation, filtering, and source URLs | 7 | Done |
| **SP-03** | W3 (Days 11-15) | To be planned | - | - | - |
| **SP-04** | W4 (Days 16-20) | To be planned | - | - | - |
| **SP-05** | W5 (Days 21-25) | To be planned | - | - | - |
| **SP-06** | W6 (Days 26-30) | To be planned | - | - | - |
| **SP-07** | W7 (Days 31-35) | To be planned | - | - | - |
| **SP-08** | W8 (Days 36-40) | To be planned | - | - | - |
| **SP-09** | W9 (Days 41-45) | To be planned | - | - | - |
| **TOTAL** | **9 Wks** | **Full Platform Delivery** | Weeks 1-2 planned so far; remaining weeks to be added | **12 so far** | **5 of 12 done** |

---

## 4. Documentation Index

The Agile documentation suite is organized across the following documents:

| Document | Contents |
|:---|:---|
| [Product Backlog (`PRODUCT_BACKLOG.md`)](./PRODUCT_BACKLOG.md) | Product vision, personas, user stories with MoSCoW prioritization, dependencies, and Definition of Done (DoD). |
| [Sprint Plans (`SPRINT_PLANS_W01_TO_W02.md`)](./SPRINT_PLANS_W01_TO_W02.md) | Sprint goals, committed stories, task breakdowns, sprint reviews, and demo notes. Currently covers Week 1 and Week 2; later weeks are added as they are planned. |
| [Daily Standup Logs (`DAILY_STANDUP_LOGS.md`)](./DAILY_STANDUP_LOGS.md) | Daily log entries documenting tasks, impediments, and action taken. |
| [Agile Metrics & Retrospective (`RETROSPECTIVE_AND_METRICS.md`)](./RETROSPECTIVE_AND_METRICS.md) | Stories planned versus done, test counts, defect summary, and sprint retrospectives. |
| [Mentor Excel Templates (`templates/`)](./templates) | `Agile_Template` (Product Backlog, Sprint Backlog, Stand-up, Retrospection), `Unit_Test_Plan`, and `Defect_Tracker`. |

---

## 5. Team Roles & RACI Matrix

| Role | Responsibility |
|:---|:---|
| **Intern / Development Team** | Design, backend APIs, LLM structuring, Web Search Agent, UI, testing, and documentation. Team members: Akash Pingale, Prathamesh Shinde (add remaining members). |
| **Internship Mentor** | Task assignment, review of deliverables, sprint guidance, and technical obstacle escalation. Mentor contact: Subramanyam. |
| **Product Owner (Mentor / Team)** | User story requirement validation and acceptance of each sprint increment. |
| **Scrum Master (rotating)** | Sprint ceremony facilitation, tracking of stories done, impediment removal, and keeping the Excel sheets and these documents up to date. |

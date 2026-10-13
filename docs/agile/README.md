# Agile Framework: Milestone 1 (Week 1 and Week 2)

## Project Title
**Development of AI Based Startup Idea Validator with Market Analysis Assistance**

---

## 1. Scope of This Repository

This repository covers **Milestone 1 (Week 1-2, about 10 hours)** of the project SOP. Later milestones are outside the scope of this repository for now.

Milestone 1 in the SOP:
1. Study startup validation frameworks, multi-agent design patterns, and web search API integration.
2. Design system architecture, agent roles, orchestration flow, and data models.
3. Develop the startup idea submission interface and structured idea extraction using an LLM.
4. Integrate the Web Search Agent using the Tavily API for live market and competitor data.

The team follows **Agile Scrum** with **1-week sprints**. The mentor-provided Excel templates (Product Backlog, Sprint Backlog, Stand-up, Retrospection, Defect Tracker, Unit Test Plan) are stored in [`templates/`](./templates). The Markdown documents in this folder summarize the same information for GitHub.

---

## 2. Sprint Cadence

```
+-----------------------------------------------------------------------------------+
|                       MILESTONE 1 (WEEK 1-2) SPRINT CADENCE                       |
+-----------------------------------------------------------------------------------+
| Sprint 1 (Week 1) : Foundations - Tasks 1 to 5 (study, agents, architecture,     |
|                     submission design, Tavily test)                               |
| Sprint 2 (Week 2) : Implementation - Idea submission interface, LLM structuring, |
|                     Web Search Agent                                              |
+-----------------------------------------------------------------------------------+
```

The Sprint 1 foundation tasks were due on **12 October 2026**. Calendar dates for each sprint are recorded in the Excel Sprint Backlog.

### Scrum Ceremonies

- **Daily Stand-up**: what was done, what is planned, impediments. Logged in [`DAILY_STANDUP_LOGS.md`](./DAILY_STANDUP_LOGS.md).
- **Sprint Planning**: pick stories from the Product Backlog and break them into tasks.
- **Sprint Review & Demo**: show the working increment to the mentor.
- **Sprint Retrospective**: Start Doing / Stop Doing / Continue Doing, as in the Retrospection template.

---

## 3. Sprint Summary

| Sprint | Week | Primary Focus | Status |
|:---:|:---:|:---|:---:|
| **SP-01** | W1 | Understand project, multi-agent design, architecture, submission design, Tavily test | Done |
| **SP-02** | W2 | Idea submission interface, LLM structuring, Web Search Agent | Planned |

---

## 4. Documentation Index

1. [**Product Backlog (`PRODUCT_BACKLOG.md`)**](./PRODUCT_BACKLOG.md): vision, personas, Definition of Done, user stories with MoSCoW priority.
2. [**Sprint Plans (`SPRINT_PLANS_W01_TO_W02.md`)**](./SPRINT_PLANS_W01_TO_W02.md): goals, stories, tasks, review notes for both sprints.
3. [**Daily Stand-up Logs (`DAILY_STANDUP_LOGS.md`)**](./DAILY_STANDUP_LOGS.md): stand-up entries.
4. [**Retrospective & Metrics (`RETROSPECTIVE_AND_METRICS.md`)**](./RETROSPECTIVE_AND_METRICS.md): metrics, defects, retrospectives.
5. [**Excel templates (`templates/`)**](./templates): `Agile_Template`, `Unit_Test_Plan`, `Defect_Tracker`.

---

## 5. Team Roles

| Role | Responsibility |
|:---|:---|
| **Interns (Development Team)** | Design, implementation, testing, documentation. Team members: Akash Pingale, Prathamesh Shinde (add remaining members). |
| **Mentor** | Task assignment, review of deliverables, guidance. Mentor contact: Subramanyam. |
| **Scrum Master (rotating)** | Runs ceremonies, keeps the Excel sheets and these documents up to date. |

---

## 6. Repository Rules

- License: **MIT** (see [`LICENSE`](../../LICENSE)).
- Each sprint updates the Excel templates and the matching Markdown document.
- Secrets such as API keys live only in `.env` and are never committed. Use `.env.example` for placeholders.
- Work is merged through pull requests reviewed by a teammate.

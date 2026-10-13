# Agile Sprint Plans (Week 01 to Week 02)

## Project Title
**Development of AI Based Startup Idea Validator with Market Analysis Assistance**

---

## Sprint Overview Summary

| Sprint | Week | Milestone | Primary Theme | Stories Planned | Stories Done |
|:---:|:---:|:---:|:---|:---:|:---:|
| **Sprint 1** | Week 1 | M1 | Foundations: understanding, agents, architecture, submission design, search test | 5 | 5 |
| **Sprint 2** | Week 2 | M1 | Idea submission module and Web Search Agent | 7 | - |

Story IDs refer to [`PRODUCT_BACKLOG.md`](./PRODUCT_BACKLOG.md). The last column is filled in at each Sprint Review.

---

## Sprint 1: Foundations (Tasks 1-5)
**Duration**: Week 1
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

Repository set-up (MIT license, Agile documentation, folder layout, test scaffold) was also completed in this sprint.

### Sprint 1 Review & Demo
- **Demoed**: Task documents, wireframe, and a live Tavily run with readable output saved to `src/web_search/output/`.
- **Mentor feedback**: to be recorded by the team.

---

## Sprint 2: Idea Submission Module & Web Search Agent
**Duration**: Week 2
**Sprint Goal**: A founder can submit an idea, see it converted to a structured object, and the Web Search Agent returns sourced results for it.

### Committed User Stories
- `US-SUB-01`: Submission form.
- `US-SUB-02`: LLM structuring with schema validation (`models/startup_idea.py`).
- `US-SUB-03`: Review and confirm screen.
- `US-WEB-01`: Query generation from the structured idea.
- `US-WEB-02`: Web Search Agent on top of `utils/search_client.py`.
- `US-WEB-03`: Result de-duplication and relevance filtering.
- `US-WEB-04`: Source URL kept with every result.

### Sprint 2 Review & Demo
- To be filled in at the Sprint Review. This closes Milestone 1.

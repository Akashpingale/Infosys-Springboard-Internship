# Infosys-Springboard-Internship

Project repository for the Infosys Springboard Internship: **AI Based Startup Idea Validator with Market Analysis Assistance**. Created for team collaboration and development.

## Repository structure

```
Infosys-Springboard-Internship/
|-- README.md
|-- LICENSE
|-- .gitignore
|-- docs/                          Project documentation (read in order)
|   |-- 01_project_understanding.md
|   |-- 02_multi_agent_system.md
|   |-- 03_system_architecture.md
|   |-- 04_startup_idea_submission_module.md
|   |-- 05_web_search_api.md
|   |-- 05_sample_output.md
|   |-- agile/                     Scrum docs for Milestone 1
|   |   |-- README.md
|   |   |-- PRODUCT_BACKLOG.md
|   |   |-- SPRINT_PLANS_W01_TO_W02.md
|   |   |-- DAILY_STANDUP_LOGS.md
|   |   |-- RETROSPECTIVE_AND_METRICS.md
|   |   `-- templates/             Mentor-provided Excel sheets
|   |       |-- Agile_Template_v0.1.xlsx
|   |       |-- Defect_Tracker_Template_v0.1.xlsx
|   |       `-- Unit_Test_Plan_v0.1.xlsx
|   `-- assets/                    Images and wireframes used by the docs
|       |-- task4_wireframe.html
|       `-- task4_wireframe.png
`-- src/                           Source code
    |-- README.md
    `-- web_search/                Tavily web search API test
        |-- .env.example           Copy to .env and add your key
        |-- requirements.txt
        |-- search_test.py
        `-- output/                Generated results
            |-- search_results.json
            |-- search_results.md
            `-- screenshots/
```

## Documentation

| # | Document | Topic |
|---|---|---|
| 01 | [Project understanding](docs/01_project_understanding.md) | Task 1: Project understanding and startup validation |
| 02 | [Multi-agent system](docs/02_multi_agent_system.md) | Task 2: Study multi-agent AI systems |
| 03 | [System architecture](docs/03_system_architecture.md) | Task 3: Design the system architecture |
| 04 | [Startup idea submission module](docs/04_startup_idea_submission_module.md) | Task 4: Idea submission UI wireframe and LLM structuring |
| 05 | [Web search API](docs/05_web_search_api.md) | Task 5: Web search API integration ([sample output](docs/05_sample_output.md)) |

Agile / Scrum tracking (backlog, sprints, stand-ups, retrospectives): [docs/agile/README.md](docs/agile/README.md)

## Quick start

See [src/README.md](src/README.md) for setup and running the web search test.



flowchart TD
    U[User] --> UI[Streamlit User Interface]
    UI --> B[Python Backend]
    B --> V[Validate and Structure Startup Idea]
    V --> O[Workflow Orchestrator]

    O --> W[Web Search Agent]
    W --> S[Web Search API]
    S --> R[Structured Search Results]

    R --> M[Market Analysis Agent]
    V --> M
    R --> C[Competitor Analysis Agent]
    V --> C

    M --> SW[SWOT and Risk Agent]
    C --> SW

    M --> MVP[MVP Recommendation Agent]
    C --> MVP
    SW --> MVP

    M --> L[LLM Service]
    C --> L
    SW --> L
    MVP --> L

    L --> RG[Report Generation Agent]
    M --> RG
    C --> RG
    SW --> RG
    MVP --> RG

    RG --> B
    B --> OUT[Display and Download Final Report]
    OUT --> UI

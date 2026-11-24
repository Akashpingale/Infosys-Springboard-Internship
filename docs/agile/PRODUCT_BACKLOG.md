Agile Product Backlog & Epic Breakdown
Project Title
Development of AI Based Startup Idea Validator with Market Analysis Assistance
---
1. Product Vision & Target Personas
Product Vision
To give early-stage founders a fast, evidence-based first opinion on a startup idea. From a short description, a multi-agent platform structures the idea with an LLM, retrieves live market and competitor information through web search, analyses the market, the competitors, the strengths, weaknesses and risks, recommends an MVP and a go-to-market plan, answers follow-up questions, and produces a shareable validation report. Every claim carries numbered sources or an honest label (sourced, AI interpretation, from your idea, or assumption).
Target Personas
First-time Founder / Student Entrepreneur: has an idea and limited time or budget for market research, and needs a clear, sourced first opinion.
Early-stage Founder with a Prototype: wants to compare the idea against competitors, find gaps, and decide what to build first.
Mentor / Incubator Reviewer: wants a consistent, source-backed starting point and a report that can be checked claim by claim.
---
2. Definition of Done (DoD)
A user story is Done only when the applicable criteria are met:
[x] Code Complete: implemented, runs locally, and reviewed according to the team's workflow.
[x] Testing Standards: automated tests are written with `pytest` (back end), `vitest` (front end) and Playwright (browser); the suites pass; no test calls a real provider.
[x] Security: API keys are read from environment variables and are not in the working tree (secret scan: 0 hits on 18 Nov 2026). One key committed on 11 Oct 2026 remains in Git history and must be revoked (Section 5).
[x] Documentation: the relevant files in `docs/` and the Agile templates are updated.
[x] Demo-ready: the increment can be shown during the Sprint Review.
Stories marked † are verified with fake providers only; their live checks have not been run (Section 5).
---
3. Product Epics & Story Cards
The Sprint column shows the planned sprint, and the actual sprint where it differed (planned → actual).
---
Epic 1: Foundation & Research (Sprint 1)
Story ID	Story Title	User Story Description	Priority	Sprint	Status
US-FND-01	Project Understanding Notes	As a team member, I want notes on startup validation and one sample idea so that the team shares the same understanding.	MUST	1	DONE
US-FND-02	Agent Roles & Responsibilities	As a team member, I want agent roles and responsibilities defined so that each module has a clear responsibility.	MUST	1	DONE
US-FND-03	System Architecture & Information Flow	As a developer, I want a system architecture and information flow so that implementation follows one design.	MUST	1	DONE
US-FND-04	Submission Wireframe & Output Format	As a founder, I want a submission-module wireframe and structured output format so that an idea can be represented consistently.	MUST	1	DONE
US-FND-05	Tavily Web Search Test	As a developer, I want a working Tavily web-search test so that the project can retrieve live information.	MUST	1	DONE
---
Epic 2: Startup Idea Submission & Structured Extraction (Sprint 2)
Story ID	Story Title	User Story Description	Priority	Sprint	Status
US-SUB-01	Idea Submission Form	As a founder, I want to submit an idea description, industry, target customers, and relevant details through a form so that the backend receives the required input.	MUST	2	DONE
US-SUB-02	LLM Structured Idea Extraction	As a founder, I want my free-text idea converted by an LLM into a structured object containing the problem, solution, target customers, industry, and key features.	MUST	2	DONE
US-SUB-03	Input & Response Error Handling	As a founder, I want missing inputs and invalid LLM responses handled clearly so that failed requests do not break the workflow.	MUST	2	DONE
US-SUB-04	UI-to-Backend Connection	As a founder, I want the submission interface connected to the backend so that I can run the initial validation workflow from the UI.	MUST	2	DONE
US-SUB-05	Review & Edit Extracted Idea	As a founder, I want to review and edit the extracted idea before analysis agents run. Delivered by the React review screen (US-WEB2-03).	SHOULD	2 → 7	DONE
---
Epic 3: Web Search Agent & Multi-Agent Orchestration (Sprint 2)
Story ID	Story Title	User Story Description	Priority	Sprint	Status
US-WEB-01	Search Query Generation	As the pipeline, I want search queries generated from the structured idea so that retrieval is relevant to the startup's market.	MUST	2	DONE
US-WEB-02	Web Search Agent (Tavily)	As the pipeline, I want Tavily search wrapped by the Web Search Agent to return readable result information, including titles, snippets, scores, and URLs where available.	MUST	2	DONE
US-WEB-03	Safe Search Error Handling	As the pipeline, I want API errors and unexpected search responses handled so that search failures are reported safely.	MUST	2	DONE
US-WEB-04	Source URL Linking	As a reader, I want search results linked to their source URLs so that I can inspect the original information.	MUST	2	DONE
US-WEB-05	Duplicate & Low-Relevance Filtering	As an analyst agent, I want duplicate and low-relevance results filtered so that downstream analysis receives cleaner evidence. URL de-duplication is done; filtering by relevance score is not built.	SHOULD	2	IN PROGRESS
US-ORC-01	Basic Orchestration Pipeline	As a developer, I want a basic orchestration function to coordinate structured extraction and web search so that the initial workflow can run in sequence.	MUST	2	DONE
US-ORC-02	Schemas & Component Boundaries	As a developer, I want defined schemas and component boundaries so that structured ideas and search results can be passed consistently between components.	MUST	2	DONE
US-ORC-03	Full Specialist-Agent Integration	As a developer, I want the Market Analysis, Competitor Analysis, SWOT/Risk, MVP Recommendation, and Report Generation agents integrated into the orchestrator. These agents, and Go-to-Market, are all in the pipeline: Market and Competitor in Milestone 2, SWOT/Risk, MVP and Go-to-Market in Milestone 3, and Report in Milestone 4.	SHOULD	2 → 8	DONE
---
Epic 4: Market Opportunity & Competitor Analysis Agents (Sprints 3-4)
Story ID	Story Title	User Story Description	Priority	Sprint	Status
US-MKT-01	Market Size Estimation	As an analyst, I want market size estimated from search results so that opportunity magnitude is quantified.	MUST	3	DONE
US-MKT-02	Growth Trend Identification	As an analyst, I want growth trends identified from market data so that future potential is assessed.	MUST	3	DONE
US-MKT-03	Opportunity Scoring	As an analyst, I want market opportunity scored on size, growth, and competition so that I have one quantified assessment.	MUST	3	DONE
US-MKT-04	Numbered Market Citations	As a reader, I want every market claim backed by numbered citations so that findings are verifiable.	MUST	3	DONE
US-MKT-05	Market-Size Targeted Searches	As a developer, I want market-size-specific queries generated and run so that the agent has targeted evidence.	SHOULD	3	DONE
US-MKT-06	Market Agent Test Suite	As a developer, I want automated tests for market analysis with mocked LLM and search so that the stage is reliable.	MUST	3	DONE
US-COMP-01	Competitor Identification	As an analyst, I want competitors identified from search results so that the competitive landscape is mapped.	MUST	4	DONE
US-COMP-02	Feature Comparison	As an analyst, I want competitor features compared against the proposed solution so that gaps and overlaps are visible.	MUST	4	DONE
US-COMP-03	Targeted Competitor Searches	As an analyst, I want targeted competitor searches run so that comparisons rest on current information.	SHOULD	4	DONE
US-COMP-04	Cited Competitor Claims	As a reader, I want every competitor claim cited with source numbers so that comparisons are verifiable.	MUST	4	DONE
US-COMP-05	Evidence Integrity Checks	As a developer, I want integrity checks for missing citations, broken URLs, and unreferenced evidence so that quality is enforced.	MUST	4	DONE
US-COMP-06	Analysis Display in Streamlit	As a founder, I want market and competitor analysis displayed in the Streamlit UI so that I can review all findings in one place.	MUST	4	DONE
US-COMP-07	Multi-Domain Test Coverage	As a developer, I want automated tests covering multiple domains (AgriTech, FinTech, FoodTech) so that the analysis generalizes.	MUST	4	DONE
---
Epic 5: Strategy Agents & Startup Advisor (Sprints 5-6)
Story ID	Story Title	User Story Description	Priority	Sprint	Status
US-SWOT-01	SWOT Quadrants	As a founder, I want 3-5 points per SWOT quadrant derived from validation findings so that I see strategic positioning.	MUST	5	DONE †
US-SWOT-02	SWOT Basis Labels	As a founder, I want each SWOT point labeled as sourced, interpreted, or assumed so that I know its basis.	MUST	5	DONE †
US-RISK-01	Risk Identification	As a founder, I want 6-10 risks identified with likelihood and impact scores so that I can prioritize mitigation.	MUST	5	DONE †
US-RISK-02	Severity Scoring	As a founder, I want severity computed from likelihood × impact so that risks are ranked objectively.	MUST	5	DONE †
US-STRAT-01	Numbered Findings Digest	As a developer, I want strategy prompts to work from a numbered digest of findings so that reasoning is traceable.	MUST	5	DONE †
US-MVP-01	MVP Feature Ranking	As a founder, I want MVP features ranked by impact × effort so that I know what to build first.	MUST	6	DONE †
US-MVP-02	First-Release Scope	As a founder, I want features split into first release and later based on team capacity so that scope is realistic.	MUST	6	DONE †
US-MVP-03	MVP Success Metrics	As a founder, I want success metrics defined for MVP validation so that I know what to measure.	MUST	6	DONE †
US-GTM-01	Positioning Statement	As a founder, I want a positioning statement derived from differentiation points so that my message is clear.	MUST	6	DONE †
US-GTM-02	Acquisition Channel Ranking	As a founder, I want acquisition channels ranked by suitability with a first experiment each so that I know where to start.	MUST	6	DONE †
US-GTM-03	Three-Phase Launch Plan	As a founder, I want a three-phase launch plan (early adopters, scaling, growth) so that I have a roadmap.	MUST	6	DONE †
US-ADV-01	Cited Advisor Answers	As a founder, I want to ask questions about my validation results and get answers with citations.	MUST	6	DONE †
US-ADV-02	Off-Topic Refusal	As a founder, I want the advisor to refuse questions unrelated to my validation so that answers stay relevant.	MUST	6	DONE †
US-ADV-03	Question Limits	As a founder, I want question length and count limited so that the system stays responsive.	MUST	6	DONE †
US-ADV-04	Conversation History	As a developer, I want conversation history sent with each question so that follow-up questions work naturally.	SHOULD	6	DONE †
US-ADV-05	Suggested Questions	As a founder, I want pre-written question suggestions so that I know what to ask.	SHOULD	6	DONE †
US-ADV-06	Clear Conversation	As a founder, I want to clear conversation history to regain question quota.	SHOULD	6	DONE †
---
Epic 6: React Interface & Background Runs (Sprint 7)
Story ID	Story Title	User Story Description	Priority	Sprint	Status
US-WEB2-01	Background Runs API	As a developer, I want background runs, run history and a metadata route added to the API so that a browser client can start a validation, poll it and reopen it later, without changing any existing route.	MUST	7	DONE
US-WEB2-02	Limit-Aware Submission Form	As a founder, I want a submission form that states every limit the backend enforces, so that I am not rejected after submitting.	MUST	7	DONE
US-WEB2-03	Idea Review Screen	As a founder, I want to review and correct the extracted idea before the expensive stages run. (closes the intent of US-SUB-05)	MUST	7	DONE
US-WEB2-04	Stage Progress & Cancel	As a founder, I want to watch the four stages progress and to cancel a run, instead of watching one spinner for two minutes.	MUST	7	DONE
US-WEB2-05	Claim Sources & Source Drawer	As a founder, I want every claim to carry the sources it rests on, and a drawer that shows what rests on a given source.	MUST	7	DONE
US-WEB2-06	Result Tabs	As a founder, I want the market analysis, the competitor comparison, the sources and the run's own record on separate tabs so that one screen has one job.	MUST	7	DONE
US-WEB2-07	Export as Markdown, JSON or PDF	As a founder, I want to export a result as Markdown, JSON or PDF so that I can share it.	SHOULD	7	DONE
US-WEB2-08	Run History	As a founder, I want my past validations listed so that I can reopen, rename or delete one.	SHOULD	7	DONE
US-WEB2-09	Provider Status Screen	As a founder, I want to see whether the backend and each provider are configured, without any key being shown.	SHOULD	7	DONE
US-WEB2-10	Responsive Design	As a reader using a phone, a tablet or a desktop, I want every screen to work at 390, 820 and 1440 px with targets I can hit.	MUST	7	DONE
US-WEB2-11	Accessibility	As a reader using a keyboard or a screen reader, I want no serious or critical accessibility violation on any screen. Result: 0 serious or critical axe violations (see US-TEST-07).	MUST	7	DONE
US-WEB2-12	Provider-Free Automated Tests	As a developer, I want the new interface covered by automated tests that never call a provider, so that the suite can run on any machine without credits.	MUST	7	DONE
US-WEB2-13	Live Parity Run	As a team member, I want one real validation run started from the new interface so that parity with Streamlit is confirmed. Five validations were run live from the React interface (3 complete, 2 partial, one of them because of a Gemini quota error).	MUST	7	DONE
US-WEB2-14	Streamlit Retained	As a team member, I want the Streamlit interface kept working until that parity is confirmed.	MUST	7	DONE
---
Epic 7: Report Generation & System Optimization (Sprint 8)
Story ID	Story Title	User Story Description	Priority	Sprint	Status
US-REP-01	Validation Report (PDF, Markdown, JSON)	As a founder, I want a 16-section validation report (PDF, Markdown, JSON) so that I can share findings professionally.	MUST	8	DONE †
US-REP-02	AI Executive Summary	As a founder, I want an executive summary written by AI so that readers get the key points first.	MUST	8	DONE †
US-REP-03	Report Consistency Checks	As a developer, I want 12 consistency checks (citation integrity, figure accuracy, bibliography) so that report quality is enforced.	MUST	8	DONE †
US-REP-04	Report Download in React	As a founder, I want report downloadable from the React interface as PDF, Markdown, or JSON.	MUST	8	DONE †
US-OPT-01	Query Profile v2	As a developer, I want query profile v2 with improved query design and evidence filtering.	SHOULD	8	DONE †
US-OPT-02	Prompt Profile v2	As a developer, I want prompt profile v2 with enhanced reasoning rules and matrix consistency check.	SHOULD	8	DONE †
US-OPT-03	Parallel Search	As a developer, I want parallel search execution (configurable 1-8 concurrent) so that research is faster.	SHOULD	8	DONE †
---
Epic 8: Testing, Documentation & Delivery (Sprints 2 and 9)
Story ID	Story Title	User Story Description	Priority	Sprint	Status
US-TEST-01	Workflow Test Suite	As a developer, I want automated tests for successful workflows, missing inputs, API errors, and unexpected responses so that the initial workflow is reliable.	MUST	2	DONE
US-TEST-02	Multi-Industry Runs	As a developer, I want to run the workflow against at least three startup ideas from different industries so that basic integration is verified.	MUST	2	DONE
US-TEST-03	Setup Documentation	As a developer, I want setup instructions, dependencies, environment variables, and execution steps documented so that another team member can run the project.	MUST	2	DONE
US-TEST-04	Publish to GitHub main	As a team member, I want the completed code and documentation published to the team's GitHub main branch so that the team has a shared, up-to-date version.	MUST	2	DONE
US-TEST-05	Backend Test Suite	As a developer, I want automated backend tests that cover all agents and routes, so that regressions are caught. Result: 2,956 passed on 18 Nov 2026; 2,961 passed and 4 skipped on a re-run on 24 Nov 2026.	MUST	9	DONE
US-TEST-06	Front-End & Browser Tests	As a developer, I want front-end unit tests and browser tests, so that the interface stays reliable. Result on 18 Nov 2026: 552 front-end tests and 369 browser tests (Chromium, 390, 820 and 1440 px) passed; one browser test is intermittent.	MUST	9	DONE
US-TEST-07	Accessibility Testing	As a team member, I want accessibility testing, so that no screen has a serious or critical violation. Result: 0 serious or critical axe violations on 41 screens at three widths; the report page has no axe check yet.	MUST	9	DONE
US-DOC-01	Technical Documentation	As a team member, I want comprehensive technical documentation covering architecture, agents, API, and configuration.	MUST	9	DONE
US-DOC-02	User Guide & Demo Runbook	As a user, I want a user guide with setup, running, and troubleshooting instructions.	MUST	9	DONE
US-DOC-03	Project Report	As a reviewer, I want a project report documenting objectives, methodology, results, and learnings.	MUST	9	DONE
---
4. Backlog Summary
Epic	Stories	DONE	IN PROGRESS
Epic 1: Foundation & Research	5	5	0
Epic 2: Startup Idea Submission & Structured Extraction	5	5	0
Epic 3: Web Search Agent & Multi-Agent Orchestration	8	7	1
Epic 4: Market Opportunity & Competitor Analysis Agents	13	13	0
Epic 5: Strategy Agents & Startup Advisor	17	17	0
Epic 6: React Interface & Background Runs	14	14	0
Epic 7: Report Generation & System Optimization	7	7	0
Epic 8: Testing, Documentation & Delivery	10	10	0
Total	79	78	1
Measured results (docs/15_final_test_report.md)
Check	Result
Backend tests (`python -m pytest`)	2,956 passed on 18 Nov 2026; re-run on 24 Nov 2026: 2,961 passed, 4 skipped
Front-end tests (`npm test`)	552 passed in 42 files
Browser tests (Playwright, Chromium, 390 / 820 / 1440 px)	369 passed
Accessibility (axe)	0 serious or critical violations on 41 screens at three widths
Secret scan of the working tree	0 hits in 848 text files
All automated results use fake providers. No live provider check was run for Milestones 3 and 4.
---
5. Open Items
Item	Detail
US-WEB-05	Duplicate results are removed by URL, but results are not filtered by relevance score.
Live checks (†)	Live checks L-1 to L-8 for the strategy agents, the Advisor and the report have not been run, so those stories are verified with fake providers only (`docs/15`, section 4).
Exposed API key	A Tavily key committed on 11 Oct 2026 (commit `50ea1ae`) is still readable in Git history. It must be revoked and replaced; the rotation is not yet confirmed.
Report page tests	The report page has no axe check, keyboard check or Playwright journey.
Intermittent browser test	`keyboard-m3` "advisor-full does not animate" at 1440 px failed once and passed on re-runs; the root cause is unknown.
Coverage	Code coverage has not been measured.
Light theme	The tokens exist, but the interface cannot switch to it.
Streamlit	The Streamlit interface is kept next to the React interface (US-WEB2-14).
---
6. Notes for Backlog Maintenance
Keep a story DONE only when its Definition of Done is met; otherwise change it to IN PROGRESS.
Story IDs match the `US ID` column of the mentor's `Agile_Template_v0.1.xlsx` (Product Backlog and Sprint Backlog sheets).
Keep all API keys in environment variables; never commit a real `.env` file.
Re-run the test commands in Section 4 before each submission and update the numbers if they change.

# 45-Day Daily Standup Logs (9-Week Internship)

## Project Title
**Development of AI Based Startup Idea Validator with Market Analysis Assistance**

These entries follow the mentor's stand-up format: **Sprint, Day, Impediments, and Action Taken**, with **Today** included for readability. Each entry is taken from the project's records: Git history, test reports, saved live runs and the team's earlier Milestone 1 stand-up log. A working day with no record is listed in the calendar below as "No record" and has no entry; it is never filled with an assumed one.

## Daily Standup Structure
Each logged working day includes:
1. **Today**
2. **Impediments**
3. **Action Taken**

---

## 1. Working-Day Calendar and Holidays

The internship has **45 working days**, from **Day 01 (Wed 7 Oct 2026)** to **Day 45 (Sun 6 Dec 2026)**. These dates are holidays and are not counted as working days:

| Month | Holidays |
|:---|:---|
| October 2026 | 11 (Sun), 17 (Sat), 18 (Sun), 20 (Tue), 21 (Wed), 24 (Sat), 25 (Sun), 31 (Sat) |
| November 2026 | 1 (Sun), 7 (Sat), 8 (Sun), 14 (Sat), 15 (Sun), 20 (Fri), 21 (Sat), 22 (Sun) |

No holidays are listed after 22 Nov, so Day 37, Day 38, Day 44 and Day 45 fall on a weekend (28 Nov, 29 Nov, 5 Dec and 6 Dec). Work done on a holiday is logged under the heading **Holiday**.

| Week | Sprint | Days | Dates | Logged | No record |
|:---:|:---:|:---:|:---|:---|:---|
| 1 | Sprint 1 | 01-05 | 7, 8, 9, 10, 12 Oct | Day 03, 04, 05 | Day 01, 02 |
| 2 | Sprint 2 | 06-10 | 13, 14, 15, 16, 19 Oct | Day 06, 07, 08, 09 | Day 10 |
| 3 | Sprint 3 | 11-15 | 22, 23, 26, 27, 28 Oct | Day 14, 15 | Day 11, 12, 13 |
| 4 | Sprint 4 | 16-20 | 29, 30 Oct, 2, 3, 4 Nov | - | Day 16-20 |
| 5 | Sprint 5 | 21-25 | 5, 6, 9, 10, 11 Nov | - | Day 21-25 |
| 6 | Sprint 6 | 26-30 | 12, 13, 16, 17, 18 Nov | Day 27, 28, 30 | Day 26, 29 |
| 7 | Sprint 7 | 31-35 | 19, 23, 24, 25, 26 Nov | Day 31, 33, 34 | Day 32 |
| 8 | Sprint 8 | 36-40 | 27, 28, 29, 30 Nov, 1 Dec | upcoming | upcoming |
| 9 | Sprint 9 | 41-45 | 2, 3, 4, 5, 6 Dec | upcoming | upcoming |

Entries are placed by the real date. Some work was finished earlier than the sprint that planned it, so an entry can sit in an earlier week than its sprint in `SPRINT_PLANS_W01_TO_W09.md`. For example, the React interface (Sprint 7 in the plan) and Milestone 4 (Sprint 8 and 9 in the plan) were built before their planned weeks. Each entry names the backlog stories it relates to.

---

## 2. Daily Log

### Week 1 (Sprint 1: Foundations & Web Search API Exploration)

No record: Day 01 (7 Oct) and Day 02 (8 Oct).

#### Day 03 — 2026-10-09 (Fri)
- **Today**: Created the team repository (initial commit).
- **Impediments**: None recorded.
- **Action Taken**: Pushed the initial commit to the team's GitHub repository.

#### Day 04 — 2026-10-10 (Sat)
- **Today**: Corrected the capitalization of the project title in the repository (Anil Kumar).
- **Impediments**: None recorded.
- **Action Taken**: Pushed the fix to `main`.

#### Holiday — 2026-10-11 (Sun), work done on a holiday
- **Today**: Task 5 (`US-FND-05`): ran `src/web_search/search_test.py` with a live Tavily API key and saved sample search output and screenshots under `src/web_search/output/`. Also added the Task 4 submission-module document (`US-FND-04`), `.gitignore`, `.env.example` and `requirements.txt`.
- **Impediments**: Live web-search testing depends on a valid API key and network/API availability. A `.env` file with the Tavily key was committed (commit `50ea1ae`); the file is no longer tracked, but the key must still be revoked.
- **Action Taken**: Configured the API key through the local environment and saved the returned results and screenshots as evidence of the web-search test.

#### Day 05 — 2026-10-12 (Mon), Sprint 1 foundation tasks due
- **Today**: Documents for Task 1 (`US-FND-01`), Task 3 (`US-FND-03`) and Task 4 (`US-FND-04`) were committed, by Anil Kumar, Kanukula Devi and Chandana B. Reviewed and organized the Milestone 1 documentation and repository structure.
- **Impediments**: Documentation paths and filenames needed to remain consistent as the repository structure was organized.
- **Action Taken**: Reviewed the documentation and updated references and structure where needed, keeping the existing Milestone 1 materials.

---

### Week 2 (Sprint 2: Idea Submission, Structured Extraction & Workflow Integration)

No record: Day 10 (19 Oct).

#### Day 06 — 2026-10-13 (Tue)
- **Today**: Completed the agent roles document (`US-FND-02`) and the rest of the Milestone 1 documentation. Worked on the implementation foundation: configuration, request and response models, application setup, and the LLM and web-search clients with error handling.
- **Impediments**: The implementation needed consistent data contracts and predictable error handling across API and external-service boundaries.
- **Action Taken**: Organized the implementation around explicit schemas, configuration and application error handling so extraction, search and orchestration could be tested independently.

#### Day 07 — 2026-10-14 (Wed)
- **Today**: Implemented and tested LLM-based structured idea extraction, the Web Search Agent, the API routes and basic orchestration (`US-SUB-02`, `US-WEB-01`, `US-WEB-02`, `US-ORC-01`). Ran the workflow live on four ideas (AgriTech, FinTech, FoodTech, HealthTech) and saved the outputs in `docs/test_runs/`. The latest full test run reached **293 passing tests**.
- **Impediments**: The LLM service returned a transient HTTP 503 during a live run; the model `gemini-3.6-flash` returned 503 on every attempt; the Gemini client was closed mid-request.
- **Action Taken**: Added retry and error handling, switched the model to `gemini-3-flash-preview`, and kept the client open for the whole call. A later live run recovered from the transient error and completed extraction and web search (`docs/07_pipeline_test_report.md`, section 5).

#### Day 08 — 2026-10-15 (Thu)
- **Today**: Committed Milestone 1 Tasks 1-5. Continued the frontend integration and reviewed the startup idea submission experience (`US-SUB-04`).
- **Impediments**: Live LLM and search requests take longer than mocked tests; the frontend presentation needed alignment and usability improvements.
- **Action Taken**: Verified the live workflow against several sample ideas, captured demo evidence, and refined the frontend without changing the API contracts.

#### Day 09 — 2026-10-16 (Fri)
- **Today**: Prepared the working solution for demonstration, reviewed UI alignment, and shared a screen recording of the working solution with the mentor. Reviewed GitHub publication status and the remaining repository changes.
- **Impediments**: A laptop technical issue affected participation in the mentor meeting, and the repository needed a careful Git review before all local changes could be published safely.
- **Action Taken**: Joined the meeting from a mobile phone, recorded the working demo and emailed it to the mentor. Continued checking repository status and frontend files before staging or pushing further changes. This closes Milestone 1.

---

### Week 3 (Sprint 3: Market Opportunity Agent)

No record: Day 11 (22 Oct), Day 12 (23 Oct) and Day 13 (26 Oct).

#### Holiday — 2026-10-24 (Sat), work done on a holiday
- **Today**: Ran one live standalone market analysis (`US-MKT-01` to `US-MKT-05`). Extraction took 6.0 s, the two searches returned 11 and 5 results, and the market analysis finished in 109.7 s with 2 segments, 11 sources and 3 broader-market figures. The output is saved in `docs/test_runs_m2/dev_market_agritech_v2.txt`.
- **Impediments**: Gemini returned HTTP 504 after about 90 s on the market call; the default 30 s LLM timeout is too short for that call. The run also showed problems in figure reading, added conclusions, off-topic pain points, conflicting counts and cut-off snippets.
- **Action Taken**: The retry (retry 1 of 2 after 1 s) recovered the call. Each problem was reproduced from the saved output and fixed in `agents/figures.py`, `agents/market_claims.py` and the focused snippets (`docs/08_milestone2_agents.md`, section 5).

#### Day 14 — 2026-10-27 (Tue)
- **Today**: Ran the full pipeline live once for each of three ideas (AgriTech, FinTech, FoodTech) through `scripts/run_live_m2.py` (`US-COMP-01` to `US-COMP-07`). All three finished `complete` in 102.5 s to 159.3 s with no integrity violations.
- **Impediments**: A localhost run showed that the LLM client did not log enough to diagnose an HTTP 400. The live runs went through the script only, so the Markdown report, the API audit fields and the backend time limit did not exist yet.
- **Action Taken**: Added safe logging of the provider message (keys redacted, prompt never echoed). Added the Markdown report export, the audit fields in the API response and the backend time limit afterwards (`docs/09_milestone2_test_report.md`, section 2).

#### Day 15 — 2026-10-28 (Wed)
- **Today**: Ran the pipeline from localhost with the Groq fallback active.
- **Impediments**: In JSON object mode, Groq's competitor reply broke the model three times, and the retry waited 28.8 s for a second Gemini 504 before Groq rejected its own output.
- **Action Taken**: Switched Groq to Structured Outputs with a strict JSON schema, with a repair retry. The fix is tested with fakes; a live re-run is still to do (`docs/08`, section 4.9).

---

### Week 4 (Sprint 4: Competitor Analysis Agent & Integration)

No record: Day 16 to Day 20 (29 Oct to 4 Nov).

---

### Week 5 (Sprint 5: SWOT & Risk Analysis)

No record: Day 21 to Day 25 (5 Nov to 11 Nov).

#### Holiday — 2026-11-08 (Sun), work done on a holiday
- **Today**: Pushed the Milestone 1 and Milestone 2 implementation to `main`. Documented the React interface (`docs/10_ui_design_system.md`, `US-WEB2-01` to `US-WEB2-14`) and recorded the five validations run from it.
- **Impediments**: Two of the five live runs from the React interface ended `partial`; one of them was caused by a Gemini quota error.
- **Action Taken**: Recorded the five runs (three complete, two partial) in `docs/10`, section 9, and kept the Streamlit interface working until parity is confirmed.

---

### Week 6 (Sprint 6: MVP, Go-to-Market & Startup Advisor)

No record: Day 26 (12 Nov) and Day 29 (17 Nov).

#### Day 27 — 2026-11-13 (Fri)
- **Today**: Ran the Milestone 3 front-end, build and browser checks (`US-WEB2-12`): 477 front-end tests and 288 browser tests passed, and axe found 0 serious or critical violations on the 14 new screens and the 27 earlier ones.
- **Impediments**: The ui_v2 screenshot spec (81 tests) was not run in this pass.
- **Action Taken**: Recorded the results in `docs/12_milestone3_test_report.md`.

#### Holiday — 2026-11-14 (Sat), work done on a holiday
- **Today**: Ran the Milestone 3 backend suite (SWOT, Risk, MVP, Go-to-Market and Advisor stories): **2,454 passed**. Scanned the working tree for key-shaped text: 0 hits.
- **Impediments**: Seven bugs found while building and reviewing Milestone 3, for example a strategy job that kept stale warnings and a chat reply built with the wrong `ChatLimits` class.
- **Action Taken**: Fixed all seven, each pinned by a named test (`docs/12`, section 6). Two items stay open: strategy stage keys in the legacy report, and Advisor replies that are not scanned for secrets.

#### Holiday — 2026-11-15 (Sun), work done on a holiday
- **Today**: Committed Milestone 3 to `main` (commit `94ddc9a`).
- **Impediments**: Live checks L-1 to L-5 are not executed; the strategy agents and the Advisor are verified with fake providers only.
- **Action Taken**: Listed the live checks in `docs/12`, section 4, to be run by the founder.

#### Day 28 — 2026-11-16 (Mon)
- **Today**: Ran the Milestone 4 baseline (`US-REP-01` to `US-REP-04`, `US-OPT-01` to `US-OPT-03`).
- **Impediments**: Browser test `keyboard-m3` "advisor-full does not animate" at 1440 px failed once with a 30 s timeout.
- **Action Taken**: It passed on three re-runs alone; the root cause was not found, so it is listed as an intermittent test (`docs/15_final_test_report.md`, section 2.3).

#### Day 30 — 2026-11-18 (Wed)
- **Today**: Measured the final automated results (`US-TEST-05` to `US-TEST-07`): 2,956 backend, 552 front-end and 369 browser tests passed; 0 serious or critical axe violations; 0 secret-scan hits in 848 text files.
- **Impediments**: The end-to-end testing task (T7) and the live verification checkpoint (T8) were skipped; coverage tools were never installed.
- **Action Taken**: Listed everything not executed in `docs/15`, section 5.

---

### Week 7 (Sprint 7: React Interface & Background Runs)

No record: Day 32 (23 Nov).

#### Day 31 — 2026-11-19 (Thu)
- **Today**: Committed Milestone 4 to `main` (commit `ad344bf`): Report Generation Agent, query and prompt profiles v2, parallel search and the final documentation in `docs/final/`.
- **Impediments**: The report page has no axe, keyboard or Playwright check. Live checks L-1 to L-8 are not executed.
- **Action Taken**: Recorded both in `docs/15` as outstanding.

#### Day 33 — 2026-11-24 (Tue)
- **Today**: Compared the agile documents with the mentor's reference repository. Re-ran the full backend suite: **2,961 passed, 4 skipped**. Filled the three mentor Excel templates (Agile, Defect Tracker, Unit Test Plan).
- **Impediments**: The agile documents covered Milestone 1 only, and the Excel templates were empty.
- **Action Taken**: Built the Product Backlog (79 stories), Sprint Backlog, Stand-up, Retrospection, 33 defects and 86 unit-test rows from the repository records.

#### Day 34 — 2026-11-25 (Wed)
- **Today**: Rewrote the agile documents in the reference format: `PRODUCT_BACKLOG.md`, `README.md`, `SPRINT_PLANS_W01_TO_W09.md`, `RETROSPECTIVE_AND_METRICS.md` and this log.
- **Impediments**: Some days have no stand-up record.
- **Action Taken**: Listed those days in the calendar instead of writing entries for them.

---

### Week 8 (Sprint 8: Report Generation & Optimization) and Week 9 (Sprint 9: Final Testing, Documentation & Delivery)

These days are still to come: Day 35 (26 Nov) to Day 45 (6 Dec). Planned work, from `docs/15_final_test_report.md`, section 5:

| Day | Date | Planned focus |
|:---:|:---|:---|
| 35-36 | 26, 27 Nov | Revoke and replace the exposed Tavily key; confirm the other exposed keys are rotated |
| 37-38 | 28, 29 Nov (weekend) | Run live checks L-1 to L-8 with real credits |
| 39-40 | 30 Nov, 1 Dec | Add the report page tests (axe, keyboard, Playwright); install coverage tools and measure |
| 41-43 | 2, 3, 4 Dec | Update the test report and the agile documents with the new results; rehearse the demo runbook |
| 44-45 | 5, 6 Dec (weekend) | Final review and submission |

---

## 3. Next Stand-up Entry

Copy this block for the next working day:

#### Day NN — YYYY-MM-DD
- **Today**:
- **Impediments**:
- **Action Taken**:

# Agile Metrics, Delivery Trajectory & Sprint Retrospectives

## Project Title
**Development of AI Based Startup Idea Validator with Market Analysis Assistance**

Retrospectives use the mentor's `Retrospection` columns: Start Doing, Stop Doing, Continue Doing, Action Taken. Each one is built from the project's recorded test reports, defect tracker and Git history. The same data is in `templates/Agile_Template_v0.1.xlsx` and `templates/Defect_Tracker_Template_v0.1.xlsx`.

---

## 1. Sprint Metrics

Across the 9 sprints, **78 of 79 user stories** were delivered. The team did not estimate story points, so progress is measured in stories, defects and test results.

| Sprint | Week | Stories Planned | Stories Done | Defects Logged | Defects Closed | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **Sprint 1** | Week 1 | 5 | 5 | 1 | 0 | The committed Tavily key is still open |
| **Sprint 2** | Week 2 | 17 | 14 | 5 | 5 | US-SUB-05 moved to Sprint 7, US-ORC-03 to Sprint 8; US-WEB-05 is in progress |
| **Sprint 3** | Week 3 | 6 | 6 | 7 | 7 | Defects came from the first live market run |
| **Sprint 4** | Week 4 | 7 | 7 | 4 | 4 | Defects came from the three-domain live runs |
| **Sprint 5** | Week 5 | 5 | 5 | - | - | Milestone 3 defects are shown under Sprint 6 |
| **Sprint 6** | Week 6 | 12 | 12 | 9 | 7 | Milestone 3 defects found across Sprints 5-6; 2 open |
| **Sprint 7** | Week 7 | 14 | 15 | 1 | 1 | Includes US-SUB-05, moved from Sprint 2 |
| **Sprint 8** | Week 8 | 7 | 8 | 4 | 3 | Includes US-ORC-03, moved from Sprint 2; 1 intermittent browser test open |
| **Sprint 9** | Week 9 | 6 | 6 | 2 | 0 | Open items found in the final test report (also covers Sprint 8-9) |
| **TOTAL** | **9 Weeks** | **79** | **78** | **33** | **27** | **1 story in progress, 6 defects open** |

Sprints 5, 6 and 8 are verified with fake providers only; their live checks have not been run.

### Test Results by Milestone Report

| Report | Backend | Front-end | Browser | Source |
|:---|:---:|:---:|:---:|:---|
| Milestone 1 (14 Oct 2026) | 293 passed | - | - | `docs/07_pipeline_test_report.md` |
| Milestone 2 (27 Oct 2026) | 1,301 passed | - | - | `docs/09_milestone2_test_report.md` |
| React interface (before Milestone 3) | 1,636 passed | 295 passed | 183 passed | `docs/10_ui_design_system.md` |
| Milestone 3 (13-14 Nov 2026) | 2,454 passed | 477 passed | 288 passed | `docs/12_milestone3_test_report.md` |
| Milestone 4 (18 Nov 2026) | 2,956 passed | 552 passed | 369 passed | `docs/15_final_test_report.md` |
| Backend re-run (24 Nov 2026) | 2,961 passed, 4 skipped | - | - | `python -m pytest` |

All results use fake providers. The 4 skipped tests need a local run history to run. Accessibility: 0 serious or critical axe violations on 41 screens at three widths.

---

## 2. Cumulative Delivery Trajectory

```
Cumulative stories done (Total: 79 stories, 78 done)
 78 |                                                      # [SP-09: 78]
 72 |                                                 #    [SP-08: 72]
 64 |                                           #          [SP-07: 64]
 49 |                              #                       [SP-06: 49]
 37 |                      #                               [SP-05: 37]
 32 |                 #                                    [SP-04: 32]
 25 |           #                                          [SP-03: 25]
 19 |      #                                               [SP-02: 19]
  5 | #                                                    [SP-01:  5]
  0 +---------------------------------------------------------------
     W1     W2     W3     W4     W5     W6     W7     W8     W9
```

- **Average delivery**: 8.7 stories per sprint (78 stories over 9 sprints). Sprints range from 5 to 15 stories, so a story count says little about effort.
- **Largest sprint**: Sprint 7 (React interface), with 15 stories.
- **Test pass rate**: all automated tests passed in the latest run (2,961 backend passed, 4 skipped; 552 front-end and 369 browser passed on 18 Nov 2026).

---

## 3. Sprint-by-Sprint Retrospective Analysis

### Sprint 1 Retrospective (Week 1)

| Start Doing | Stop Doing | Continue Doing | Action Taken | Status |
|:---|:---|:---|:---|:---:|
| Scanning for secrets before every push. Checking that every file a document mentions exists in the repo. | Committing `.env` files. Documenting files that are not committed (`.gitignore`, `.env.example` and `05_sample_output.md` were referenced but missing). | Writing one document per task with sample output. Linking documents from the README. | `.gitignore` and `.env.example` added; missing files added; paths in `docs/05_web_search_api.md` updated. The Tavily key committed in commit `50ea1ae` must be revoked and replaced. | Open |

### Sprint 2 Retrospective (Week 2)

| Start Doing | Stop Doing | Continue Doing | Action Taken | Status |
|:---|:---|:---|:---|:---:|
| Running live checks on several industries before a demo. Holding provider clients in a variable for the whole call. | Creating the Gemini client inline (it was closed mid-request). Reporting every provider failure as a vague "AI service" error. | Automated tests with mocks (293 passing). Short bounded retries for transient 5xx errors. | Client is held and closed explicitly; the cause is logged as class plus HTTP status; `LLM_MODEL` changed from `gemini-3.6-flash` (503 on every attempt) to `gemini-3-flash-preview`; document paths corrected (`docs/07`, section 5). | Done |

### Sprint 3 Retrospective (Week 3)

| Start Doing | Stop Doing | Continue Doing | Action Taken | Status |
|:---|:---|:---|:---|:---:|
| Checking claims in code, not only in prompts: a figure reader, claim checks and a relevance check. Keeping whole sentences in targeted snippets. | Trusting a model reply because it came with a source. Reading "downloaded N times" as a count of times. | Reproducing every problem from the saved live output before changing code. Adding a warning for every repair so nothing changes silently. | Problems from the first live market run fixed in `agents/figures.py`, `agents/market_claims.py` and the focused snippets (`docs/08`, section 5). | Done |

### Sprint 4 Retrospective (Week 4)

| Start Doing | Stop Doing | Continue Doing | Action Taken | Status |
|:---|:---|:---|:---|:---:|
| Running through the API and the UI, not only the script. Using Groq Structured Outputs with a strict schema. | Relying on the 30 s default timeout. Using Groq JSON object mode for the competitor reply. | Running one live check per domain (AgriTech, FinTech, FoodTech). Integrity checks on citations. | Three integration fixes added after the live runs: Markdown report export, audit fields in the API response, backend time limit. The Groq fix is tested with fakes; a live re-run is still to do. | Done |

### Sprint 5 Retrospective (Week 5)

| Start Doing | Stop Doing | Continue Doing | Action Taken | Status |
|:---|:---|:---|:---|:---:|
| Reviewing the strategy plumbing before the stages are built on it. | Letting a strategy job keep stale warnings from stages it runs again. | Building every strategy stage from one numbered digest. Testing with fake providers only. | The strategy job now drops saved warnings of a stage it reruns, pinned by a test (`docs/12`, section 6, bug 1). Live strategy checks are not executed. | Done |

### Sprint 6 Retrospective (Week 6)

| Start Doing | Stop Doing | Continue Doing | Action Taken | Status |
|:---|:---|:---|:---|:---:|
| Running new route tests early: the 16 failures of the first chat API test run were one wrong class. | Matching routing keywords loosely ("customer" matched "customers"). Printing non-ASCII names on a Windows console. | Founder review of each agent's output. Pinning each fix with a named test. | Seven bugs fixed, each with a named test (`docs/12`, section 6). Open: strategy stage keys in the legacy report's "Time taken" line, and Advisor replies that are not scanned for secrets. | Partly done |

### Sprint 7 Retrospective (Week 7)

| Start Doing | Stop Doing | Continue Doing | Action Taken | Status |
|:---|:---|:---|:---|:---:|
| Making the light theme switchable (the tokens exist, the switch does not). Adding one real run for each new screen. | Treating a 24 px citation chip as a failure: two accessibility exceptions are documented and accepted. | Replaying saved results through mock APIs (MSW, Playwright) so tests never spend credits. Keeping 0 serious or critical axe violations. | Five real validations run from the React interface (three complete, two partial). Streamlit kept until parity is confirmed (`docs/10`, section 9). | Done |

### Sprint 8 Retrospective (Week 8)

| Start Doing | Stop Doing | Continue Doing | Action Taken | Status |
|:---|:---|:---|:---|:---:|
| Adding a Playwright journey, an axe check and screenshots for the report page. | Extending the shared API client for downloads (it added 27 bytes to the entry bundle). | Golden-file tests for Markdown and PDF output. Building all three report formats from one document. | Report header changed to a `div` so `print.css` does not hide it; duplicate subtitle hidden; downloads moved into the lazy chunk (`docs/15`, section 7). | Done |

### Sprint 9 Retrospective (Week 9)

| Start Doing | Stop Doing | Continue Doing | Action Taken | Status |
|:---|:---|:---|:---|:---:|
| Installing `pytest-cov` and the front-end coverage tool and measuring coverage. Running live checks L-1 to L-8 and confirming the exposed keys are rotated. | Skipping end-to-end testing (T7) and live verification (T8) at the end of the project. | Reporting measured results apart from "not executed" items (`docs/15`). | Outstanding list written in `docs/15`, section 5. Backend re-run on 24 Nov 2026: 2,961 passed, 4 skipped. | Open |

---

## 4. Defect Summary

Defects are tracked in [`templates/Defect_Tracker_Template_v0.1.xlsx`](./templates/Defect_Tracker_Template_v0.1.xlsx). Defect types used by the tracker: Logical, User Interface, Maintainability, Standards, Others.

| Type | Logged | Closed | Open |
|:---|:---:|:---:|:---:|
| Logical | 16 | 16 | 0 |
| User Interface | 4 | 3 | 1 |
| Maintainability | 2 | 2 | 0 |
| Standards | 4 | 2 | 2 |
| Others | 7 | 4 | 3 |
| **Total** | **33** | **27** | **6** |

### Open Defects

| Defect | Type | Detected |
|:---|:---:|:---:|
| Tavily API key committed on 11 Oct 2026 (commit `50ea1ae`) is still readable in Git history; it must be revoked and replaced | Standards | Sprint 1 |
| The "Time taken" line of the full report names strategy stages by their keys | User Interface | Sprint 5-6 |
| Advisor replies are not scanned for secrets before they are returned | Standards | Sprint 6 |
| Intermittent browser test `keyboard-m3` "advisor-full does not animate" at 1440 px | Others | Sprint 8 |
| The report page has no axe check, keyboard check or Playwright journey | Others | Sprint 8-9 |
| Live checks L-1 to L-8 not executed; code coverage not measured | Others | Sprint 9 |

---

## 5. Key Internship Learnings & Competencies Gained

1. **Agile Engineering Discipline**: working through Sprint Planning, Daily Stand-ups, a Product Backlog with MoSCoW priorities, Sprint Reviews and Retrospectives, with the mentor's Excel templates as the record.
2. **Multi-Agent System Design**: building a seven-stage pipeline (extraction, web search, market, competitors, SWOT and risk, MVP, go-to-market) with Pydantic schemas, an agent protocol and a status model of complete, partial and failed.
3. **Grounding LLM Output in Evidence**: enforcing citations and honest labels in code (figure reader, claim checks, integrity checks, report consistency checks) instead of relying on prompts alone.
4. **Resilience with External Providers**: handling timeouts and transient 5xx errors with bounded retries, a Groq fallback, structured outputs and a backend time limit.
5. **Full-Stack Delivery**: a FastAPI back end, a Streamlit interface and a React interface with background runs, responsive design and accessibility checks.
6. **Quality Assurance**: testing with fake providers (no network, no keys), 2,956 backend, 552 front-end and 369 browser tests, and reporting what was measured apart from what was not run.

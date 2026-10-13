# Agile Metrics & Sprint Retrospectives (Milestone 1)

## Project Title
**Development of AI Based Startup Idea Validator with Market Analysis Assistance**

Retrospectives use the mentor's `Retrospection` columns: Start Doing, Stop Doing, Continue Doing, Action Taken. A dash means the sprint has not happened yet.

---

## 1. Sprint Metrics

| Sprint | Week | Stories Planned | Stories Done | Completion | Defects Logged | Defects Closed | Automated Tests Passing |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Sprint 1** | Week 1 | 5 | 5 | 100% | see Defect Tracker | see Defect Tracker | 8 |
| **Sprint 2** | Week 2 | 7 | - | - | - | - | - |

The 8 passing tests in Sprint 1 cover the structured idea schema, the health endpoint, and the search client error handling. Run them with `python -m pytest`.

---

## 2. Sprint Retrospectives

### Sprint 1 Retrospective (Week 1)

Draft prepared from a repository review. The team should confirm and edit it.

| Start Doing | Stop Doing | Continue Doing | Action Taken | Status |
|:---|:---|:---|:---|:---:|
| Scanning for secrets before every push | Committing `.env` files | Writing one document per task with sample output | `.gitignore` and `.env.example` added; the committed Tavily key must be revoked and replaced | Open |
| Checking that every file a document mentions exists in the repo | Documenting files that are not committed (`.gitignore`, `.env.example`, and `05_sample_output.md` were referenced but missing) | Linking documents from the README | Missing files added and paths in `docs/05_web_search_api.md` updated to the new layout | Done |

### Sprint 2 Retrospective (Week 2)
_To be written at the end of the sprint._

---

## 3. Defect Summary

Defects are tracked in [`templates/Defect_Tracker_Template_v0.1.xlsx`](./templates/Defect_Tracker_Template_v0.1.xlsx). Defect types used by the tracker: Logical, User Interface, Maintainability, Standards, Others.

| Type | Logged | Closed |
|:---|:---:|:---:|
| Logical | - | - |
| User Interface | - | - |
| Maintainability | - | - |
| Standards | - | - |
| Others | - | - |

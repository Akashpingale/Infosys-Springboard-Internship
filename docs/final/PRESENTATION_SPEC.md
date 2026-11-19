# Presentation specification

About 12 slides for the final demonstration. Each slide lists its message, its content and the source file for every number on it. The deck itself is produced separately by the founder; this file only specifies it. Use the interface's terms: Sourced, AI interpretation, From your idea, Assumption; High, Medium, Low; the tab names.

Every number below was measured on 18 November 2026 or is marked "not executed". If a number changes before the demonstration, update it from its source file, not from this page.

| # | Slide | Message | Content | Numbers and their source |
|---:|---|---|---|---|
| 1 | Title | AI Based Startup Idea Validator with Market Analysis Assistance | Project title, Infosys Springboard internship, team names, mentor | Team and mentor: [FOUNDER TO FILL]; names recorded so far are in `docs/agile/README.md` section 5 |
| 2 | Problem | Founders decide on guesses about markets and competitors | The validation questions from `docs/01_project_understanding.md`; why manual research is slow and unsourced | none |
| 3 | Solution flow | From two lines to a cited report | Idea → review → search → market → competitors → strategy → Advisor → report, one line each | 7 stages: `orchestrator.py`; 16 report sections: `docs/13_report_generation_agent.md` section 5 |
| 4 | Agent architecture | One job per agent, checks in code | The pipeline diagram from `docs/final/TECHNICAL_DOCUMENTATION.md` section 2.1; AI requests and searches per agent | Per-agent counts: TECHNICAL_DOCUMENTATION section 5 |
| 5 | Evidence discipline | Every point says what it rests on | The four basis labels with one example each; citation chips; code checks; consistency checks | 12 consistency checks: `docs/13` section 6 |
| 6 | Live demonstration: idea and run | Correct the idea before anything expensive runs | Placeholder slide shown before switching to the browser | A live run takes about 2 to 4 minutes (plan estimate, not measured in Milestone 4) |
| 7 | Live demonstration: results and Advisor | Sources open in place; the Advisor answers only from this validation | Placeholder slide | none |
| 8 | Live demonstration: report | One document, three formats, one AI request | Placeholder slide; fallback: the saved run of 13 November (`docs/final/DEMO_RUNBOOK.md` section 4) | 1 AI request, 0 searches: `docs/13` section 1 |
| 9 | Testing and quality | Green suites with fake providers; live checks outstanding | Suite table; the not-executed list | 2956 backend, 552 front-end in 42 files, 369 browser tests passed; 0 serious or critical axe violations on 41 earlier screens at three widths; coverage not measured; live checks not executed: `docs/15_final_test_report.md` sections 1 and 5 |
| 10 | Optimisation | Four areas built behind switches; the comparison is not executed | The four-area table; the empty adoption check; "defaults stay v1" | Every result cell "not executed": `docs/14_evaluation_and_optimization.md` sections 1 and 5 |
| 11 | Limitations and unverified items | What has not been shown yet | Live checks, PDF with the real fonts, browser journeys, coverage, key rotation, the intermittent browser test | `docs/15` section 5; TECHNICAL_DOCUMENTATION section 14 |
| 12 | Learning and next steps | What was learned and what comes next | Learning outcomes and next steps | [FOUNDER TO FILL]; next steps from TECHNICAL_DOCUMENTATION section 14 |
| 13 | Evaluation criteria map | Where each criterion's evidence is | The table below | as in the table |

## Evaluation criteria map (plan Section 1.5)

| Criterion | Evidence to show | Status |
|---|---|---|
| 1. Accuracy and relevance of real-time market data and competitor intelligence | Competitor recall against reference lists, source diversity, market-size availability, integrity violations, unsupported figures; before and after tables (`docs/14` section 5) | **Not executed.** Tooling and tables ready; reference competitor names [FOUNDER TO FILL] |
| 2. Quality and depth of SWOT, risk and opportunity assessment | Rubric scores, risk category coverage, grounded share (`docs/14` sections 3.3 and 5.3) | **Not executed.** The rubric is scored by people |
| 3. Usefulness of MVP recommendations and go-to-market outputs | Rubric scores; share of recommendations with a concrete first experiment; assumption visibility | **Not executed** |
| 4. Coherence and completeness of the final report | Sections present or explained, consistency-check results, the PDF itself (`docs/13`) | Built: 12 of 12 checks pass on every fixture and saved result in the tests. The PDF with the real fonts: **not executed** |
| 5. Completeness of implementation, testing, documentation and final presentation | Test counts (`docs/15`), coverage, clean-checkout check, `docs/final/`, this specification, the runbook, the rehearsal record | Counts measured; coverage **not measured**; clean-checkout check and rehearsal **not executed** |

## Design notes for the deck

- Dark background and IBM Plex, to match the interface ([docs/10](../10_ui_design_system.md)).
- Screens from `docs/assets/ui_v2/` and `ui_v3/` show the earlier screens and the synthetic strategy result; say so on the slide. There are no screenshots of the report page yet.
- Never put a key, a `.env` line or a local path on a slide.

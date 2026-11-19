# 13. Report Generation Agent (Milestone 4, requirement R1)

**Project:** Development of AI Based Startup Idea Validator with Market Analysis Assistance

**Status:** built and tested with fakes. The written summary (the one AI request) has **not been executed** against a real model. The PDF has **not been inspected** with the production IBM Plex fonts, which are not installed yet. No report has been generated from a live run. Everything below describes the code and its offline tests, not live output.

Source of the requirements: `MILESTONE_4_MASTER_IMPLEMENTATION_PLAN (1).md`, Sections 6 (data models), 7 (the agent), 11 to 15 (usage, API, persistence, React, security) and Appendix A.1 (the prompt). Test evidence: [docs/15](15_final_test_report.md).

---

## 1. What it does

The agent compiles every stored output of a finished validation into one structured document. A founder or mentor can read it from start to finish, cite it, print it and download it as PDF, Markdown or JSON. The agent assembles and explains. It does not search the web, does not read the Advisor conversation and does not add facts.

| | |
|---|---|
| Reads | The stored run: result, constraints, submission, stage timings, `usage` and `versions` |
| Does not read | The web, the Advisor thread |
| Writes | A `ReportDocument` stored on the run's row; PDF, Markdown and JSON rendered on request |
| AI requests | Exactly 1, for the written summary, plus the retries and the Groq fallback the existing client already makes. If it fails, the report is still produced |
| Searches | 0 |

## 2. Files

| File | Lines | Role |
|---|---:|---|
| `models/report.py` | 196 | `ReportDocument`, `ReportMeta`, `ReportSection`, the six block types, `BibEntry`, `ConsistencyReport`, the narrative draft models, `report_json` |
| `agents/report_sections.py` | 954 | Pure builders, one per catalogue section, and `build_document` |
| `agents/report_bibliography.py` | 133 | Citation numbering by first appearance; mapping from `analysis:id` source keys |
| `agents/report_checks.py` | 328 | The 12 consistency checks C-01 to C-12 |
| `agents/report_agent.py` | 451 | `build_report`: gate, fingerprint, digest, the one AI request, narrative checks, assembly |
| `utils/report_render_md.py` | 141 | Markdown renderer and the shared escaping helpers |
| `utils/report_render_pdf.py` | 404 | PDF renderer (ReportLab Platypus) |
| `utils/usage.py` | 47 | The per-run counter of AI requests and searches |
| `routes/report_routes.py` | 170 | The five report routes, the per-run busy gate, the download file names |
| `web/src/features/report/` | 9 source files | Report page, contents, blocks, sources, banners, download menu, header button, hooks, copy |

Line counts were measured on the working tree on 18 November 2026.

## 3. Build flow

`build_report(run, *, narrative=True, generated_at=None)` in `agents/report_agent.py`:

1. **Gate.** The run must be `done` with a result whose status is `complete` or `partial`. Otherwise the agent raises `report_unavailable` (HTTP 409) before any call.
2. **Fingerprint.** SHA-256 of `{"result": <result without usage and versions>, "constraints": <run constraints or null>}`, as JSON with sorted keys and no whitespace. `usage` and `versions` are left out, so they can never make a report look out of date.
3. **Deterministic sections.** `build_document` in `report_sections.py`. Each builder is a pure function of the typed result. Builders never call a model and never round or rephrase numbers.
4. **Digest and written summary.** The narrative facts reuse the Advisor's `context_facts`, filtered to the IDEA, CON, MKT, CMP, RSK, MVP, GTM and VER (verify next) facts and capped at `STRATEGY_DIGEST_MAX_CHARS`. One structured call returns a `ReportNarrativeDraft` within `REPORT_TIME_LIMIT_S` (default 60 seconds). A provider failure, invalid output after the retry, or the time limit gives `narrative_status = failed`. `narrative=false` makes no call and gives `skipped`.
5. **Narrative checks** (Section 4).
6. **Assembly** in the fixed catalogue order (Section 5).
7. **Bibliography.** One numbering across market and competitors, in order of first citation. The same page cited by both analyses gets one number. The search engine's own summary (`S0`) becomes "Search engine summary (generated, not a page)" with `has_page = false`. At most 100 entries, with a visible note when the cap applies.
8. **Consistency checks** C-01 to C-12, stored in `meta.consistency` and summarised in the Method section as "N of 12 consistency checks passed."
9. **Persistence** on the run's row (Section 7).

`meta.prompt_version` is `report-v1` when the summary was attempted and empty when it was skipped.

## 4. The written summary and its checks

The prompt is Appendix A.1 of the plan, verbatim. It combines the Milestone 3 shared rules (only numbered facts, cite by ref, basis never `sourced`, no number, name or date that is not in a cited fact, JSON only) with the editor role, which forbids verdict words. The draft has `overview` (1 to 2 paragraphs), `key_insights` (3 to 5), `next_steps` (3 to 6) and `closing_caveat`.

| # | Check | Action |
|---|---|---|
| 1 | Every `based_on` ref exists in the digest | The invalid ref is removed |
| 2 | Basis is AI interpretation, assumption or the founder's own words, never sourced | Adjusted; a statement with no valid ref becomes an assumption. The draft schema does not offer `sourced` |
| 3 | Unsupported figure (a currency, percentage or magnitude no cited fact states) | The statement is removed |
| 4 | Overclaim phrases (the Milestone 3 list) | The statement is removed |
| 5 | Near-duplicates (similarity 0.8) | The first is kept |
| 6 | Counts and lengths | At most 2 overview paragraphs of 600 characters, 5 insights, 6 next steps |
| 7 | Each next step cites a risk, feature, channel, competitor, market or verify-next fact | Otherwise dropped. Fewer than 3 valid steps are filled by code from "what to verify" and the first experiment of the "Start here" channel |
| 8 | Verdict language: viable, not viable, proceed, abandon, promising, doomed, will succeed | The statement is removed |
| 9 | Key-shaped text in any narrative text | The narrative fails |

The closing caveat in the report is fixed text written by code: "This report interprets the evidence found for this idea and does not predict results." The model's own caveat is never shown. When the summary fails, the Executive summary and Recommended next steps sections start with the callout "The written summary could not be generated. All other sections are complete." and keep their deterministic content.

## 5. Section catalogue

The order is fixed. A section whose data is missing is not hidden: it is listed in `meta.sections_missing` with a reason and shown as a short "Not included" line.

| # | Id | Title | Built from |
|---|---|---|---|
| 1 | `cover` | Title block | Idea, run status, date, report version, "AI-assisted analysis; interpretations are labelled." |
| 2 | `executive_summary` | Executive summary | Written summary, stored summary lines, key insights |
| 3 | `at_a_glance` | Validation at a glance | Counts from the result; no score |
| 4 | `idea` | The idea as understood | Extracted idea and constraints |
| 5 | `market` | Market opportunity | Market analysis |
| 6 | `competitors` | Competitive landscape | Competitor analysis and the comparison matrix |
| 7 | `swot` | SWOT | SWOT stage |
| 8 | `risks` | Risk assessment | Risk register |
| 9 | `mvp` | MVP recommendation | MVP stage |
| 10 | `gtm` | Go-to-market strategy | Go-to-market stage |
| 11 | `next_steps` | Recommended next steps | Written summary and "what to verify" |
| 12 | `method` | How this report was produced | Pipeline, basis labels, evidence strength, consistency result, quality notes |
| 13 | `limitations` | Limitations | Every limitation and warning-level notice, plus fixed standing statements |
| 14 | `sources` | Sources | Bibliography |
| A | `appendix_run` | Appendix A: Run details | Stage timings, AI requests and searches, queries, versions |
| B | `appendix_glossary` | Appendix B: Terms | Basis labels, severity levels, effort sizes, evidence strength levels |

A run without strategy lists SWOT, Risk assessment, MVP recommendation and Go-to-market strategy as missing, with "Strategy was not part of this validation."

Labels match the React interface (T0 conflict C-2): **Sourced**, **AI interpretation**, **From your idea**, **Assumption**. The legacy Markdown export (`GET /api/runs/{id}/report.md`) keeps its own "User provided" label, because it must stay byte-identical.

## 6. Consistency checks

| Id | Check |
|---|---|
| C-01 | Every citation number exists in the bibliography, and every bibliography entry is cited at least once |
| C-02 | Every catalogue section is present or listed as missing with a reason |
| C-03 | Every figure in "Validation at a glance" equals the value recomputed from the stored result |
| C-04 | The positioning target segment equals the market priority segment when both exist |
| C-05 | Every risk referenced by an MVP feature or a channel exists in the risk register shown |
| C-06 | Every feature referenced by a channel exists in the MVP section shown |
| C-07 | Every gap shown carries the standing caveat, and every hypothesis differentiator is labelled |
| C-08 | No narrative statement is labelled sourced |
| C-09 | Every warning-level notice appears in Limitations |
| C-10 | The run status shown equals the stored status, and a partial run lists the stages that did not finish |
| C-11 | No text contains a configured key value or key-shaped text |
| C-12 | No text contains control characters that could break an output format; escaping is checked per renderer in the tests |

A failed check does not block the report. It is recorded and shown in the Method section with the failing ids. All 12 checks pass on every synthetic fixture, on every committed result in `docs/test_runs*/` and on the two saved live fixtures in `web/src/test/` (`tests/test_m4_report_agent.py`, `tests/test_m4_report_checks.py`). These are fixtures and saved results, not new live runs.

## 7. API and storage

| Method and path | Purpose | Success |
|---|---|---|
| `POST /api/runs/{id}/report` | Generate, or return the current report. Optional body `{ "force": false, "narrative": true }` | 200 with the `ReportDocument` |
| `GET /api/runs/{id}/report` | Read the stored report | 200, or 404 `report_not_found` |
| `GET /api/runs/{id}/report/pdf` | Download the PDF | `application/pdf`, attachment |
| `GET /api/runs/{id}/report/markdown` | Download the Markdown | `text/markdown`, attachment |
| `DELETE /api/runs/{id}/report` | Remove the stored report | 204 |

Rules:

1. A run that is not `done` or has no usable result answers 409 `report_unavailable`.
2. A current report (same fingerprint) with `force=false` is returned as stored, with no AI request. `force=true` or a stale report builds a new one and replaces it.
3. `narrative=false` builds the report with no AI request (`narrative_status = skipped`).
4. A second `POST` for the same run while one is being written answers 409 `report_busy`. Writing the summary takes one slot of the Advisor's concurrency limit (`CHAT_MAX_CONCURRENT`).
5. The downloads render the stored document and never call a model. Without a report they answer 404 with "Generate the report first."
6. File names are `startup-validation_{slug}_{YYYY-MM-DD}.pdf` or `.md`. The slug is lower-case ASCII letters, digits and hyphens from the idea title, at most 40 characters, with `idea` as the fallback.
7. The existing `GET /api/runs/{id}/report.md` is unchanged.

Error codes, in the project's error shape: `report_unavailable` (409), `report_not_found` (404), `report_busy` (409), `report_render_failed` (500, for example "The report fonts are not installed. See the setup guide. Missing: …"), `report_too_large` (422, above 60 pages).

`GET /api/runs/{id}` gains `report: { exists, generated_at, stale, narrative_status }`. `GET /api/meta` gains `report` (`available`, `pdf_available`, `time_limit_s`) and `profiles` (`query_profile`, `prompt_profile`, `app_version`).

**Storage.** Three columns on the `runs` table: `report_json`, `report_fingerprint` and `report_generated_at`. `ensure_schema` adds them with `ALTER TABLE` only when missing and never rewrites existing rows. Deleting a run deletes its report. The existing key redaction covers the report column. A stored report with a newer `schema_version` is refused with a plain message and can be replaced by generating again.

## 8. Renderers

**Markdown.** GitHub tables, headings by level, citations as `[n]`, a numbered source list, callouts as block quotes. Every dynamic string is escaped for Markdown and HTML: `&`, `<` and `>` become entities; backslash, backtick, `*`, `_`, `[`, `]`, `|`, `~`, `$` and `#` get a backslash; a leading `-`, `+`, `=` or `1.` is escaped; line breaks and control characters become spaces. Links are emitted only for `http` and `https` addresses.

**PDF.**

| Aspect | Implementation |
|---|---|
| Page | A4, 20 mm margins, black text, one accent colour `#0369A1` |
| Fonts | `REPORT_FONT_DIR` (default `assets/fonts`) must hold `IBMPlexSans-Regular.ttf`, `IBMPlexSans-Bold.ttf`, `IBMPlexSans-Italic.ttf` and `IBMPlexMono-Regular.ttf`. A missing file fails the PDF with a plain error naming the files. There is no silent fallback, and Markdown and JSON still work |
| Structure | Title, subtitle, title block, Contents with page numbers (multi-pass build), the sections, Sources, then the appendices from a new page; a PDF bookmark per section |
| Header and footer | "AI Startup Idea Validator" and the idea title; "Generated YYYY-MM-DD" and "Page x of y" |
| Tables | Repeating header row, wrapped cells, right-aligned numbers, symbols plus words in the comparison matrix |
| Escaping | Every dynamic string is cleaned and XML-escaped before it reaches ReportLab's paragraph markup |
| Metadata | Title, subject and creator are the product name; author "anonymous"; no user name, path or key |
| Determinism | ReportLab invariant mode: identical input gives identical bytes |
| Limits | 60 pages; beyond that `report_too_large` |

**JSON.** The stored `ReportDocument`, unmodified.

## 9. In the React interface

- The results header shows **Generate report**, **Generating**, **View report** or **Update report** (when the stored report is out of date). It appears only for a finished run with a complete or partial result.
- The report page (`/runs/:runId/report`, its own lazy chunk) shows the header, the banners (out of date, summary failed, partial), a contents list (sticky from 1024 px, collapsible below), the document and the sources. Citation numbers jump to their source entry. Source links open in a new tab with `rel="noopener noreferrer"`.
- The **Download** menu offers PDF, Markdown and JSON. Without the fonts, PDF is disabled with "PDF is not available because the report fonts are not installed. Markdown and JSON are available."
- **Regenerate** asks first when a written summary would be replaced. While a report is being written, the page shows "Writing the report. This takes up to a minute." with a Cancel that aborts the request.
- The export menu on the results page is relabelled "Raw results (Markdown)", "Raw results (JSON)" and "Print this page", so it cannot be confused with the report.
- Run details gains a **Usage** table (AI requests and searches per stage) and a **Versions** panel. The Status page gains a "Report and profiles" panel: whether the PDF fonts are installed, the two profiles and the summary time limit. It never shows paths or keys.
- All report text is rendered as text. `web/src/lib/noRawHtml.test.ts` covers the new files.

Screen details: [docs/10, section 12](10_ui_design_system.md#12-milestone-4-report-page).

## 10. Settings

| Setting | Default | Bounds | Meaning |
|---|---|---|---|
| `REPORT_TIME_LIMIT_S` | 60 | 20 to 600 | Seconds allowed for the written summary; exceeding it is a summary failure |
| `REPORT_FONT_DIR` | `assets/fonts` | a folder; relative paths are read from the project root | Where the four TTF files and the OFL licence live |

Both are optional and documented in `.env.example`. An out-of-range value falls back to the default with a warning in the backend log.

## 11. Security and output safety

| Risk | Control |
|---|---|
| ReportLab markup injection from `<` or `&` | Every dynamic string escaped before use; tests render hostile strings in every block type |
| Markdown or HTML injection in a viewer | Markdown and HTML metacharacters escaped; links only from validated URLs |
| `javascript:` or other URL schemes | Only `http` and `https` become links; anything else is plain text |
| Very large inputs | 60-page cap and 100-entry bibliography cap |
| File name injection | Slug-only file names; the header value is built from the slug |
| Leaks in PDF metadata | Generic author; no paths, user names or keys |
| A key in the text | C-11 on every document; the narrative fails on key-shaped text; the store redacts configured keys |
| Stored XSS on the report page | Text rendering only in React |

Privacy: report generation sends the result text in the digest to the same language-model providers as the rest of the pipeline (Gemini, and Groq on fallback). Nothing is sent to analytics.

## 12. Known limitations

- **Live behaviour not executed.** No written summary has been produced by a real model, so its quality, length and the rate of summary failures are unknown.
- **Fonts not installed.** Until the IBM Plex TTF files and the OFL licence are placed in `assets/fonts/`, the PDF download answers `report_render_failed` and the report page disables PDF. The PDF has not been inspected with the real fonts. With ReportLab, a character missing from a font is drawn as an empty box without a warning; which characters the supplied files lack is not executed yet.
- **No tagged PDF.** ReportLab does not produce tagged PDF. The reading order follows the document order, but screen-reader structure inside the PDF is limited. The report page in the browser is the accessible version.
- **No browser test of the report page.** The Milestone 4 interface is covered by 75 Vitest tests in jsdom. No Playwright journey, axe check or screenshot covers it, because the end-to-end testing task (T7) was not executed.
- **Fixed catalogue.** Sections cannot be reordered or switched off, by design.

## 13. Tests

| File | Tests | Covers |
|---|---:|---|
| `tests/test_m4_report_models.py` | 35 | Models, compatibility with every stored fixture, schema version |
| `tests/test_m4_report_sections.py` | 36 | Each builder on complete, partial, no-strategy and minimal results |
| `tests/test_m4_report_bibliography.py` | 17 | Numbering, cross-analysis merge, `S0`, uncited entries, cap |
| `tests/test_m4_report_checks.py` | 32 | C-01 to C-12 with planted offenders and clean passes |
| `tests/test_m4_report_agent.py` | 76 | Full build, summary failure, partial run, fingerprint, one AI request, no search |
| `tests/test_m4_render_md.py` | 26 | Golden Markdown and escaping |
| `tests/test_m4_render_pdf.py` | 36 | Pages, contents, links, fonts missing, determinism, hostile strings |
| `tests/test_m4_cross_format.py` | 9 | The same text on screen, in Markdown and in PDF |
| `tests/test_m4_report_api.py` | 39 | Every route, rule and error code |
| `tests/test_m4_store_migration.py` | 20 | New columns on old databases, deletion, redaction |
| `web/src/features/report/*.test.tsx` and two results and status test files | 75 | Report page, blocks, download menu, header button, hooks, Run details panels, Status |

The tests use ReportLab's bundled Vera fonts, copied under the production file names into a temporary folder. Counts were collected on 18 November 2026; the full results are in [docs/15](15_final_test_report.md).

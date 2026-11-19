# User guide: AI Startup Idea Validator

This guide is for founders who use the React interface. It describes the tool as built. Where something has not been checked with real AI and search providers, the guide says so.

## 1. What the tool does and does not do

**It does:**
- turn two or three lines about your idea into a structured idea you review and correct;
- search the web (Tavily) for market, competitor, demand and funding evidence, and keep the source of every result;
- analyse the market and the competitors from that evidence, citing numbered sources;
- on request, build a SWOT and risk register, an MVP feature plan and a go-to-market plan from those findings;
- answer questions about one finished validation (the Advisor);
- compile everything into one report you can read on screen and download as PDF, Markdown or JSON.

**It does not:**
- give a score or say whether to proceed. Interpretations are labelled, and they are not predictions;
- prove that a competitor does not exist. Absence from search results does not prove absence;
- replace talking to customers. The "what to verify" list tells you what to check yourself;
- remember you. There are no accounts; the history is a file on your own computer.

## 2. Writing a good idea

On the first screen, describe the idea in two or three sentences (30 to 2,000 characters, at least 3 words). Say what problem you solve, for whom, and how. Pick the closest industry and name the target customers. In "Relevant details", add anything you already know, such as a pilot partner, a region or a competitor you have heard of. A competitor you name yourself is treated as "From your idea" and is checked against the search results.

The tool then shows the **extracted idea**: problem, solution, target customers, industry and key features. Correct anything that is wrong before you run the analysis. The run uses your corrected version.

## 3. Resources and goals

Leave **Include strategy** on if you want the SWOT, MVP and go-to-market parts. Open **Resources and goals (optional)** to give team size, months to the first release, budget level, technical skill and launch region. Whatever you leave empty is assumed (a team of 2 and 3 months) and marked as an assumption in the results and the report.

Strategy adds 3 AI requests to a run and no searches.

## 4. Reading the results

While the run is going, the tracker shows four stages, or seven with strategy, with the time each takes. **Cancel** asks the run to stop; the stage in progress finishes first. When it finishes, the results have seven tabs:

| Tab | What it shows |
|---|---|
| Overview | The summary, the tiles per area, how the evidence strength was worked out, the takeaways, what to verify next and the quality notes |
| Market | Industry overview, demand evidence, market size (TAM, SAM, SOM with their status), trends, segments, opportunities, limitations |
| Competitors | The competitor list, the feature comparison, coverage, possible gaps and differentiation opportunities |
| Strategy | SWOT, risk register, MVP plan and go-to-market plan |
| Advisor | Questions about this validation |
| Sources | Every source, with what rests on it |
| Run details | Stage timings, warnings, the Usage table (AI requests and searches per stage) and the Versions panel |

A numbered chip after a claim opens the source drawer for that source.

## 5. What the basis labels mean

Every labelled point carries one of four labels. The same words appear on screen and in the report.

| Label | Meaning |
|---|---|
| Sourced | Stated by a cited source. Click the number to see it |
| AI interpretation | The AI's reading of the evidence. No source states it |
| From your idea | Taken from what you wrote |
| Assumption | Assumed where no evidence or input was available |

Strategy points (SWOT, risks, MVP, go-to-market) and the report's written summary are never labelled Sourced, because they interpret the findings.

## 6. What "evidence strength" means and does not mean

Evidence strength (Strong, Moderate or Limited) describes how well the findings are backed by sources. It combines three parts: the share of findings labelled Sourced, the breadth of the sources, and the evidence level the analyses reported. The Overview tab shows each part and how it was weighted. It says nothing about whether the idea is good. A weak result can mean a new market or a poor search; a strong one can still describe a crowded market.

## 7. Using the Advisor

Open the **Advisor** tab, or press **Ask the advisor about this** at the end of a section. The Advisor answers only from this validation's results, with a basis label and sources on each paragraph. When the results do not cover a question it says so, and it refuses questions unrelated to the validation.

Limits: 25 questions per validation, 1,000 characters per question, one question at a time, 2 seconds between questions. **Clear conversation** gives the questions back. Each question is one AI request; a question about a part the results do not have is answered without one.

## 8. Generating and downloading the report

1. Open a finished validation and press **Generate report** in the header. The report page opens and shows "Writing the report. This takes up to a minute." You can cancel.
2. The report has a fixed order: title block, executive summary, validation at a glance, the idea, market, competitors, SWOT, risks, MVP, go-to-market, next steps, how the report was produced, limitations, sources, and two appendices. A part your run does not have is listed as "Not included" with the reason.
3. Use **Download** for PDF, Markdown or JSON. The files are named `startup-validation_<idea>_<date>`.
4. When you add or change strategy later, the report is marked "This report was made before the latest changes to this validation." Press **Regenerate**, or **Update report** in the results header.

Making a report costs one AI request and no search. Opening or downloading an existing report costs nothing. If the written summary fails, the report is still made, with "The written summary could not be generated. Everything else is complete." and **Try again**.

PDF needs the report fonts to be installed. Without them the menu says "PDF is not available because the report fonts are not installed. Markdown and JSON are available." The Status page shows whether the fonts are installed.

The results page still has **Export** with "Raw results (Markdown)", "Raw results (JSON)" and "Print this page". These are the raw results, not the report.

## 9. History

**History** lists your saved validations with title, industry, status, start date and duration. You can open, rename or delete one. Deleting removes its Advisor conversation and its report too. A validation can be loaded back into the form with **Edit and re-run**.

## 10. Limits and quota messages

| Message | What it means |
|---|---|
| "The AI service rate limit or quota was reached." | The Gemini free-tier quota is used up for now. With a Groq key configured, Groq answers instead, so this means its limit was reached too. Wait and try again |
| "The AI service is busy right now." | A temporary server error. The tool already retried |
| "The web search rate or credit limit was reached." | Tavily credits are used up for now |
| A third run is refused | At most 2 runs can go at once |
| "This conversation is full." | The 25 Advisor questions are used. Clear the conversation to start again |
| "Can't reach the server. Start it with `python app.py`" | The backend is not running |

A run that hits a limit may finish as **Partial**: the parts that finished are kept and the rest are listed.

## 11. Privacy

Idea text and findings are sent to Gemini (and to Groq on fallback), and search queries are sent to Tavily. Report generation and Advisor questions send result text to the same language-model providers. Nothing is sent to analytics. Results and the history file stay on your computer.

## 12. Not verified yet

Milestone 4 features (the report, its written summary, the PDF with the real fonts) have been tested only with fake providers. No live run of them has been executed. See [docs/15](../15_final_test_report.md) for the list.

# Demonstration runbook

A 12-minute demonstration of the AI Startup Idea Validator, with what to say, what can go wrong and a fallback for each step. This is a draft: the founder rehearses it and amends it.

**Status:** not rehearsed. No rehearsal has been recorded (section 7). Milestone 4 features have run only with fake providers, so the first live run of the report will happen in the rehearsal, not before.

---

## 1. Before the day

1. **Rotate the exposed keys.** The Git history holds an old Tavily-key-shaped string and an old `src/web_search/.env` (T0 audit). Revoke them in the provider dashboards and put new keys in `.env`.
2. **Install the report fonts** in `assets/fonts/` (`IBMPlexSans-Regular.ttf`, `IBMPlexSans-Bold.ttf`, `IBMPlexSans-Italic.ttf`, `IBMPlexMono-Regular.ttf` and the OFL licence). Without them, show the Markdown download instead of the PDF.
3. **Prepare the saved-run fallback** (section 4) and download its report files to a folder outside the repository.
4. **Make a screen recording** of one complete run, from submitting the idea to downloading the report, at least one day before. Windows: Xbox Game Bar (`Win + Alt + R`) or any recorder you already have; macOS: `Shift + Cmd + 5`. Keep it outside the repository. Play it if the live run cannot be shown at all.
5. **Rehearse once** with the timings below and record the minutes per step in section 7.
6. **Run the preflight checklist** (section 3) on the day, before the audience arrives.

## 2. The 12-minute flow

| Minute | Step | What to say | What can go wrong | Fallback |
|---|---|---|---|---|
| 0:00 | Problem and approach (slides 1 to 4) | Founders guess at markets; the tool gathers evidence, cites it and labels what is interpretation | none | none |
| 1:30 | Submit an idea, review it, add resources | The idea is structured first, and you correct it before anything expensive runs. Resources you leave empty are assumed and marked | Typing takes too long; extraction hits a quota error | A "Try an example" button fills the form. If extraction fails, open the saved run from History |
| 3:00 | Watch the seven stages (a live run takes about 2 to 4 minutes; talk through the pipeline while it runs) | Each stage, what it searches, and that code checks every citation | Rate limit or slow provider; a stage ends partial | Open the saved run from History (section 4). A partial result is a real, documented outcome |
| 5:30 | Overview, Market, Competitors with citations and the source drawer | Numbers are copied from sources; the chip opens the source; gaps are hypotheses | A market figure is Unavailable | Explain why the tool says Unavailable instead of guessing |
| 7:00 | Strategy tab and two Advisor questions: one in scope, one out of scope | Strategy points are interpretations, never Sourced; the Advisor answers only from this validation | Advisor quota error | The saved run already has an Advisor conversation; show it |
| 9:00 | Generate the report and show the PDF | One AI request, no search; 12 consistency checks; sections that are missing are explained | Summary fails; fonts missing | The report is still made without the summary. Show the Markdown, or the pre-generated report of the saved run |
| 10:30 | Evidence slide: test counts and the optimisation table | 2956 backend, 552 front-end and 369 browser tests passed with fakes; the optimisation comparison was not executed | none | none |
| 11:30 | Limitations and next steps | What is not verified, and what comes next | none | none |

Questions follow; see section 6.

## 3. Preflight checklist (manual)

The plan's `preflight.py` script was deferred (plan Section 3), so this is a checklist. Never print a key value; the commands below print key names only.

| # | Check | PowerShell | POSIX shell | Done |
|---:|---|---|---|---|
| 1 | Python 3.10 or newer, Node 18 or newer | `python --version; node --version` | `python3 --version; node --version` | [FOUNDER TO FILL] |
| 2 | Ports 8000 and 5173 free (or your own servers already on them) | `Get-NetTCPConnection -State Listen -LocalPort 8000,5173 -ErrorAction SilentlyContinue` | `lsof -i :8000 -i :5173` | [FOUNDER TO FILL] |
| 3 | `.env` exists and the key names are set (names only) | `Select-String -Path .env -Pattern '^(LLM_API_KEY\|LLM_MODEL\|TAVILY_API_KEY\|GROQ_API_KEY)=.+' \| ForEach-Object { $_.Line.Split('=')[0] }` | `grep -oE '^(LLM_API_KEY\|LLM_MODEL\|TAVILY_API_KEY\|GROQ_API_KEY)=.' .env \| cut -d= -f1` | [FOUNDER TO FILL] |
| 4 | Keys rotated since the T0 audit | Your confirmation | Your confirmation | [FOUNDER TO FILL] |
| 5 | Report fonts present | `Test-Path assets\fonts\IBMPlexSans-Regular.ttf` (and the other three) | `ls assets/fonts` | [FOUNDER TO FILL] |
| 6 | History file writable | `(Get-Item data\runs.db).IsReadOnly` is `False` | `test -w data/runs.db && echo writable` | [FOUNDER TO FILL] |
| 7 | Backend answers | `Invoke-RestMethod http://127.0.0.1:8000/health` | `curl -s http://127.0.0.1:8000/health` | [FOUNDER TO FILL] |
| 8 | The Status page shows the providers configured and "PDF fonts Installed" | <http://127.0.0.1:5173/status> | same | [FOUNDER TO FILL] |
| 9 | Optional, spends one AI request: the model and key work | `python scripts/check_llm.py` | `python scripts/check_llm.py` | [FOUNDER TO FILL] |
| 10 | History rows are labelled so that no seeded or saved row is taken for a live one | History page | History page | [FOUNDER TO FILL] |

About check 10: `data/runs.db` holds four seeded rows whose ids start with `demo-`. Three of them (`demo-saved-fintech`, `demo-partial-fintech`, `demo-failed-fintech`) store the gig-worker credit-scoring submission next to a cash-flow platform result (T0 audit), so do not show them as a matched example. Rename the saved fallback run so that its title ends with "(recorded run, not live)".

In check 3, the pipe characters are escaped only because this is a Markdown table; type them as plain `|`.

## 4. The saved-run fallback (a user procedure)

Plan Section 3 asks for an existing saved real run and a pre-generated report as a labelled fallback, without manufacturing a recorded run. The plan's import script was deferred, so these are manual steps for the founder. **Nothing from the database is copied into this repository**, and the generated report files stay outside it.

**The run.** The only saved real run that finished all seven stages is `c103255c265b4156b379f43977d142e6` in the localhost history file `C:\Users\akash\Infosys-Springboard-localhost\runs.db` (T0 audit): the agritech submission, run on 13 November 2026 at 13:59 UTC, 176.25 seconds, no resources given (so the MVP defaults were assumed), with an Advisor conversation of 3 questions and 3 answers. It has no report yet.

**Steps** (PowerShell; the POSIX equivalents use `cp`, `export` and `curl`):

1. Copy the history file to a new folder, so that the original is never changed. A Milestone 4 backend adds the report columns to the file it opens.
   `New-Item -ItemType Directory C:\demo-history; Copy-Item C:\Users\akash\Infosys-Springboard-localhost\runs.db C:\demo-history\runs.db`
2. Start the Milestone 4 backend from this repository against the copy, in its own terminal:
   `$env:RUNS_DB_PATH = "C:\demo-history\runs.db"; python app.py`
3. Start the React interface (`npm run dev` in `web/`), open History and open the run. Rename it so that its title ends with "(recorded run, not live)".
4. Generate the report:
   - with rotated keys and credit approval: press **Generate report** (1 AI request, no search);
   - without a live call: `Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/runs/c103255c265b4156b379f43977d142e6/report -ContentType 'application/json' -Body '{"narrative": false}'`. The report is then made without the written summary and says so.
5. On the report page, download the PDF (needs the fonts) and the Markdown into a folder outside the repository, for example `C:\demo-history\`.
6. On the day, if the live run fails, open this run from History: the report page shows the stored report without a new request, and the Advisor tab shows the saved conversation. Say that it is a saved run from 13 November.

If the run is not in that file, or the file is not available, use the screen recording instead.

## 5. Turning the project report into Word or PDF

`docs/final/PROJECT_REPORT.md` is the source. Kiro does not produce Word or PDF files. Any converter you install yourself works, for example Pandoc (not a project dependency):

```sh
pandoc docs/final/PROJECT_REPORT.md -o PROJECT_REPORT.docx
```

Or open the Markdown in an editor with a Markdown preview and print it to PDF. Fill every `[FOUNDER TO FILL]` first.

## 6. Q&A preparation

Draft answers for the founder to review. Each names the document that holds the evidence.

**Why multiple agents instead of one large prompt?**
Each stage has one job, its own input and output model and its own checks, so a failure stays in its stage and the run returns what finished as `partial`. The market and competitor stages cite numbered evidence, and code checks those citations before anything reaches the strategy stages. Sources: [docs/02](../02_multi_agent_system.md), [docs/06](../06_multi_agent_architecture.md), [TECHNICAL_DOCUMENTATION, section 5](TECHNICAL_DOCUMENTATION.md#5-agents).

**How is accuracy controlled?**
The model may cite only numbered search results. Code then checks every citation, URL, figure and unit, removes conclusions a source does not state, and labels every point with its basis. Strategy points and the report summary can never be labelled Sourced. The report runs 12 consistency checks over itself. Sources: [docs/08](../08_milestone2_agents.md), [docs/11, section 7](../11_milestone3_strategy_and_advisor.md#7-checks), [docs/13](../13_report_generation_agent.md).

**What happens when a provider fails?**
Gemini 5xx errors are retried twice. A rate limit, quota error, 5xx or timeout gets one Groq attempt when a Groq key is set. A failed analysis or strategy stage is recorded and the run continues; only a failed extraction stops the run. A failed report summary still gives a report. A Groq takeover has never been observed live. Sources: [TECHNICAL_DOCUMENTATION, section 5](TECHNICAL_DOCUMENTATION.md#5-agents), [docs/15](../15_final_test_report.md).

**What is not verified?**
Every Milestone 4 live check, the PDF with the real fonts, the real-backend browser journeys, the failure matrix, coverage, the reproducibility check and the report page in a browser. The automated suites pass with fake providers, which proves the code paths, not live behaviour. Source: [docs/15, section 5](../15_final_test_report.md#5-outstanding-not-executed-or-not-verified).

**Why is there no viability score?**
A single number would hide which parts rest on sources and which are interpretation, and it would read as a prediction. The tool shows evidence strength (how well the findings are backed) and labels every point instead. Sources: [USER_GUIDE, section 6](USER_GUIDE.md#6-what-evidence-strength-means-and-does-not-mean), [docs/13](../13_report_generation_agent.md).

**How is the report built?**
From the saved run only: 16 sections in a fixed order built by code, one AI request for the written summary with nine checks on it, a bibliography numbered by first citation, and 12 consistency checks. The PDF, Markdown and JSON come from the same document. Source: [docs/13](../13_report_generation_agent.md).

**Did the optimisation improve anything?**
Not measured. The candidate query and prompt profiles are built and tested offline behind switches, but the three-idea comparison has not been run, so the defaults stay `v1` and no improvement is claimed. Source: [docs/14](../14_evaluation_and_optimization.md).

**What would you do next?**
Rotate the keys, run the three-idea pilot and decide the defaults; install the fonts and review the PDF; add the real-backend browser journeys and measure coverage. [FOUNDER TO FILL: your own priorities.]

## 7. Rehearsal record

| Date | Step timings (minutes) | What went wrong | Changes made to this runbook |
|---|---|---|---|
| [FOUNDER TO FILL] | [FOUNDER TO FILL] | [FOUNDER TO FILL] | [FOUNDER TO FILL] |

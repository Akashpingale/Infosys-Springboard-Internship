# T17 report: Advisor tab (R4 UI)

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T17 (line ~1288), with Section 14.6 in full, 14.4 ("Every section ends with an 'Ask the advisor about this' text button"), 14.8, 14.9, 14.10 (Advisor empty copy), 10.3 to 10.7 (limits, reply structure, suggestions, failure behaviour), 12.2 to 12.4 (chat endpoints and error codes), 17.4 and 17.5. Nothing from T18 or later was built: print rules, `PRINTED_TABS`, `print.css`, Markdown and e2e are untouched.

No backend file changed, so the backend suite was not re-run (brief: frontend tasks run it only when a backend file changed). No backend server was started.

## Files

| File | Status | Size / diff | Purpose |
|---|---|---|---|
| `web/src/features/advisor/AdvisorTab.tsx` | new | 548 lines | The Advisor tab. Header "Ask about this validation", the muted caveat line, and chips for `available_sections` under "The Advisor can use:". Starter questions as buttons while the thread is empty, under the 14.10 empty copy. The thread is an `<ol aria-label="Conversation">`, with follow-up chips after the last advisor message. The composer has the label "Your question", a 2-row textarea that grows to 6 rows, a "n / max" counter, the helper "Enter sends. Shift+Enter starts a new line." and a primary **Send** button. Enter sends, Shift+Enter adds a newline, and Enter is ignored during IME composition (`compositionstart/end`, `isComposing`, keyCode 229). While a question is pending, the question shows in the thread and a "Thinking" row has **Cancel**, which aborts through `useSendChat.cancel`. One `aria-live="polite"` region says "Advisor is answering", then "Advisor replied." Focus goes back to the composer after a send and the new reply is scrolled into view (`auto` under reduced motion). "{n} questions left" appears at 5 or fewer. At 0 the composer is replaced by "This conversation is full." with a Clear button. "Clear conversation" opens the existing `ConfirmDialog`, with its cancel button ("Keep it") focused. Errors are shown inline in plain words, and the draft goes back into the composer. Run not finished, or no result: an explanation and a link to the run. Strategy absent: "Strategy has not been generated yet." with "Generate strategy" (`mode: missing`). Also exports `AskAdvisorButton`, `ADVISOR_QUESTIONS`, `ADVISOR_COPY`, `advisorAvailable`, `questionsLeft` and `sendProblem` |
| `web/src/features/advisor/ChatMessage.tsx` | new | 62 lines | `ChatMessageItem`. A user message is right-aligned on a raised surface. An advisor message is left-aligned with full-width paragraphs. Each paragraph has a `BasisChip`, citation chips (`resolveStrategySources` → the same `Citations`/drawer as the other tabs) and "From: Market, Competitors" (from `paragraph.sections`; `general` is not named). All text renders as React text with `whitespace-pre-wrap`, never as HTML or markdown. Also `SECTION_LABELS` and `fromLine` |
| `web/src/features/advisor/AdvisorTab.test.tsx` | new | 632 lines, 29 tests | |
| `web/src/features/advisor/advisorRun.test.tsx` | new | 234 lines, 8 tests | |
| `web/src/lib/noRawHtml.test.ts` | new | 44 lines, 2 tests | Guard test in the style of `tokens.test.ts`. It walks every `.ts/.tsx/.js/.jsx` file in `web/src` and fails on any use of React's raw-HTML prop. The forbidden word is built from parts, so the guard scans itself too. A self-check confirms that the walk covers more than 60 files, including `AdvisorTab.tsx` and `ChatMessage.tsx`, and that the pattern catches an offender |
| `web/src/features/run/RunPage.tsx` | changed (T17's named file) | +45 −4 vs start of task | Renders `AdvisorTab` for the `advisor` tab, replacing the placeholder `EmptyState`. The Advisor draft (`advisorDraft`) and a one-shot `focusComposer` flag live in the page, so a draft survives a tab switch. `ask(question)` writes the question in, asks for composer focus and switches to the Advisor tab. It never sends. Passes `onAsk={ask}` to `StrategyTab`. Wraps the Market and Competitors panels with `withAsk(...)`, which adds one `AskAdvisorButton` at the end of the tab when that analysis exists. `onShowOverview` switches to Overview from the "unavailable" link. The print effect and `PRINTED_TABS` are unchanged (T18) |
| `web/src/features/strategy/StrategyTab.tsx` | changed (T14 file; pre-approved wiring) | +20 −6 | See "Integration edits" |
| `web/src/features/run/strategyRun.test.tsx` | existing test edited (pre-approved) | +8 −4 | See below |
| `web/src/features/run/RunPage.test.tsx` | existing test edited (pre-approved setup-only handler) | +6 −1 | See below |

`hashes.py check` against the start-of-task baseline (82 uncommitted files) lists exactly these nine files. No backend, Streamlit, e2e, `useChat.ts`, `strategyHandlers.ts` or other T1–T16 file changed. The new source files have no comments or docstrings. MarketTab.tsx and CompetitorsTab.tsx (committed M2 files) were not edited.

## Requirement mapping (Section 18 T17 and 14.6)

| Requirement | Where |
|---|---|
| Header, muted line, chips for `available_sections` | `AdvisorTab` header section; `SECTION_LABELS` gives the plain names (Market, Competitors, SWOT, Risks, MVP plan, Go-to-market) |
| Up to four deterministic starter questions as buttons when the thread is empty | `data.suggestions` from `GET /chat`, rendered as buttons (the backend caps them at 4). Pressing one asks it |
| Thread: user right / advisor left, basis chip, citation chips, "From:" labels, follow-up chips after the last advisor message | `ChatMessageItem`; follow-ups come from `last.follow_ups` and are hidden while pending or when the thread is full |
| Composer: label, 2→6 rows, counter, Send, Enter / Shift+Enter / IME, draft kept on error | `Field` (existing component, gives the counter and the error line) plus `TextArea`, a layout effect for the growth, and `onKeyDown` with composition guards |
| Pending: "Thinking" row with Cancel (abort) and `aria-live="polite"` "Advisor is answering" | `useSendChat(...).cancel()` (T13 hook, unchanged). A cancelled question returns to the composer with "Cancelled. Your question is still here." |
| Reply announced once "Advisor replied.", focus stays in the composer, new message scrolled into view | Live region text set in the per-call `onSuccess`, `composer.focus()` on send, `scrollIntoView` on the new reply id |
| Limit: "{n} questions left" at ≤ 5; at 0 "This conversation is full." with Clear | `questionsLeft`; full panel. A `chat_limit_reached` answer also re-reads the thread so the full state appears |
| Clear: text button, existing confirm dialog with cancel focused | `ConfirmDialog` ("Clear this conversation?", "Clear it" / "Keep it"); `useClearChat` (T13 hook) |
| Errors inline and plain: busy, cooldown, provider trouble, offline | `sendProblem`: `chat_busy` / `chat_cooldown` pass on the backend's plain message (12.4). 5xx gives "The AI service is busy. Try again in a minute.", plus "Try rephrasing the question." when the backend appended it (10.7). Unreachable gives "Lost connection. Your question is still here." Other codes pass on the backend's message. The draft is restored in every case |
| Unavailable: explanation and a link to the run | `advisorAvailable` (run `done` with a `complete`/`partial` result, the same rule as `routes/chat_routes.py`). The thread is not requested otherwise. A backend `chat_unavailable` 409 shows the backend's message |
| Missing sections: "Strategy has not been generated yet." with "Generate strategy" | Shown when none of swot/risks/mvp/gtm is in `available_sections`. The button (only when `/api/meta` says strategy is available and the result can carry a strategy) sends one `POST /strategy {mode: 'missing'}` |
| All text as text; `dangerouslySetInnerHTML` forbidden with a guard test | No raw-HTML prop anywhere. `noRawHtml.test.ts`, plus a render test with `<b>`/`<img onerror>` text |
| Prefilled "Ask the advisor about this" from every Strategy section | `StrategyTab` `Section` gets an `ask` callback. The button sits at the end of SWOT, Risks, MVP plan and Go-to-market when that part exists. Its accessible description is the section heading |
| … and from the Market and Competitors tabs (only if a one-line addition fits) | Added in `RunPage.panel()` as one `withAsk(...)` per tab, so the M2 tab files are untouched. The button sits at the end of the tab, outside its grid |
| Integration: citation chips use the same drawer | `onOpenSource` is the page's `setOpenSource`. Test opens the drawer from an Advisor chip |
| Integration: sections list from `available_sections` | Header chips and the strategy-missing rule both read it |
| Limits from the API, not written twice | Message length from `thread.limits.max_message_chars` (fallback `/api/meta` `chat`), turns from `remaining_turns` |

## Tests (39 new)

`AdvisorTab.test.tsx` (29):
- Header and starter questions: `names the tab, says what the answers rest on and lists the sections it can use`; `offers the starter questions as buttons while the thread is empty`; `asks a starter question when it is pressed, then shows the answer`; `shows no suggestions once the thread has messages`.
- Thread: `shows the saved conversation in order, yours on the right and the advisor on the left`; `gives every advisor paragraph a basis chip, its citation chips and where it came from`; `shows the follow-up questions after the last advisor message, and asks one when it is pressed`; `renders what the advisor wrote as text, never as markup`.
- Asking: `sends the question, clears the composer, shows the answer and reads the thread again`; `announces once that the advisor replied`; `sends with Enter and adds a new line with Shift+Enter`; `ignores Enter while a character is being composed`; `sends nothing for an empty or too long question, and says why`; `shows a Thinking row while it waits, announces it, and cancels on request with the question kept`.
- Errors keep the draft: `says the AI service is busy when the provider fails`; `adds the rephrasing hint when the reply could not be read`; `says the connection was lost and keeps the question`; `passes on the plain words for a busy thread and for the cooldown`.
- Limits and clearing: `shows how many questions are left only when five or fewer remain` (6 → none, 3 → "3 questions left", 1 → "1 question left"); `replaces the composer with a full note and a Clear button when no questions remain`; `reads the thread again when the backend says the conversation is full`; `asks before clearing, with Keep it focused, and clears only on confirmation`; `says so when the conversation could not be cleared`.
- Unavailable and missing strategy: `explains that questions wait for a finished validation, and asks nothing` (no GET is made); `links to the run when there is no result to ask about`; `shows the backend's reason when it refuses to open the conversation`; `offers to generate the strategy when the run has none, and sends one request`; `makes no strategy offer when the strategy is there`.
- Prefill: `puts the question in the composer and focuses it without sending it`.

`advisorRun.test.tsx` (8, through the real `RunPage` or `StrategyTab`):
- `ends every Strategy section with the button`; `opens the Advisor with the question written in and focused, and sends nothing`; `writes in the question of the section it was pressed in`; `is offered at the end of the Market and Competitors tabs too`; `is not offered on a part that could not be completed`; `is not offered when the page gives the tab nowhere to send it`.
- `keeps the thread and the draft when the reader moves to another tab and back, and on a re-render`; `opens a cited source in the same drawer as the other tabs`.

`noRawHtml.test.ts` (2): `never hands raw HTML to React anywhere in the source`; `walks enough files to mean something, including the Advisor, and still catches an offender`.

The abort test stubs `AbortController` with Node's `transferableAbortController().constructor`, exactly as T13's `useChat.test.tsx` does, so undici accepts the signal.

## Existing-test edits (pre-approved: placeholder-to-real Advisor assertion, and setup-only MSW handlers; no assertion removed or loosened)

The Advisor tab now calls `GET /api/runs/{id}/chat` when opened. Two existing tests open it and needed the handler as setup only. One test asserted the placeholder text and now asserts the real 14.10 empty-state copy (orchestrator addendum during T14).

1. `web/src/features/run/strategyRun.test.tsx`

| Before | After |
|---|---|
| import list: `STRATEGY_DONE, STRATEGY_RUNNING, STRATEGY_STAGE_LABELS, metaWithStrategy, runUrl, strategyOk` | adds `EMPTY_THREAD` and `chatThreadOk` (existing factories in `strategyHandlers.ts`) |
| `moves through all seven …`: `server.use(show(DONE), metaWithStrategy());` | `server.use(show(DONE), metaWithStrategy(), chatThreadOk(() => EMPTY_THREAD));` (setup only) |
| `it('opens the Strategy tab and a placeholder for the Advisor tab', …` / `server.use(show(DONE), metaWithStrategy());` | `it('opens the Strategy tab and the Advisor tab', …` / `server.use(show(DONE), metaWithStrategy(), chatThreadOk(() => EMPTY_THREAD));` |
| `expect(screen.getByRole('tabpanel')).toHaveTextContent('Questions about this validation will be answered here.');` | `await waitFor(() => expect(screen.getByRole('tabpanel')).toHaveTextContent('Ask about your market, competitors, risks, MVP or launch plan.'));` (exact 14.10 "Advisor empty" copy; `waitFor` because the thread is fetched first) |

2. `web/src/features/run/RunPage.test.tsx`, `moves between tabs with the arrow keys` (setup only):

| Before | After |
|---|---|
| `import { server } from '@/test/server';` | plus `import { EMPTY_THREAD, chatThreadOk } from '@/test/strategyHandlers';` |
| `server.use(show(DONE), http.get(\`${API_URL}/api/meta\`, () => HttpResponse.json(META)));` | `server.use(show(DONE), http.get(\`${API_URL}/api/meta\`, () => HttpResponse.json(META)), chatThreadOk(() => EMPTY_THREAD));` (split over lines) |

Undo proof (`undo_check.py` reverses exactly these hunks on the current files and hashes the result against the copies taken before editing):

| File | Current SHA-256 | Reverted | Pre-edit copy (`.orig`) | Match |
|---|---|---|---|---|
| `strategyRun.test.tsx` | 0A8CF253A9357501EC26ED4CC642539C629CAFF0DA6C05971888CC355A3ACAA8 | DA5D11D3C71642E622C75545EC02122C27830625A117AFE2402EDF8762FFDB48 | DA5D11D3…62FFDB48 | True |
| `RunPage.test.tsx` | E454B4EA2EAE3F68C2488163FF784F1AAAC5DE710321AF5CB35FDF866E026AEF | 0CC78DA7B20E16F9668DC1BB8986AFC5403A2FAF4053D69F73E4CD54B69F1B03 | 0CC78DA7…69F1B03 | True |

The final `npm test` log has 0 lines matching `unhandled`, `onUnhandledRequest` or `MSW]`.

## Integration edit to an earlier task's file (pre-approved, brief addendum during T15)

`web/src/features/strategy/StrategyTab.tsx` (T14), pre-edit copy `StrategyTab.tsx.orig`:

| Before | After |
|---|---|
| imports | adds `import { ADVISOR_QUESTIONS, AskAdvisorButton } from '@/features/advisor/AdvisorTab';` |
| `function Section({ id, title, children })` | gains an optional `ask?: (() => void) \| undefined` and renders `<AskAdvisorButton onClick={ask} describedBy={\`${id}-heading\`} />` after `children` when given |
| `StrategyTabProps { run, result, sources, onOpenSource }` | adds an optional `onAsk?: (question: string) => void` |
| after `const retry = …` | `const asker = (question, ready) => (onAsk && ready ? () => onAsk(question) : undefined);` |
| four `<Section …>` openings | each gains `ask={asker(ADVISOR_QUESTIONS.<part>, Boolean(<part result>))}` (SWOT and Risks use `swot`, MVP uses `mvp`, GTM uses `gtm`) |

The individual section components (`SwotSection`, `RisksSection`, `MvpSection`, `GtmSection`) are unchanged. Putting the button in StrategyTab's shared `Section` wrapper keeps it at the end of every section with one edit. Without `onAsk` (all T14–T16 StrategyTab tests) nothing renders, so those tests are unaffected.

## Plan-vs-code points and decisions

1. **Starter and follow-up buttons ask at once.** 14.6 calls them "buttons" and says only that the section prefill must not send. Pressing a suggestion or a follow-up sends that question (one AI request, from an explicit click). It does not touch a draft the user is typing. If the question fails, it goes into the composer when the composer is empty.
2. **The composer is read-only while a question is pending.** This keeps "Your question is still here" true: the sent question is always the one put back on error or cancel. Typing resumes as soon as the answer or the error arrives. "One question in flight" (10.3) is also enforced in the UI: Send and the suggestion buttons are disabled while pending.
3. **The draft lives in RunPage.** "Draft kept on error" is met inside the tab. Keeping the draft in the page also lets the section prefill work and keeps a draft through tab switches. The pending request itself belongs to the Advisor tab's `useSendChat`. If the reader leaves the tab mid-question, the answer is still stored and the thread is re-read on return (the hook's own `onSuccess` invalidates the query). A second question sent meanwhile gets the backend's `chat_busy` message.
4. **Composer focus only follows a click on "Ask the advisor about this"** (one-shot `focusComposer` flag, cleared once used). Opening the Advisor tab with the arrow keys leaves focus on the tab list, so roving tabindex still works (14.8.5: no focus moves without a user action).
5. **"A link to the run" for an unavailable Advisor** is a real `<Link to="/runs/{id}">` labelled "Open the overview". On the run page, `onShowOverview` turns it into a switch to the Overview tab, because a link to the page the reader is already on would do nothing. In practice this state is reached for a failed or cancelled run that has a partial result, since tabs only show for finished runs.
6. **"Generate strategy" in the Advisor sends `{ mode: 'missing' }` with no constraints.** This is the same call as the Strategy tab's retry. Choosing resources stays on the Strategy tab ("Change resources and regenerate"). The offer appears only when the strategy is wholly absent, as 14.6 says. A partly generated strategy is handled by the Strategy tab's per-section "Try again".
7. **Market and Competitors buttons are added in `RunPage.panel()`** instead of inside `MarketTab.tsx` / `CompetitorsTab.tsx`. It is one `withAsk(...)` line per tab, and the button sits after the tab's content. The M2 files stay untouched. Each button shows only when that analysis exists, and Strategy buttons show only for parts that exist: asking about a failed part would only return the "not in your results" answer.
8. **Prefilled question wording** (`ADVISOR_QUESTIONS`) is UI copy that the plan does not give. Each question contains a keyword from the backend's topic-routing map (`agents/advisor_agent.py` `ROUTES`: segment, competitor, strengths/weaknesses/SWOT, risk, features/first release, channel/experiment), so the right section is expanded.
9. **Error wording.** "Cancelled. Your question is still here." and "Write a question first." are new UI strings (the plan names none for these cases). The too-long message reuses the backend's 12.4 wording "Write a question of up to {n} characters.".
10. **No new animation.** The "Thinking" row uses a static icon, not a spinner (14.8.6).
11. **Stale comment left for T18.** `RunPage.tsx` still says above `PRINTED_TABS` that "The two Milestone 3 tabs hold placeholders for now". T18 owns that constant and the print rules (14.7: Strategy printed, Advisor excluded), so neither the constant nor its comment was touched.
12. **Sonner's toaster** adds its own `aria-live="polite"` region inside `Providers`. The "announced once" test counts live regions inside the Advisor tab's root only. The tab has exactly one.

## Commands run and results

| Command | Result |
|---|---|
| `python .agents\tasks\m3-t17\hashes.py save` | 82 uncommitted files hashed |
| `Get-FileHash` / `Get-Item data\runs.db` (start) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z |
| `npx tsc --noEmit` (after the source edits) | Clean |
| `npx vitest run src/features/advisor src/lib/noRawHtml.test.ts src/features/run src/features/strategy` (`vitest-1.log`) | 178 tests: 175 passed, 3 failed. All three were faults in the new tests: a missing `await findByRole` on first load, `rerender` without providers, and a live-region count that included Sonner's region. Fixed in the test files only |
| `npx vitest run src/features/advisor` (`vitest-2.log`) | 45 tests: 44 passed, 1 failed (the live-region count again, now scoped to the tab root). Fixed |
| `npm run typecheck` (`typecheck.log`) | Clean (exit 0), app and e2e |
| `npm test` (`npm-test.log`) | **34 files, 469 passed** (430 after T16 + 39 new); **0** lines matching `unhandled`, `onUnhandledRequest` or `MSW]`. `not wrapped in act` lines: 5, the same as T16's log |
| `npm run build` (`build.log`) | Built. Entry chunk `index-o5Xumwi0.js` **268.79 kB / 85.54 kB gzip** (T16: 268.79 / 85.55; baseline 268.78 / 85.54). RunPage chunk 141.21 kB / 35.19 kB gzip (T16: 126.65 / 30.60) |
| `python .agents\tasks\m3-t17\undo_check.py` | Both edited tests match their pre-edit hashes (table above) |
| `python .agents\tasks\m3-t17\hashes.py check` (end) | Only the nine files listed in Files |
| `Get-FileHash` / `Get-Item data\runs.db` (end) | 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296, 2026-11-08T15:31:17Z (unchanged) |

Playwright was not run: T19 owns the browser specs (axe at three widths, keyboard spec for the composer and the confirm dialog), and the brief's frontend gate is typecheck, `npm test` and build. The ui_v2 screenshots spec was not run. Nothing was committed, pushed, reset, reverted or stashed. No branch was created or switched. No `.env` file and no `data/runs.db` content was opened. No live provider call was made.

# T10 review: Advisor service (R4)

Verdict: APPROVED. No blockers.

## Scope and file check
- `hashes.py check` against `baseline_hashes.json` (saved 12:20:27, after the T9 review at 12:18:40) lists only `new agents/advisor_agent.py` and `new tests/test_m3_advisor.py`. These are the two new files the T10 entry names. Its "Existing files: none expected" holds.
- No existing test was edited. `tests/test_m3_advisor.py` imports helpers from the T5 to T7 test modules without changing them.
- Under `.agents`, only `m3-t10\` was written after the baseline. The `m3-t1` to `m3-t9` folders are untouched.
- `agents/advisor_agent.py` has no comments or docstrings. The `# ---` section dividers in the new test file follow the convention of the approved M3 test files.

## Requirement check (Section 18 T10; 10.2 to 10.6; A.0, A.4)
- **Routing (10.4.1):** `ROUTES` and `route_question` use word-boundary regexes and cover all 8 sections, including every plan example. One deviation: "customers" matches only the plural. The coder recorded it, and it is consistent with the plan's example word.
- **Context (10.4.2):** `context_facts` and `build_context` always include IDEA, CON, SUM and VER, plus the headline facts of every section. Matched sections are expanded in full. The cap comes from `chat_context_max_chars`. `_drop_queue` drops non-matched facts first, starting from the end, then trims matched facts in T3 `trim_queue` order. IDEA and CON are never dropped. The tests check this exact drop order.
- **History (10.4.3):** `recent_exchanges` uses the `chat_history_turns` window, oldest first. Each exchange is shortened to 1,200 characters, and tags are stripped from it.
- **Prompt and canary (10.4.4, A.4):** No A.0 rule was removed. The basis rule is adapted as A.4 says. All A.4 lines are present, and the canary appears only in the system part. `new_canary` creates a fresh marker for each question. The `<facts>`, `<conversation>` and `<question>` blocks are delimited, and tags inside stored text, history or the question cannot open or close a block.
- **Call (10.4.5):** `call_structured(system, user, AdvisorDraft, caller=generate_json)` is the same call the T5 to T7 agents make. Provider errors propagate and nothing is built. The 10.7 error mapping is T11's job.
- **Missing section:** If every data section a question routes to is absent, a code-built `no_evidence` reply names the missing sections, with no model call. This matches 10.4 and A-R4 #8.
- **Checks 1 to 9 (10.5):** `check_reply` implements each check:
  - 1: `split_refs` removes invalid refs.
  - 2 and 3: `_basis` does the downgrades.
  - 4: `figure_supported` applies the 7.5 check 4 rule. When no paragraph remains, the reply is `no_evidence` with `MSG_NO_EVIDENCE`.
  - 5: `overclaims` removes the paragraph.
  - 6: a canary or a system-prompt line in the text, refs or follow-ups gives the refusal. This runs before check 7.
  - 7: `in_scope = false` returns only the out-of-scope message.
  - 8: paragraphs are cut to 600 characters and at most 5; follow-ups to 120 characters and at most 3.
  - 9: control characters are stripped.

  Paragraph `sections` and `sources` are computed from the valid refs. The output fits the `ChatMessage` and `ChatParagraph` limits.
- **Suggestions (10.6):** Built deterministically with no LLM call: top risk, first MVP feature, start-here channel, first verify-next item and closest competitor, keeping the first four.
- **No search:** `advisor_agent.py` imports nothing from search. The test patches `web_search_agent.search` and `requests.post` with spies and confirms that neither is called.

## Verification I ran
- `pytest tests/test_m3_advisor.py`: 76 passed, 1 warning.
- Full backend suite: 2325 passed, 1 warning (the Starlette/httpx deprecation warning, as in the baseline). This matches the coder's report: 2249 after T9 plus 76 new.
- `data/runs.db` (checked with Get-FileHash/Get-Item only): SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17Z. All three match the brief.
- No `.env` file or database content was opened. No live calls were made, and no git state was changed.

## Recorded open points (not blockers; for the final report)
- "customers" matches only the plural.
- The 10.7 error messages are left to T11.
- The Advisor call uses the default output-token limit.
- Replies get no secret scan, because 7.5 check 10 covers the strategy stages only; T12 tests for leaks.

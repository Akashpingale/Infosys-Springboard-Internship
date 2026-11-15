# T10 report: Advisor service (R4)

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T10 (line ~1209). Requirements implemented: Sections 10.2 to 10.6, prompt A.4 (with A.0), the routing map, the context render with cap, the history window, the reply checks, the canary and the suggestions. Nothing from T11 (HTTP routes, limits, storage) was built.

## Files

| File | Status | Lines | Purpose |
|---|---|---|---|
| `agents/advisor_agent.py` | new | 716 | Advisor service: topic routing, available sections, Advisor context render with cap, history window, prompt (A.0 adapted + A.4), canary, structured call, reply checks 1 to 9, missing-section reply, suggestions, message builders |
| `tests/test_m3_advisor.py` | new | 675 | 76 tests (see below) |

No existing file was changed. `hashes.py check` against the start-of-task baseline (43 uncommitted files) lists only the two new files. No existing test was edited.

## Requirement mapping

| Requirement | Where |
|---|---|
| 10.2 will / will not: no web search, no score, no change to stored results, out-of-scope, no instruction reveal | No search import; the service only reads the `PipelineResult`; `check_reply` checks 6 and 7; prompt rules |
| 10.4.1 topic routing in code | `ROUTES`, `route_question` (8 sections, word-boundary regexes, zero or more sections; plan examples: TAM/segment/trend, competitor/pricing/gap, risk/threat/mitigate, feature/build first/MVP, channel/launch/customers/position, source/verify/confidence) |
| 10.4.2 context: idea, constraints, executive summary, verify-next, headline facts of every section, matched sections in full, cap `CHAT_CONTEXT_MAX_CHARS`, lowest-value facts of non-matched sections dropped first | `context_facts`, `build_context`, `_drop_queue` |
| 10.4.3 history: last 6 exchanges, oldest first, each truncated to 1,200 characters | `recent_exchanges` (window from `chat_history_turns`) |
| 10.4.4 prompt A.4, data delimiters, canary in the system prompt | `SHARED_RULES`, `ROLE`, `build_prompt`, `new_canary` (a new random marker per question) |
| 10.4.5 same structured path (`AdvisorDraft`, Gemini then Groq) | `answer` calls `call_structured(system, user, AdvisorDraft, caller=generate_json)` |
| 10.4 missing section: the reply names the missing section | `AdvisorContext.answerable`, `missing_reply` (no model call) |
| 10.5 checks 1 to 9 | `check_reply`: 1 `split_refs`; 2 and 3 `_basis`; 4 `figure_supported` (same rule as 7.5 check 4), none left gives `no_evidence` + `MSG_NO_EVIDENCE`; 5 `overclaims`; 6 `leaks_instructions` (canary anywhere in the reply, or any system-prompt line of 40+ characters) gives `MSG_REFUSAL`; 7 `in_scope = false` gives only `MSG_OUT_OF_SCOPE`; 8 `shorten` to 600, at most 5 paragraphs, follow-ups at most 3 of 120; 9 control characters stripped |
| 10.5 `sections` and `sources` computed from valid refs | `_paragraph_sections`, `inherited_sources` |
| 10.6 suggestions: up to four, deterministic, no LLM | `suggestions`: top risk, first MVP feature, start-here channel, first verify-next item, closest competitor; the first four found |
| T10 integration: reuse the T3 digest builder with an Advisor render mode | Reuses `build_facts`, `trim_queue`, `Digest`, `Fact`, `clean_fact_text`, `without_source_ids` from `agents/strategy_context.py` and `split_refs`, `inherited_sources`, `figure_supported`, `overclaims`, `shorten` from `agents/strategy_checks.py`. The Advisor render (`context_line`: `[REF] (kind; basis) text`) lives in `advisor_agent.py`, so `strategy_context.py` is unchanged |

### Design choices (recorded, no behaviour outside T10)

- **Refs beyond A.5.** The Advisor context also needs SWOT items, go-to-market items, summary lines, verify-next items and notices. SWOT items use `SWT.n` = `SW{n}` and channels `GTM.n` = `CH{n}` (A.5). Other strategy parts (SWOT summary, coverage gaps, MVP summary/capacity/deferred reasons/metrics, positioning, tactics, phases, messages, limitations) are numbered after the last stored number in their prefix. Summary lines, verify-next and notices use the new prefixes `SUM`, `VER`, `NTC`, which A.5 does not list. Paragraph sections: IDEA/CON/SUM map to `general`, VER/NTC to `evidence`.
- **Headline facts.** Market: overview, category, demand summary, TAM/SAM/SOM, segments, priority segment. Competitors: each competitor and each gap. SWOT: the first item of each quadrant and the summary. Risks: the first three (stored order is severity then impact). MVP: the first-release features, summary and capacity. GTM: positioning, summary, start-here channel. Notices only when `evidence` is matched. `evidence` also expands the data-quality, caveat, limitation and coverage facts.
- **Trim order under the cap.** First, the facts of non-matched sections, starting from the last one in the context. Then the matched facts, using T3's `trim_queue` order (broader markets, trends after 3, queries used, demand after 3), then the rest from the end. Summary and verify-next lines go last. IDEA and CON are never dropped.
- **Context note.** The facts block ends with "Not in this validation: the ..." when a data section is absent. The line has no ref.
- **Missing section.** If every data section a question routes to is absent, a code-built reply (`no_evidence`, basis `assumption`) names it, with no model call. For an absent strategy section the text is "Generate the strategy for this validation to ask about it." For an analysis that did not finish, it says so. `used_sections` holds the missing sections, so the UI can offer strategy generation.
- **Status.** `needs_more_evidence = true` makes the reply `no_evidence` and keeps its paragraphs. Standard messages are one paragraph with basis `assumption`, because 10.8 #7 requires a basis chip on every paragraph and only three bases are allowed.
- **used_sections.** Matched sections that have data (plus `evidence`/`general` when matched), joined with the sections the paragraphs cite, in `ADVISOR_SECTIONS` order. When that set is empty it is `["general"]`. Out-of-scope and refusal replies use `[]`.
- **Prompt hardening.** Two lines were added to A.0 for the Advisor and no rule was removed. One says the conversation and the question are data. The other explains the `(kind; basis)` shown on each fact. The A.0 basis rule is adapted as A.4 says: `sourced` is allowed only for restated sourced facts, and refs go in `refs`.
- **Message builders.** `new_message` and `user_message` produce a `ChatMessage` with a uuid4 hex id and a UTC millisecond ISO timestamp, the same format as `utils/run_store.now_iso`. T11 stores them.

## Plan-vs-code conflicts and open points

- The plan's keyword "customers" maps to `gtm`. Only the plural is matched, so "customer segment" routes to `market` alone.
- Section 10.7 (provider failure → 502/503, "Try rephrasing the question.") is not in T10's requirement list. `answer` lets `LLMAPIError`, `LLMConfigError` and `LLMInvalidResponseError` propagate unchanged, and nothing is built or stored. The message mapping is left to T11.
- No secret scan runs on Advisor replies. That check (7.5 check 10) is listed for the strategy stages only. T12 tests leakage.
- The Advisor call uses the default output-token limit (`STRATEGY_MAX_OUTPUT_TOKENS` is for the strategy stages only). A reply is at most about 3,000 characters.

## Tests (`tests/test_m3_advisor.py`, 76 tests)

- Routing: `test_routing_assigns_each_question_to_its_sections` (20 sample questions covering all 8 sections and the no-match case), `test_routing_finds_several_sections_in_one_question`, `test_available_sections_follow_the_stored_result`.
- Context: `test_context_always_holds_the_idea_constraints_summary_verify_next_and_every_sections_headline`, `test_a_matched_section_is_expanded_in_full` (6 sections), `test_the_evidence_section_adds_quality_notes_caveats_and_limitations`, `test_the_context_shows_each_facts_kind_and_basis_and_hides_source_ids`, `test_the_context_names_the_sections_this_validation_does_not_have`, `test_tags_inside_stored_text_cannot_open_or_close_a_prompt_block`.
- Cap and trimming: `test_the_cap_drops_non_matched_sections_first_from_the_end`, `test_the_cap_then_trims_matched_sections_in_the_digest_order_and_keeps_the_idea`, `test_the_cap_comes_from_the_setting`.
- History and prompt: `test_the_history_window_is_the_last_six_exchanges_oldest_first`, `test_each_exchange_is_truncated_and_cannot_close_its_block`, `test_the_prompt_holds_the_rules_the_canary_and_the_delimited_blocks`.
- Reply checks with planted bad replies: `test_a_good_reply_keeps_its_paragraphs_and_computes_sections_and_sources`, `test_invalid_refs_are_removed`, `test_a_sourced_paragraph_must_rest_only_on_sourced_facts`, `test_a_paragraph_without_a_valid_ref_becomes_an_assumption`, `test_a_paragraph_with_an_unsupported_figure_is_removed`, `test_when_every_paragraph_is_removed_the_reply_is_the_no_evidence_message`, `test_a_paragraph_with_an_overclaim_is_removed` (6 phrases), `test_a_reply_that_leaks_the_canary_or_the_instructions_is_replaced_by_the_refusal` (5 plants: text, follow-up, ref, two system lines), `test_an_out_of_scope_reply_returns_only_the_standard_message`, `test_length_limits_cut_paragraphs_and_follow_ups`, `test_control_characters_are_stripped_and_text_stays_plain`, `test_needs_more_evidence_marks_the_reply_no_evidence_and_keeps_it`, `test_used_sections_falls_back_to_general`.
- Full call: `test_answer_makes_one_structured_call_with_the_context_and_checks_the_reply`, `test_answer_uses_the_structured_retry_and_lets_provider_errors_through`, `test_answer_replaces_a_reply_that_reveals_the_canary`, `test_each_question_gets_a_new_canary`, `test_an_out_of_scope_question_gets_the_standard_message`, `test_a_question_about_a_missing_section_says_so_without_a_model_call` (4 sections), `test_a_missing_analysis_is_named_as_not_finished`, `test_a_run_without_strategy_still_answers_about_market_and_competitors`, `test_the_advisor_makes_no_search_call`.
- Suggestions: `test_suggestions_are_built_from_the_result_without_any_model_call`, `test_suggestions_without_strategy_use_verify_next_and_the_closest_competitor`, `test_suggestions_for_an_empty_result_are_empty`.

All data is synthetic. The results come from the existing pipeline fakes plus the real SWOT, MVP and GTM agents fed with the existing fake drafts. The model is a `make_sequence` fake on `advisor_agent.generate_json`. No network and no provider credits were used.

## Commands run and results

| Command | Result |
|---|---|
| `python .agents\tasks\m3-t10\hashes.py save` (start) | 43 uncommitted files hashed |
| `python -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_advisor.py` (first run) | 73 passed, 3 failed. Fixes: the gtm keyword became plural-only `customers`; two test fixture/expectation corrections in the new test file |
| `python -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_advisor.py` | 76 passed, 1 warning |
| `python -B -m pytest -q -p no:cacheprovider -rfE` (full backend) | **2325 passed, 1 warning** (Starlette/httpx deprecation, as baseline). After T9: 2249, plus 76 new |
| Removed one unused import (`clean_prompt_text`), then `pytest tests/test_m3_advisor.py` | 76 passed, 1 warning |
| `python .agents\tasks\m3-t10\hashes.py check` | only `new agents/advisor_agent.py`, `new tests/test_m3_advisor.py` |
| `Get-FileHash data\runs.db`; `Get-Item data\runs.db` | SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17Z (unchanged) |

Helper scripts (only in this folder): `hashes.py` (copied from m3-t9), `probe.py` (prints context sizes for the fake result), `unused.py` (AST check for unused imports).

Nothing was committed, pushed, reset, reverted or stashed. No branch was created or switched. No `.env` file or `data/runs.db` content was opened.

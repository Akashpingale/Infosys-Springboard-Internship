# T11 report: Chat API (R4)

Plan entry: MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 18, T11 (line ~1219). Requirements implemented: Section 10.3 (session model and limits), 10.7 (failure behaviour, server side), 12.2 to 12.4 for the three chat routes, 13.3 (what is stored and logged). Nothing from T12 or later was built.

## Files

| File | Status | Size | Purpose |
|---|---|---|---|
| `routes/chat_routes.py` | new | 156 lines | `GET`, `POST`, `DELETE /api/runs/{run_id}/chat`; `ChatGate` (one question in flight per run, cooldown, concurrency semaphore); `ChatRoute` (maps request validation errors to `chat_message_invalid`) |
| `app.py` | modified | +5 lines (file is +7/-0 vs HEAD; T8 added the other 2) | Imports and registers `chat_router`; creates `app.state.chat_gate = ChatGate()` next to `app.state.run_manager` |
| `tests/test_m3_chat_api.py` | new | 659 lines, 39 tests | See below |

`utils/run_store.py` is not changed: the cascade (`delete` removes `chat_messages` rows in the same transaction) is already there from T2, as the entry says. `hashes.py check` against the start-of-task baseline (45 uncommitted files) lists only `changed app.py`, `new routes/chat_routes.py` and `new tests/test_m3_chat_api.py`. No existing test was edited.

## Requirement mapping

| Requirement | Where |
|---|---|
| 12.2 `GET /api/runs/{id}/chat` returns `{ messages, suggestions, available_sections, remaining_turns, limits }` | `read_chat` builds `ChatThread`: stored messages in `seq` order, `advisor_agent.suggestions`, `advisor_agent.available_sections`, remaining turns, limits from `meta_routes.chat_limits()` (the same values `/api/meta` publishes) |
| 12.2 `POST /api/runs/{id}/chat` with `{ "message" }` returns `{ message, remaining_turns }`; the user message is stored with it | `ask`: `advisor_agent.answer(result, question, history)`, then `ChatStore.append(run_id, user, reply)` writes both rows in one transaction |
| 12.2 `DELETE /api/runs/{id}/chat` 204 | `clear_chat` → `ChatStore.clear` |
| 10.3 availability: `state = done` with a `complete` or `partial` result, otherwise 409 | `_available` reads the run through `RunManager.get` (the in-memory run while it is active, otherwise the stored row) and raises `ChatUnavailableError` (409 `chat_unavailable`) for queued, running (including a strategy job on a saved run), failed and cancelled runs |
| 10.3 `CHAT_MAX_USER_TURNS` | Counted from stored user messages (`ChatStore.count(run_id, "user")`); at the limit 409 `chat_limit_reached`; clearing gives the turns back |
| 10.3 `CHAT_MAX_MESSAGE_CHARS`, 12.3 validation (trimmed, control characters stripped, 1 to n characters, not only whitespace) | `ChatRequest` (T1) does the cleaning and the check; `ChatRoute` turns any request validation error on these routes (empty, whitespace, too long, missing, null, wrong type, unknown field, invalid JSON) into 422 `chat_message_invalid` "Write a question of up to {n} characters." with n from the setting |
| 10.3 one question in flight per run | `ChatGate.turn` marks the run busy; a second question gets 409 `chat_busy` |
| 10.3 cooldown `CHAT_COOLDOWN_S` | `ChatGate.turn`: a question on the same run within the cooldown of the previous one gets 429 `chat_cooldown`; per run; uses the module-level `clock` (monkeypatched in tests, as `deadline.clock` is) |
| 10.3 global concurrency `CHAT_MAX_CONCURRENT` | `threading.BoundedSemaphore` in `ChatGate`, sized from the setting when the app is created; extra questions wait for a slot |
| T11 atomic store; nothing stored on failure (10.7, A-R4 #6) | Both messages are written by one `append` call after a successful answer. Provider failures (`LLMAPIError` 502, `LLMConfigError` 503) and any other error leave the store untouched and free the run |
| 10.7 invalid model output after retry: "Same, plus 'Try rephrasing the question.'" | `LLMInvalidResponseError` is re-raised with the message `"{its message} Try rephrasing the question."` (502 `llm_invalid_response`) |
| 10.7 run deleted meanwhile → 404 | `ChatStore.append` returns False when the run row is gone → `RunNotFoundError`; nothing is stored |
| 10.3 deleting a run deletes its thread | Existing `RunStore.delete` (T2); tested through `DELETE /api/runs/{id}` |
| 13.2 / 13.3 redaction, no prompts or provider names stored, logs without question text | `ChatStore` uses the store's redaction; only `ChatMessage` JSON is stored; the route logs the run id, the question length and the error class only |
| 12.4 error codes | Reuses the T1 classes: `ChatUnavailableError`, `ChatLimitError`, `ChatBusyError`, `ChatCooldownError`, `ChatMessageInvalidError`, plus the existing `RunNotFoundError` and mapped provider errors |

## Design choices and plan-vs-code points (recorded; no behaviour outside T11)

- **Store access.** `RunManager` has no public store property, and `utils/run_manager.py` is not in T11's file list. The route builds `ChatStore(manager._store)`. `ChatStore` itself (T2) already uses the store's private `_use` and `_clean`, so this follows the existing pattern.
- **Availability on GET.** The 409 `chat_unavailable` rule is applied to `GET` and `POST`. 10.3 says "the endpoint returns a plain 409 and the tab explains why", and 14.6 needs the tab to know when the run is not finished. `DELETE` only checks that the run exists (404), so clearing works on any saved run.
- **Clear while a question is in flight.** `DELETE` returns 409 `chat_busy` in that case. Otherwise the pending answer would be stored right after the clear, and the cleared thread would not start empty (10.3 "a new thread starts empty").
- **Order of checks on POST.** Body validation (422) runs first because FastAPI parses the body before the handler. Then 404, then 409 `chat_unavailable`, then 409 `chat_limit_reached`, then 409 `chat_busy`, then 429 `chat_cooldown`, then the wait for a concurrency slot.
- **Cooldown clock.** The cooldown counts from the moment the previous question was accepted, whether it succeeded or failed.
- **Concurrency overflow.** No error code exists for it in 12.4, so a question over `CHAT_MAX_CONCURRENT` waits for a slot. Provider calls already have their own timeouts.
- **Limits state.** The busy set, cooldown times and semaphore live in memory on `app.state.chat_gate`, created in `create_app` (no database file is opened). They reset when the server restarts. This fits the single-user local app (10.3).
- **Two `ChatLimits` classes.** One is in `models/chat.py` (T1) and one in `models/api.py` (T8), with the same fields. `ChatThread` needs the T1 class, so the route copies `chat_limits()` into it. The OpenAPI schema still has a single `ChatLimits` component, and the `MetaResponse.chat` reference is unchanged (checked with `openapi_names.py`).
- **OpenAPI 422 on GET and DELETE.** FastAPI adds a default 422 entry to every route with a path parameter. These two routes have no body, so that response cannot occur.

## Tests (`tests/test_m3_chat_api.py`, 39 tests)

- Asking and reading: `test_a_question_gets_a_checked_answer_and_the_exchange_is_stored`, `test_the_thread_holds_suggestions_sections_turns_and_limits`, `test_a_run_with_strategy_lists_every_section`, `test_the_thread_survives_a_reload` (new app and manager on the same temp file), `test_the_earlier_exchanges_are_sent_with_the_next_question`, `test_a_partial_run_is_available`.
- Clear and delete: `test_clearing_removes_the_thread_and_gives_the_turns_back`, `test_deleting_the_run_deletes_its_thread`, `test_an_unknown_run_is_404_on_every_chat_route` (GET, POST, DELETE).
- Availability: `test_a_running_run_answers_409_until_it_has_finished`, `test_failed_and_cancelled_runs_are_unavailable`.
- Message validation: `test_an_invalid_message_is_refused_with_chat_message_invalid` (8 bodies: empty, whitespace, only control characters, 1001 characters, missing, null, number, unknown field), `test_a_body_that_is_not_json_is_refused_the_same_way`, `test_the_message_is_trimmed_and_cleaned_and_may_use_the_full_length`, `test_the_length_limit_follows_the_setting`.
- Limits: `test_the_twenty_sixth_question_is_refused_until_the_thread_is_cleared` (default 25), `test_the_turn_limit_follows_the_setting`, `test_a_question_within_the_cooldown_is_refused` (per run, default-style 2 s with a fake clock), `test_one_question_in_flight_per_run` (second question and clear both 409 `chat_busy`), `test_at_most_two_questions_are_answered_at_once` (3 runs, at most 2 model calls at once, all 3 answered), `test_the_concurrency_follows_the_setting`.
- Failures: `test_a_provider_failure_stores_nothing` (502 `llm_api_error`, 503 `llm_not_configured`), `test_invalid_model_output_after_the_retry_asks_to_rephrase`, `test_an_unexpected_failure_stores_nothing_and_frees_the_run`, `test_a_run_deleted_during_the_answer_is_404_and_nothing_is_stored`.
- Without strategy: `test_a_run_without_strategy_answers_about_the_market_and_says_strategy_is_missing` (second question answered with no model call).
- Storage and logs: `test_a_key_in_a_question_is_not_stored` (fake key built from parts, raw temp-db rows checked), `test_the_question_text_is_never_logged`.
- Schema: `test_the_chat_routes_are_published`.

Every test uses fakes. The results come from the existing pipeline fakes (`tests.m3_fakes.full_result`), and the strategy results from the real agents fed with the existing fake drafts. Runs go through `FakePipeline` and a `RunStore` in `tmp_path`. The Advisor model is a `make_sequence` fake, or a `HeldAdvisor` that blocks, on `advisor_agent.generate_json`. No network access and no provider credits were used.

## Commands run and results

| Command | Result |
|---|---|
| `python .agents\tasks\m3-t11\hashes.py save` (start) | 45 uncommitted files hashed |
| `python -B -m pytest -q -p no:cacheprovider -rfE tests/test_m3_chat_api.py` (first run) | 23 passed, 16 failed. Causes: `ChatThread` needs the `models.chat.ChatLimits` class, not the `models.api` one (fixed in the route); the citation test picked a market fact without sources (fixture fix in the new test) |
| `python -B .agents\tasks\m3-t11\openapi_names.py` | One `ChatLimits` component; `MetaResponse.chat` and `ChatThread.limits` both reference it |
| `pytest tests/test_m3_chat_api.py --tb=short -p no:logging` | 37 passed, 1 failed, 1 error. The error came from `-p no:logging`, which removes `caplog`. The failure: the DELETE route also lists FastAPI's default 422, so that assertion in the new test became a subset check |
| `pytest tests/test_m3_chat_api.py` | **39 passed**, 1 warning |
| `python -B -m pytest -q -p no:cacheprovider -rfE` (full backend) | **2364 passed, 1 warning** (the Starlette/httpx deprecation warning, as in the baseline). After T10: 2325, plus 39 new |
| `pytest tests/test_m3_chat_api.py` three more times (thread tests) | 39 passed each time |
| `python .agents\tasks\m3-t11\hashes.py check` | `changed app.py`, `new routes/chat_routes.py`, `new tests/test_m3_chat_api.py` only |
| `Get-FileHash data\runs.db`; `Get-Item data\runs.db` | SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17Z (unchanged) |

Helper scripts (only in this folder): `hashes.py` (copied from m3-t10) and `openapi_names.py` (prints the chat schema component names from `create_app().openapi()`; it opens no database).

Nothing was committed, pushed, reset, reverted or stashed. No branch was created or switched. No `.env` file and no `data/runs.db` content was opened.

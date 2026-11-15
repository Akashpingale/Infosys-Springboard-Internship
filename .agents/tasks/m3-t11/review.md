# T11 review: Chat API (R4)

Verdict: APPROVED. No blockers.

## Evidence

- Scope. `hashes.py check` against the start baseline (45 files) lists only `changed app.py`, `new routes/chat_routes.py`, `new tests/test_m3_chat_api.py`. The T11 baseline differs from the T10 baseline only in T10's own files (`agents/advisor_agent.py`, `tests/test_m3_advisor.py`), so the baseline is the T10 end state. `utils/run_store.py` is unchanged; its `delete` already removes `chat_messages` rows in the same transaction (run_store.py:192-195). No existing test was edited.
- `app.py`: T11 adds the `ChatGate` and `chat_router` imports, `include_router(chat_router)` and `app.state.chat_gate = ChatGate()`. The `strategy_router` lines in the diff against HEAD come from T8. No database is opened at app creation.
- 12.2 routes (`routes/chat_routes.py`). `GET` returns `ChatThread` with messages in `seq` order, deterministic suggestions, `available_sections`, `remaining_turns` and limits taken from `meta_routes.chat_limits()`. `POST` returns `ChatReply` and stores the user and assistant messages together in one `ChatStore.append` call, only after a successful answer. `DELETE` returns 204.
- 10.3 availability. `_available` requires `state == "done"` and result status `complete`/`partial`, otherwise 409 `chat_unavailable`. Active runs (including a strategy job) are read from memory as running and get 409.
- 10.3 limits. The user-turn limit counts stored user rows (409 `chat_limit_reached`). One question in flight per run gives 409 `chat_busy` (and `DELETE` gives `chat_busy` while a question is pending). The per-run cooldown gives 429 `chat_cooldown`. The global `BoundedSemaphore` is sized from `CHAT_MAX_CONCURRENT`. The busy flag and the semaphore are released in `finally`. `ChatRoute` maps every request-validation error to 422 `chat_message_invalid`, with n taken from the setting. Messages match the 12.4 wording (utils/errors.py:134-165).
- 10.7 failures. Provider errors (502/503) and unexpected errors store nothing and free the run. After the retry, invalid output gets " Try rephrasing the question." appended. If the run is deleted during the answer, `append` returns False, so the reply is 404 and nothing is stored.
- 13.2/13.3. Redaction comes from the store's `_clean`. Only `ChatMessage` JSON is stored. Logs record the run id, the question length and the error class, never the question text.
- I checked one possible issue and it is not reachable. In `ask`, the turn-limit check runs before `gate.turn`. To get a 26th turn, a second request would have to pass its limit check and then enter the turn only after an in-flight answer had completed and been stored, all within microseconds. The busy flag and the cooldown block every realistic interleaving.

## Verification re-run by the reviewer

- `pytest tests/test_m3_chat_api.py`: 39 passed, 1 warning (the Starlette/httpx deprecation warning).
- Full backend `pytest -q -p no:cacheprovider -rfE`: 2364 passed, 1 warning (same warning). Matches the coder's report (2325 after T10, plus 39).
- data/runs.db before and after the test runs: SHA-256 00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D, 311296 bytes, LastWriteTimeUtc 2026-11-08T15:31:17Z (matches the brief).
- No commit, branch, reset or stash was made. No `.env` file or data/runs.db content was opened. No live calls were made.

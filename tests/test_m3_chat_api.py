import json
import logging
import sqlite3
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents import advisor_agent
from agents.advisor_agent import CANARY_PREFIX, build_context, route_question, user_message
from agents.strategy_context import ref_prefix
from app import create_app
from models.schemas import PipelineResult
from orchestrator import STRATEGY_ONLY_STAGES, run_pipeline
from routes import chat_routes
from tests.fakes import LLM_REPLY_NOT_JSON, make_sequence
from tests.m3_fakes import full_result
from tests.pipeline_fakes import PIPELINE_SUBMISSION
from tests.run_fakes import FakePipeline, failing_result, manager_with
from tests.test_m3_gtm_agent import draft as gtm_draft
from tests.test_m3_gtm_agent import use_mvp_reply, use_swot_reply
from tests.test_m3_gtm_agent import use_reply as use_gtm_reply
from tests.test_m3_mvp_agent import as_reply
from tests.test_m3_mvp_agent import draft as mvp_draft
from tests.test_m3_swot_agent import draft as swot_draft
from utils.chat_store import ChatStore
from utils.errors import LLMAPIError, LLMConfigError
from utils.run_store import RunStore

RUNS = "/api/runs"
BODY = {"submission": PIPELINE_SUBMISSION.model_dump(mode="json")}
CANARY = CANARY_PREFIX + "0123456789abcdef"
QUESTION = "How big is the TAM for this idea?"
PLAIN_TEXT = "Start by talking to the first farmers who would use it."
TOO_LONG = "Write a question of up to 1000 characters."
ALL_SECTIONS = ["market", "competitors", "swot", "risks", "mvp", "gtm"]


def reply_json(*paragraphs: dict, follow_ups: list[str] | None = None) -> str:
    return json.dumps({
        "in_scope": True,
        "paragraphs": list(paragraphs) or [{"text": PLAIN_TEXT, "basis": "assumption", "refs": []}],
        "follow_ups": follow_ups or [],
        "needs_more_evidence": False,
    })


PLAIN = reply_json()


def chat(run_id: str) -> str:
    return f"{RUNS}/{run_id}/chat"


def error_of(response) -> dict:
    assert set(response.json()) == {"error"}, response.text
    return response.json()["error"]


def use_advisor(monkeypatch: pytest.MonkeyPatch, *outcomes):
    fake = make_sequence(*(outcomes or (PLAIN,)))
    monkeypatch.setattr(advisor_agent, "generate_json", fake)
    monkeypatch.setattr(advisor_agent, "new_canary", lambda: CANARY)
    return fake


class HeldAdvisor:
    def __init__(self, reply: str = PLAIN) -> None:
        self.reply = reply
        self.release = threading.Event()
        self.entered = threading.Semaphore(0)
        self.lock = threading.Lock()
        self.calls = 0
        self.active = 0
        self.most = 0

    def __call__(self, *args, **kwargs) -> str:
        with self.lock:
            self.calls += 1
            self.active += 1
            self.most = max(self.most, self.active)
        self.entered.release()
        try:
            assert self.release.wait(10), "the test never released the advisor"
            return self.reply
        finally:
            with self.lock:
                self.active -= 1


def hold_advisor(monkeypatch: pytest.MonkeyPatch, reply: str = PLAIN) -> HeldAdvisor:
    held = HeldAdvisor(reply)
    monkeypatch.setattr(advisor_agent, "generate_json", held)
    monkeypatch.setattr(advisor_agent, "new_canary", lambda: CANARY)
    return held


class Clock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def no_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAT_COOLDOWN_S", "0")


@pytest.fixture
def bare(monkeypatch: pytest.MonkeyPatch) -> PipelineResult:
    result, _ = full_result(monkeypatch)
    return result


@pytest.fixture
def full(bare: PipelineResult, monkeypatch: pytest.MonkeyPatch) -> PipelineResult:
    use_swot_reply(monkeypatch, as_reply(swot_draft()))
    use_mvp_reply(monkeypatch, as_reply(mvp_draft()))
    use_gtm_reply(monkeypatch, as_reply(gtm_draft()))
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=bare)
    assert result.status == "complete" and result.swot and result.mvp and result.gtm
    return result


@pytest.fixture
def build(tmp_path: Path):
    made = []

    def factory(pipeline=None, *, secrets: tuple[str, ...] = (), path: Path | None = None) -> TestClient:
        store = RunStore(path or tmp_path / "runs.db", secrets=secrets)
        manager = manager_with(store, pipeline or FakePipeline())
        app = create_app()
        app.state.run_manager = manager
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()
        made.append((client, manager))
        return client

    yield factory
    for client, manager in made:
        client.__exit__(None, None, None)
        manager.shutdown()


@pytest.fixture
def client(build, bare: PipelineResult) -> TestClient:
    return build(FakePipeline(bare))


def start(client: TestClient) -> str:
    response = client.post(RUNS, json=BODY)
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def finished_run(client: TestClient) -> str:
    run_id = start(client)
    assert client.app.state.run_manager.wait(run_id, 10), "the run did not finish in time"
    return run_id


def chats_of(client: TestClient) -> ChatStore:
    return ChatStore(client.app.state.run_manager._store)


def ask(client: TestClient, run_id: str, message: str = QUESTION):
    return client.post(chat(run_id), json={"message": message})


def asked(client: TestClient, run_id: str, message: str = QUESTION) -> dict:
    response = ask(client, run_id, message)
    assert response.status_code == 200, response.text
    return response.json()


def thread(client: TestClient, run_id: str) -> dict:
    response = client.get(chat(run_id))
    assert response.status_code == 200, response.text
    return response.json()


def in_thread(target, *args) -> tuple[threading.Thread, list]:
    out: list = []
    worker = threading.Thread(target=lambda: out.append(target(*args)))
    worker.start()
    return worker, out


# --- asking, reading and the stored thread -------------------------------------------------------


def test_a_question_gets_a_checked_answer_and_the_exchange_is_stored(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, bare: PipelineResult
) -> None:
    context = build_context(bare, route_question(QUESTION))
    ref = next(fact.ref for fact in context.digest.facts if ref_prefix(fact.ref) == "MKT" and fact.sources)
    text = "The market analysis names small farmers as the first group to reach."
    fake = use_advisor(monkeypatch, reply_json({"text": text, "basis": "ai_interpretation", "refs": [ref]}, follow_ups=["Which segment comes next?"]))
    run_id = finished_run(client)

    body = asked(client, run_id)

    assert set(body) == {"message", "remaining_turns"}
    assert body["remaining_turns"] == 24
    message = body["message"]
    assert message["role"] == "assistant" and message["status"] == "ok"
    assert message["follow_ups"] == ["Which segment comes next?"]
    assert [paragraph["text"] for paragraph in message["paragraphs"]] == [text]
    assert message["paragraphs"][0]["basis"] == "ai_interpretation"
    assert message["paragraphs"][0]["sections"] == ["market"]
    assert message["paragraphs"][0]["sources"], "the sources are computed from the valid ref"
    assert "market" in message["used_sections"]
    assert len(fake.calls) == 1
    stored = thread(client, run_id)["messages"]
    assert [item["role"] for item in stored] == ["user", "assistant"]
    assert stored[0]["text"] == QUESTION and stored[0]["paragraphs"] == []
    assert stored[1] == message


def test_the_thread_holds_suggestions_sections_turns_and_limits(client: TestClient, bare: PipelineResult) -> None:
    run_id = finished_run(client)

    body = thread(client, run_id)

    assert body == {
        "messages": [],
        "suggestions": advisor_agent.suggestions(bare),
        "available_sections": ["market", "competitors"],
        "remaining_turns": 25,
        "limits": {"max_message_chars": 1000, "max_user_turns": 25},
    }
    assert body["suggestions"], "the result has a closest competitor and verify-next items"


def test_a_run_with_strategy_lists_every_section(build, full: PipelineResult) -> None:
    client = build(FakePipeline(full))
    run_id = finished_run(client)

    body = thread(client, run_id)

    assert body["available_sections"] == ALL_SECTIONS
    assert body["suggestions"] == advisor_agent.suggestions(full) and len(body["suggestions"]) == 4


def test_the_thread_survives_a_reload(monkeypatch: pytest.MonkeyPatch, build, bare: PipelineResult, tmp_path: Path) -> None:
    use_advisor(monkeypatch)
    first = build(FakePipeline(bare))
    run_id = finished_run(first)
    asked(first, run_id)
    before = thread(first, run_id)

    again = build(FakePipeline(bare), path=tmp_path / "runs.db")

    assert thread(again, run_id) == before
    assert len(before["messages"]) == 2 and before["remaining_turns"] == 24


def test_the_earlier_exchanges_are_sent_with_the_next_question(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    fake = use_advisor(monkeypatch)
    run_id = finished_run(client)

    asked(client, run_id, "What is the first question about the TAM?")
    asked(client, run_id, "And a second one about the market?")

    first_user, second_user = (call[0][1] for call in fake.calls)
    assert "What is the first question about the TAM?" not in first_user.split("<question>")[0]
    assert "What is the first question about the TAM?" in second_user.split("<question>")[0]
    assert PLAIN_TEXT in second_user
    assert [item["role"] for item in thread(client, run_id)["messages"]] == ["user", "assistant", "user", "assistant"]


def test_a_partial_run_is_available(monkeypatch: pytest.MonkeyPatch, build, bare: PipelineResult) -> None:
    use_advisor(monkeypatch)
    client = build(FakePipeline(bare.model_copy(update={"status": "partial", "competitors": None})))
    run_id = finished_run(client)

    assert asked(client, run_id)["message"]["status"] == "ok"
    assert thread(client, run_id)["available_sections"] == ["market"]


# --- clearing and deleting -----------------------------------------------------------------------


def test_clearing_removes_the_thread_and_gives_the_turns_back(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_advisor(monkeypatch)
    run_id = finished_run(client)
    asked(client, run_id)

    response = client.delete(chat(run_id))

    assert response.status_code == 204 and response.content == b""
    body = thread(client, run_id)
    assert body["messages"] == [] and body["remaining_turns"] == 25
    assert client.delete(chat(run_id)).status_code == 204, "clearing an empty thread is fine"
    assert asked(client, run_id)["remaining_turns"] == 24


def test_deleting_the_run_deletes_its_thread(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_advisor(monkeypatch)
    run_id = finished_run(client)
    asked(client, run_id)
    assert chats_of(client).count(run_id) == 2

    assert client.delete(f"{RUNS}/{run_id}").status_code == 204

    assert chats_of(client).count(run_id) == 0
    response = client.get(chat(run_id))
    assert response.status_code == 404 and error_of(response)["code"] == "run_not_found"


@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_an_unknown_run_is_404_on_every_chat_route(monkeypatch: pytest.MonkeyPatch, client: TestClient, method: str) -> None:
    fake = use_advisor(monkeypatch)
    options = {"json": {"message": QUESTION}} if method == "post" else {}

    response = getattr(client, method)(chat("0" * 32), **options)

    assert response.status_code == 404
    assert error_of(response) == {"code": "run_not_found", "message": "This validation could not be found. It may have been deleted."}
    assert fake.calls == []


# --- availability ----------------------------------------------------------------------------------


def test_a_running_run_answers_409_until_it_has_finished(monkeypatch: pytest.MonkeyPatch, build, bare: PipelineResult) -> None:
    fake = use_advisor(monkeypatch)
    pipeline = FakePipeline(bare, block=threading.Event())
    client = build(pipeline)
    run_id = start(client)
    assert pipeline.reached.wait(5)

    for response in (ask(client, run_id), client.get(chat(run_id))):
        assert response.status_code == 409
        assert error_of(response) == {"code": "chat_unavailable", "message": "Questions open once the validation has finished."}
    assert fake.calls == [] and chats_of(client).count(run_id) == 0

    pipeline.block.set()
    assert client.app.state.run_manager.wait(run_id, 10)
    assert asked(client, run_id)["remaining_turns"] == 24


def test_failed_and_cancelled_runs_are_unavailable(monkeypatch: pytest.MonkeyPatch, build, bare: PipelineResult) -> None:
    fake = use_advisor(monkeypatch)
    failed = build(FakePipeline(failing_result()))
    failed_id = finished_run(failed)
    pipeline = FakePipeline(bare, block=threading.Event())
    cancelled = build(pipeline)
    cancelled_id = start(cancelled)
    assert pipeline.reached.wait(5)
    assert cancelled.post(f"{RUNS}/{cancelled_id}/cancel").status_code == 200
    pipeline.block.set()
    assert cancelled.app.state.run_manager.wait(cancelled_id, 10)
    assert failed.get(f"{RUNS}/{failed_id}").json()["state"] == "failed"
    assert cancelled.get(f"{RUNS}/{cancelled_id}").json()["state"] == "cancelled"

    for client, run_id in ((failed, failed_id), (cancelled, cancelled_id)):
        for response in (ask(client, run_id), client.get(chat(run_id))):
            assert response.status_code == 409 and error_of(response)["code"] == "chat_unavailable"
    assert fake.calls == []


# --- message validation -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"message": ""},
        {"message": "   \n\t  "},
        {"message": "\x00\x01\x7f"},
        {"message": "x" * 1001},
        {},
        {"message": None},
        {"message": 42},
        {"message": QUESTION, "extra": True},
    ],
)
def test_an_invalid_message_is_refused_with_chat_message_invalid(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, body: dict
) -> None:
    fake = use_advisor(monkeypatch)
    run_id = finished_run(client)

    response = client.post(chat(run_id), json=body)

    assert response.status_code == 422
    assert error_of(response) == {"code": "chat_message_invalid", "message": TOO_LONG}
    assert fake.calls == [] and chats_of(client).count(run_id) == 0


def test_a_body_that_is_not_json_is_refused_the_same_way(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    fake = use_advisor(monkeypatch)
    run_id = finished_run(client)

    response = client.post(chat(run_id), content=b"{not json", headers={"Content-Type": "application/json"})

    assert response.status_code == 422 and error_of(response)["code"] == "chat_message_invalid"
    assert fake.calls == []


def test_the_message_is_trimmed_and_cleaned_and_may_use_the_full_length(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    fake = use_advisor(monkeypatch)
    run_id = finished_run(client)

    asked(client, run_id, "  How big\x07 is the TAM?\x00  ")
    asked(client, run_id, "q" * 1000)

    texts = [item["text"] for item in thread(client, run_id)["messages"] if item["role"] == "user"]
    assert texts == ["How big is the TAM?", "q" * 1000]
    assert "<question>\nHow big is the TAM?\n</question>" in fake.calls[0][0][1]


def test_the_length_limit_follows_the_setting(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_advisor(monkeypatch)
    monkeypatch.setenv("CHAT_MAX_MESSAGE_CHARS", "200")
    run_id = finished_run(client)

    response = ask(client, run_id, "x" * 201)

    assert response.status_code == 422
    assert error_of(response) == {"code": "chat_message_invalid", "message": "Write a question of up to 200 characters."}
    assert asked(client, run_id, "x" * 200)["remaining_turns"] == 24
    assert thread(client, run_id)["limits"]["max_message_chars"] == 200


# --- limits ------------------------------------------------------------------------------------------


def test_the_twenty_sixth_question_is_refused_until_the_thread_is_cleared(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    fake = use_advisor(monkeypatch)
    run_id = finished_run(client)
    assert chats_of(client).append(run_id, *(user_message(f"Question {number}?") for number in range(24)))
    assert asked(client, run_id)["remaining_turns"] == 0

    response = ask(client, run_id)

    assert response.status_code == 409
    assert error_of(response) == {"code": "chat_limit_reached", "message": "This conversation is full. Clear it to start again."}
    assert len(fake.calls) == 1 and chats_of(client).count(run_id, "user") == 25
    assert thread(client, run_id)["remaining_turns"] == 0
    assert client.delete(chat(run_id)).status_code == 204
    assert asked(client, run_id)["remaining_turns"] == 24


def test_the_turn_limit_follows_the_setting(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_advisor(monkeypatch)
    monkeypatch.setenv("CHAT_MAX_USER_TURNS", "2")
    run_id = finished_run(client)

    assert [asked(client, run_id)["remaining_turns"] for _ in range(2)] == [1, 0]

    response = ask(client, run_id)
    assert response.status_code == 409 and error_of(response)["code"] == "chat_limit_reached"
    assert thread(client, run_id)["limits"]["max_user_turns"] == 2


def test_a_question_within_the_cooldown_is_refused(monkeypatch: pytest.MonkeyPatch, build, bare: PipelineResult) -> None:
    fake = use_advisor(monkeypatch)
    monkeypatch.setenv("CHAT_COOLDOWN_S", "2")
    clock = Clock()
    monkeypatch.setattr(chat_routes, "clock", clock)
    client = build(FakePipeline(bare))
    run_id, other_id = finished_run(client), finished_run(client)
    asked(client, run_id)

    clock.now += 1.5
    response = ask(client, run_id)

    assert response.status_code == 429
    assert error_of(response) == {"code": "chat_cooldown", "message": "Wait a moment before the next question."}
    assert asked(client, other_id)["remaining_turns"] == 24, "the cooldown is per run"
    clock.now += 0.5
    assert asked(client, run_id)["remaining_turns"] == 23
    assert len(fake.calls) == 3


def test_one_question_in_flight_per_run(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    held = hold_advisor(monkeypatch)
    run_id = finished_run(client)
    worker, out = in_thread(ask, client, run_id)
    assert held.entered.acquire(timeout=5)

    second = ask(client, run_id, "Another question about the market?")
    clear = client.delete(chat(run_id))

    held.release.set()
    worker.join(10)
    assert second.status_code == 409
    assert error_of(second) == {"code": "chat_busy", "message": "Wait for the current answer first."}
    assert clear.status_code == 409 and error_of(clear)["code"] == "chat_busy"
    assert out[0].status_code == 200 and held.calls == 1
    assert chats_of(client).count(run_id) == 2
    assert asked(client, run_id)["remaining_turns"] == 23, "the run is free again once the answer is stored"


def test_at_most_two_questions_are_answered_at_once(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    held = hold_advisor(monkeypatch)
    run_ids = [finished_run(client) for _ in range(3)]
    workers = [in_thread(ask, client, run_id) for run_id in run_ids]
    assert held.entered.acquire(timeout=5) and held.entered.acquire(timeout=5)

    assert not held.entered.acquire(timeout=0.5), "the third question waits for a free slot"
    assert held.active == 2

    held.release.set()
    for worker, _ in workers:
        worker.join(10)
    assert [out[0].status_code for _, out in workers] == [200, 200, 200]
    assert held.calls == 3 and held.most == 2
    assert all(chats_of(client).count(run_id) == 2 for run_id in run_ids)


def test_the_concurrency_follows_the_setting(monkeypatch: pytest.MonkeyPatch, build, bare: PipelineResult) -> None:
    monkeypatch.setenv("CHAT_MAX_CONCURRENT", "1")
    held = hold_advisor(monkeypatch)
    client = build(FakePipeline(bare))
    run_ids = [finished_run(client) for _ in range(2)]
    workers = [in_thread(ask, client, run_id) for run_id in run_ids]
    assert held.entered.acquire(timeout=5)

    assert not held.entered.acquire(timeout=0.5)

    held.release.set()
    for worker, _ in workers:
        worker.join(10)
    assert [out[0].status_code for _, out in workers] == [200, 200] and held.most == 1


# --- failures store nothing ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [(LLMAPIError(), 502, "llm_api_error"), (LLMConfigError(), 503, "llm_not_configured")],
)
def test_a_provider_failure_stores_nothing(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, failure: Exception, status: int, code: str
) -> None:
    use_advisor(monkeypatch, failure, PLAIN)
    run_id = finished_run(client)

    response = ask(client, run_id)

    assert response.status_code == status
    assert error_of(response) == {"code": code, "message": type(failure).default_message}
    assert chats_of(client).count(run_id) == 0
    assert thread(client, run_id)["remaining_turns"] == 25
    assert asked(client, run_id)["remaining_turns"] == 24, "the run is free again after a failure"


def test_invalid_model_output_after_the_retry_asks_to_rephrase(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    fake = use_advisor(monkeypatch, LLM_REPLY_NOT_JSON)
    run_id = finished_run(client)

    response = ask(client, run_id)

    assert response.status_code == 502
    assert error_of(response) == {
        "code": "llm_invalid_response",
        "message": "Could not understand the AI reply. Please try again. Try rephrasing the question.",
    }
    assert len(fake.calls) == 2, "the structured path retries once"
    assert chats_of(client).count(run_id) == 0


def test_an_unexpected_failure_stores_nothing_and_frees_the_run(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_advisor(monkeypatch, RuntimeError("boom"), PLAIN)
    run_id = finished_run(client)

    response = ask(client, run_id)

    assert response.status_code == 500 and error_of(response)["code"] == "internal_error"
    assert chats_of(client).count(run_id) == 0
    assert asked(client, run_id)["remaining_turns"] == 24


def test_a_run_deleted_during_the_answer_is_404_and_nothing_is_stored(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    held = hold_advisor(monkeypatch)
    run_id = finished_run(client)
    worker, out = in_thread(ask, client, run_id)
    assert held.entered.acquire(timeout=5)

    assert client.delete(f"{RUNS}/{run_id}").status_code == 204
    held.release.set()
    worker.join(10)

    assert out[0].status_code == 404 and error_of(out[0])["code"] == "run_not_found"
    assert chats_of(client).count(run_id) == 0


# --- a run without strategy ----------------------------------------------------------------------------


def test_a_run_without_strategy_answers_about_the_market_and_says_strategy_is_missing(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    fake = use_advisor(monkeypatch)
    run_id = finished_run(client)

    market = asked(client, run_id)["message"]
    mvp = asked(client, run_id, "Which feature should I build first?")["message"]

    assert market["status"] == "ok" and len(fake.calls) == 1
    assert mvp["status"] == "no_evidence" and mvp["used_sections"] == ["mvp"]
    assert "Generate the strategy for this validation" in mvp["paragraphs"][0]["text"]
    assert len(fake.calls) == 1, "a question about a missing section needs no model call"
    assert thread(client, run_id)["available_sections"] == ["market", "competitors"]


# --- what is stored and logged ---------------------------------------------------------------------------


def test_a_key_in_a_question_is_not_stored(monkeypatch: pytest.MonkeyPatch, build, bare: PipelineResult, tmp_path: Path) -> None:
    key = "chat-" + "planted-" + "key-value-0042"
    use_advisor(monkeypatch)
    client = build(FakePipeline(bare), secrets=(key,))
    run_id = finished_run(client)

    asked(client, run_id, f"Is {key} in the market analysis?")

    connection = sqlite3.connect(tmp_path / "runs.db")
    try:
        rows = connection.execute("SELECT content_json FROM chat_messages WHERE run_id = ?", (run_id,)).fetchall()
    finally:
        connection.close()
    assert len(rows) == 2 and all(key not in row[0] for row in rows)
    assert thread(client, run_id)["messages"][0]["text"] == "Is [redacted] in the market analysis?"


def test_the_question_text_is_never_logged(monkeypatch: pytest.MonkeyPatch, client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    marker = "unusual-marker-word"
    use_advisor(monkeypatch, PLAIN, LLMAPIError())
    run_id = finished_run(client)
    caplog.set_level(logging.INFO)

    asked(client, run_id, f"What does the market say about {marker}?")
    assert ask(client, run_id, f"And the TAM for {marker}?").status_code == 502

    assert marker not in caplog.text
    assert "question of" in caplog.text and "LLMAPIError" in caplog.text


# --- published routes ------------------------------------------------------------------------------------


def test_the_chat_routes_are_published(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    routes = paths["/api/runs/{run_id}/chat"]
    assert set(routes) == {"get", "post", "delete"}
    assert routes["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/ChatRequest")
    assert routes["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ChatReply")
    assert routes["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ChatThread")
    assert set(routes["post"]["responses"]) == {"200", "404", "409", "422", "429", "502", "503"}
    assert {"204", "404", "409", "503"} <= set(routes["delete"]["responses"])

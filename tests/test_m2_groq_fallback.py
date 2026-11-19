"""The Groq fallback for Gemini (utils/llm_client.py and utils/groq_client.py).

Gemini stays the primary LLM. With GROQ_API_KEY set, one Groq attempt answers a Gemini rate limit or
quota error (429), a temporary server error (500, 502, 503, 504) or a timeout. Nothing else falls
back, Gemini is not retried after such a failure, and the Groq attempt keeps the run's time limit and
the 10-second minimum deadline. Without GROQ_API_KEY everything is Gemini only, as before.

Both providers are faked, genai.Client and requests.post as Groq's client calls it, so nothing touches
the network. Time is simulated where the run's time limit matters.
"""

import json
import logging
import os
import re
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import requests
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

import orchestrator
from agents import competitor_analysis_agent as competitor_agent
from agents import market_size
from config import get_settings
from models.schemas import ExtractedIdea, PipelineResult
from scripts import check_groq
from tests.fakes import LLM_REPLY_OK, VALID_EXTRACTION, FakeHTTPResponse
from tests.m2_fakes import COMPETITOR_TARGETED, NO_MARKET_SIZE_RESULTS
from tests.pipeline_fakes import PIPELINE_SEARCH, PIPELINE_SUBMISSION, competitor_replies, market_reply
from utils import deadline, groq_client, llm_client
from utils.deadline import time_left, time_limit
from utils.errors import LLMAPIError, LLMConfigError, LLMInvalidResponseError
from utils.structured import RETRY_INSTRUCTION, call_structured

ROOT = Path(__file__).resolve().parent.parent
GROQ_KEY = "test-groq-key"
SYSTEM = "SYSTEM-PROMPT: return one JSON object."
USER = "USER-PROMPT: describe the idea as JSON."
URL = "/api/validate"
FULL_URL = f"{URL}?include_analysis=true"
BODY = PIPELINE_SUBMISSION.model_dump(mode="json")
# Extraction, market analysis, Phase A and Phase C, in the order the pipeline asks for them.
PIPELINE_REPLIES = (LLM_REPLY_OK, market_reply(), *competitor_replies())

Slow = namedtuple("Slow", "seconds outcome")


class Clock:
    """Simulated time for the deadline module; the fakes move it forward."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _step(outcomes: list, count: int) -> tuple[float, Any]:
    outcome = outcomes[min(count, len(outcomes) - 1)]
    return (outcome.seconds, outcome.outcome) if isinstance(outcome, Slow) else (0.0, outcome)


class Gemini:
    """Stands in for genai.Client. Each call gives the next outcome (the last repeats): text is
    returned, an exception raised. With a clock, a Slow outcome takes its time, and one that needs
    longer than the request's timeout ends at the timeout with httpx.ReadTimeout."""

    def __init__(self, outcomes: list, clock: Clock | None) -> None:
        self.outcomes = outcomes
        self.clock = clock
        self.calls: list[float] = []  # the timeout (s) of each request sent
        self.closed = 0
        self._timeout_s = 0.0

    def __call__(self, **kwargs: Any) -> "Gemini":
        self._timeout_s = kwargs["http_options"].timeout / 1000
        return self

    @property
    def models(self) -> "Gemini":
        return self

    def generate_content(self, **kwargs: Any) -> Any:
        needs, outcome = _step(self.outcomes, len(self.calls))
        self.calls.append(self._timeout_s)
        if self.clock is not None:
            if needs > self._timeout_s:
                self.clock.advance(self._timeout_s)
                raise httpx.ReadTimeout("timed out")
            self.clock.advance(needs)
        if isinstance(outcome, BaseException):
            raise outcome
        return SimpleNamespace(text=outcome)

    def close(self) -> None:
        self.closed += 1


class Groq:
    """Stands in for requests.post as utils/groq_client.py calls it, with the same outcome rules."""

    def __init__(self, outcomes: list, clock: Clock | None) -> None:
        self.outcomes = outcomes
        self.clock = clock
        self.requests: list[SimpleNamespace] = []

    def __call__(self, url: str, headers: Any = None, json: Any = None, timeout: Any = None, **kw: Any) -> Any:
        needs, outcome = _step(self.outcomes, len(self.requests))
        self.requests.append(SimpleNamespace(url=url, headers=headers, body=json, timeout=timeout, other=kw))
        if self.clock is not None:
            if needs > timeout:
                self.clock.advance(timeout)
                raise requests.Timeout("read timed out")
            self.clock.advance(needs)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@dataclass
class Providers:
    gemini: Gemini
    groq: Groq
    waits: list[float]


def use_providers(
    monkeypatch: pytest.MonkeyPatch, gemini: list, groq: list | None = None, clock: Clock | None = None
) -> Providers:
    """The real llm_client and groq_client over fake providers. Retry waits are recorded, and move
    the clock when there is one, instead of sleeping."""
    waits: list[float] = []

    def wait(seconds: float) -> None:
        waits.append(seconds)
        if clock is not None:
            clock.advance(seconds)

    providers = Providers(Gemini(gemini, clock), Groq(groq or [groq_reply("{}")], clock), waits)
    monkeypatch.setattr(llm_client.genai, "Client", providers.gemini)
    monkeypatch.setattr(groq_client.requests, "post", providers.groq)
    monkeypatch.setattr(llm_client, "time", SimpleNamespace(sleep=wait))
    return providers


def gemini_error(code: int, status: str = "ERROR", message: str = "error") -> genai_errors.APIError:
    body = {"error": {"code": code, "message": message, "status": status}}
    cls = genai_errors.ServerError if code >= 500 else genai_errors.ClientError
    return cls(code, body)


def groq_reply(content: str | None) -> FakeHTTPResponse:
    return FakeHTTPResponse(
        200,
        {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": groq_client.MODEL,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        },
    )


def groq_error(status: int, code: str | None = None, message: str = "Something went wrong.") -> FakeHTTPResponse:
    error = {"message": message, "type": "invalid_request_error"}
    if code is not None:
        error["code"] = code
    return FakeHTTPResponse(status, {"error": error})


@pytest.fixture
def groq_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", GROQ_KEY)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(deadline, "clock", fake)
    return fake


# --- configuration ---------------------------------------------------------------------------


def test_no_test_sees_a_real_groq_key() -> None:
    """tests/conftest.py clears GROQ_API_KEY, so a key in the developer's .env cannot switch the
    fallback on, or reach Groq, from a test."""
    assert os.environ.get("GROQ_API_KEY") is None
    assert get_settings().groq_api_key is None and not groq_client.is_configured()


def test_the_groq_key_is_read_at_call_time_and_never_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", f"  {GROQ_KEY}  ")
    settings = get_settings()
    assert settings.groq_api_key == GROQ_KEY and groq_client.is_configured()
    assert GROQ_KEY not in repr(settings) and GROQ_KEY not in str(settings)

    monkeypatch.setenv("GROQ_API_KEY", "   ")
    assert get_settings().groq_api_key is None and not groq_client.is_configured()


def test_env_example_documents_groq_with_a_commented_placeholder() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "# GROQ_API_KEY=your_groq_api_key_here" in text.splitlines()
    assert not re.search(r"^GROQ_API_KEY=", text, re.MULTILINE), "a copied template stays Gemini only"
    assert not re.search(r"gsk_[A-Za-z0-9]{10,}", text), "no real-looking Groq key"


def test_the_local_env_file_is_ignored_by_git() -> None:
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in lines and ".env.*" in lines and "!.env.example" in lines


# --- Gemini answers: Groq is never called ----------------------------------------------------


def test_a_gemini_answer_never_calls_groq(monkeypatch: pytest.MonkeyPatch, groq_key: None) -> None:
    providers = use_providers(monkeypatch, ['{"from": "gemini"}'])

    assert llm_client.generate_json(SYSTEM, USER) == '{"from": "gemini"}'
    assert len(providers.gemini.calls) == 1 and providers.groq.requests == []


# --- the Gemini failures that fall back ------------------------------------------------------

FALLS_BACK = [
    pytest.param(gemini_error(429, "RESOURCE_EXHAUSTED", "You exceeded your current quota."), "rate_limit", 429, id="429_quota"),
    pytest.param(gemini_error(500, "INTERNAL"), "server_error", 500, id="500"),
    pytest.param(gemini_error(502), "server_error", 502, id="502"),
    pytest.param(gemini_error(503, "UNAVAILABLE", "The model is overloaded."), "server_error", 503, id="503"),
    pytest.param(gemini_error(504, "DEADLINE_EXCEEDED"), "server_error", 504, id="504"),
    pytest.param(httpx.ReadTimeout("timed out"), "timeout", None, id="read_timeout"),
    pytest.param(httpx.ConnectTimeout("timed out"), "timeout", None, id="connect_timeout"),
]


@pytest.mark.parametrize(("error", "category", "status"), FALLS_BACK)
def test_these_gemini_failures_are_answered_by_one_groq_attempt(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    groq_key: None,
    error: Exception,
    category: str,
    status: int | None,
) -> None:
    providers = use_providers(monkeypatch, [error], [groq_reply('{"from": "groq"}')])
    with caplog.at_level(logging.INFO):
        assert llm_client.generate_json(SYSTEM, USER) == '{"from": "groq"}'

    assert len(providers.gemini.calls) == 1, "Gemini is not retried"
    assert len(providers.groq.requests) == 1 and providers.gemini.closed == 1
    assert providers.waits == [], "no backoff before the fallback"
    assert f"Gemini failed ({category}, HTTP {status}); trying the Groq fallback" in caplog.text


def test_quota_exhaustion_is_never_retried_on_either_provider(
    monkeypatch: pytest.MonkeyPatch, groq_key: None
) -> None:
    providers = use_providers(monkeypatch, [gemini_error(429, "RESOURCE_EXHAUSTED")], [groq_error(503)])
    with pytest.raises(LLMAPIError) as info:
        llm_client.generate_json(SYSTEM, USER)

    assert info.value.user_message == llm_client.MSG_BUSY
    assert len(providers.gemini.calls) == 1 and len(providers.groq.requests) == 1
    assert providers.waits == []


# --- the Gemini failures that do not fall back -----------------------------------------------

NO_FALLBACK = [
    pytest.param(gemini_error(401, "UNAUTHENTICATED"), LLMAPIError, llm_client.MSG_KEY_REJECTED, id="401_auth"),
    pytest.param(gemini_error(403, "PERMISSION_DENIED"), LLMAPIError, llm_client.MSG_KEY_REJECTED, id="403_auth"),
    pytest.param(gemini_error(400, "INVALID_ARGUMENT", "API key not valid."), LLMAPIError, llm_client.MSG_KEY_REJECTED, id="400_bad_key"),
    pytest.param(
        gemini_error(400, "INVALID_ARGUMENT", "Request contains an invalid argument."),
        LLMAPIError,
        llm_client.MSG_GENERIC,
        id="400_invalid_request",
    ),
    pytest.param(gemini_error(404, "NOT_FOUND"), LLMConfigError, llm_client.MSG_MODEL_NOT_FOUND, id="404_model"),
    pytest.param(httpx.ConnectError("no route"), LLMAPIError, llm_client.MSG_GENERIC, id="connection"),
    pytest.param(RuntimeError("odd state"), LLMAPIError, llm_client.MSG_GENERIC, id="unexpected"),
]


@pytest.mark.parametrize(("error", "raised", "message"), NO_FALLBACK)
def test_these_gemini_failures_never_reach_groq(
    monkeypatch: pytest.MonkeyPatch, groq_key: None, error: Exception, raised: type, message: str
) -> None:
    providers = use_providers(monkeypatch, [error])
    with pytest.raises(raised) as info:
        llm_client.generate_json(SYSTEM, USER)

    assert info.value.user_message == message, "the same message as without Groq"
    assert providers.groq.requests == [] and len(providers.gemini.calls) == 1


def test_a_missing_gemini_configuration_is_not_hidden_by_groq(
    monkeypatch: pytest.MonkeyPatch, groq_key: None
) -> None:
    providers = use_providers(monkeypatch, ['{"ok": true}'])
    monkeypatch.delenv("LLM_API_KEY")
    with pytest.raises(LLMConfigError):
        llm_client.generate_json(SYSTEM, USER)
    assert providers.gemini.calls == [] and providers.groq.requests == []


def test_the_diagnostic_text_call_stays_gemini_only(monkeypatch: pytest.MonkeyPatch, groq_key: None) -> None:
    providers = use_providers(monkeypatch, [gemini_error(429, "RESOURCE_EXHAUSTED")])
    with pytest.raises(LLMAPIError):
        llm_client.generate_text("Reply with the word OK")
    assert providers.groq.requests == []


# --- without GROQ_API_KEY: Gemini only, exactly as before ------------------------------------


@pytest.mark.parametrize(
    ("error", "message", "gemini_calls", "waits"),
    [
        pytest.param(gemini_error(429, "RESOURCE_EXHAUSTED"), llm_client.MSG_RATE_LIMIT, 1, [], id="429"),
        pytest.param(gemini_error(503, "UNAVAILABLE"), llm_client.MSG_BUSY, 3, [1.0, 3.0], id="503_retried"),
        pytest.param(httpx.ReadTimeout("timed out"), llm_client.MSG_TIMEOUT, 1, [], id="timeout"),
    ],
)
def test_without_a_groq_key_gemini_failures_are_handled_as_before(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str, gemini_calls: int, waits: list
) -> None:
    providers = use_providers(monkeypatch, [error])
    with pytest.raises(LLMAPIError) as info:
        llm_client.generate_json(SYSTEM, USER)

    assert info.value.user_message == message
    assert len(providers.gemini.calls) == gemini_calls and providers.waits == waits
    assert providers.groq.requests == []


# --- the Groq request ------------------------------------------------------------------------


def test_the_groq_request_carries_the_gemini_prompts_to_the_official_endpoint(
    monkeypatch: pytest.MonkeyPatch, groq_key: None
) -> None:
    providers = use_providers(monkeypatch, [gemini_error(429)], [groq_reply("{}")])
    llm_client.generate_json(SYSTEM, USER)
    (request,) = providers.groq.requests

    assert request.url == "https://api.groq.com/openai/v1/chat/completions" == groq_client.API_URL
    assert request.headers == {"Authorization": f"Bearer {GROQ_KEY}"} and GROQ_KEY not in request.url
    assert request.body == {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
        "temperature": llm_client.TEMPERATURE,
        "response_format": {"type": "json_object"},
        "reasoning_effort": "low",
        "include_reasoning": False,
        "max_completion_tokens": 4096,
    }
    assert request.timeout == 30.0, "LLM_TIMEOUT_S, as for Gemini"
    assert request.other == {}, "no other options, such as retries or streaming"


@pytest.mark.parametrize(("content", "text"), [('{"a": 1}', '{"a": 1}'), (None, "")])
def test_a_groq_reply_is_returned_as_text_like_a_gemini_one(
    monkeypatch: pytest.MonkeyPatch, groq_key: None, content: str | None, text: str
) -> None:
    use_providers(monkeypatch, [gemini_error(503)], [groq_reply(content)])
    assert llm_client.generate_json(SYSTEM, USER) == text


# --- a failed Groq attempt -------------------------------------------------------------------

GROQ_FAILURES = [
    pytest.param(groq_error(429, "rate_limit_exceeded"), LLMAPIError, llm_client.MSG_RATE_LIMIT, "rate_limit", id="429"),
    pytest.param(
        groq_error(413, "rate_limit_exceeded", "Request too large on tokens per minute (TPM)"),
        LLMAPIError,
        llm_client.MSG_RATE_LIMIT,
        "rate_limit",
        id="413_tpm",
    ),
    pytest.param(groq_error(500), LLMAPIError, llm_client.MSG_BUSY, "server_error", id="500"),
    pytest.param(groq_error(502), LLMAPIError, llm_client.MSG_BUSY, "server_error", id="502"),
    pytest.param(groq_error(503), LLMAPIError, llm_client.MSG_BUSY, "server_error", id="503"),
    pytest.param(groq_error(498), LLMAPIError, llm_client.MSG_BUSY, "server_error", id="498_flex"),
    pytest.param(requests.Timeout("read timed out"), LLMAPIError, llm_client.MSG_TIMEOUT, "timeout", id="timeout"),
    pytest.param(groq_error(401, "invalid_api_key"), LLMAPIError, llm_client.MSG_GROQ_KEY_REJECTED, "auth", id="401"),
    pytest.param(groq_error(403), LLMAPIError, llm_client.MSG_GROQ_KEY_REJECTED, "auth", id="403"),
    pytest.param(
        groq_error(400, "json_validate_failed", "Failed to generate JSON."),
        LLMInvalidResponseError,
        LLMInvalidResponseError.default_message,
        "invalid_json",
        id="400_invalid_json",
    ),
    pytest.param(groq_error(404, "model_not_found"), LLMAPIError, llm_client.MSG_GENERIC, "model_unavailable", id="404"),
    pytest.param(
        groq_error(400, "model_decommissioned"), LLMAPIError, llm_client.MSG_GENERIC, "model_unavailable", id="400_decommissioned"
    ),
    pytest.param(groq_error(400), LLMAPIError, llm_client.MSG_GENERIC, "invalid_request", id="400"),
    pytest.param(groq_error(422), LLMAPIError, llm_client.MSG_GENERIC, "invalid_request", id="422"),
    pytest.param(requests.ConnectionError("no route"), LLMAPIError, llm_client.MSG_GENERIC, "connection", id="connection"),
    pytest.param(FakeHTTPResponse(200, None, "<html>busy</html>"), LLMAPIError, llm_client.MSG_GENERIC, "bad_reply", id="not_json"),
    pytest.param(FakeHTTPResponse(200, {"choices": []}), LLMAPIError, llm_client.MSG_GENERIC, "bad_reply", id="no_choice"),
    pytest.param(
        FakeHTTPResponse(200, {"choices": [{"message": {"content": ["not", "text"]}}]}),
        LLMAPIError,
        llm_client.MSG_GENERIC,
        "bad_reply",
        id="content_not_text",
    ),
]


@pytest.mark.parametrize(("outcome", "raised", "message", "category"), GROQ_FAILURES)
def test_a_failed_groq_attempt_is_a_safe_error_and_the_end_of_the_call(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    groq_key: None,
    outcome: Any,
    raised: type,
    message: str,
    category: str,
) -> None:
    providers = use_providers(monkeypatch, [gemini_error(429, "RESOURCE_EXHAUSTED")], [outcome])
    with caplog.at_level(logging.WARNING, logger="utils.llm_client"):
        with pytest.raises(raised) as info:
            llm_client.generate_json(SYSTEM, USER)

    assert info.value.user_message == message
    assert f"Groq fallback failed ({category}, HTTP " in caplog.text
    assert len(providers.gemini.calls) == 1 and len(providers.groq.requests) == 1, "no further attempt"
    assert GROQ_KEY not in info.value.user_message


def test_an_unexpected_groq_error_is_still_a_safe_app_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None
) -> None:
    use_providers(monkeypatch, [gemini_error(503)])

    def broken(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError(f"broken while holding {GROQ_KEY}")

    monkeypatch.setattr(groq_client, "generate_json", broken)
    with caplog.at_level(logging.WARNING):
        with pytest.raises(LLMAPIError) as info:
            llm_client.generate_json(SYSTEM, USER)

    assert info.value.user_message == llm_client.MSG_GENERIC
    assert "Groq fallback failed (unexpected, RuntimeError)" in caplog.text
    assert GROQ_KEY not in caplog.text and "broken while" not in caplog.text


# --- what is logged --------------------------------------------------------------------------


def test_the_logs_name_the_provider_and_the_category_only(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None
) -> None:
    quota = gemini_error(429, "RESOURCE_EXHAUSTED", f"Quota exceeded for {USER}")
    body = {
        "error": {
            "message": f"BODY-SECRET while reading {USER}",
            "type": "server_error",
            "failed_generation": "GENERATED-TEXT",
        }
    }
    use_providers(monkeypatch, [quota], [FakeHTTPResponse(503, body)])
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(LLMAPIError):
            llm_client.generate_json(SYSTEM, USER)

    lines = [r.getMessage() for r in caplog.records if r.name in ("utils.llm_client", "utils.groq_client")]
    assert lines == [
        "Gemini failed (rate_limit, HTTP 429); trying the Groq fallback",
        "Groq fallback failed (server_error, HTTP 503, 14 characters generated)",
    ], "the length of failed_generation is logged, never its text"
    for hidden in (GROQ_KEY, "test-llm-key", "SYSTEM-PROMPT", "USER-PROMPT", "BODY-SECRET", "GENERATED-TEXT", "Quota"):
        assert hidden not in caplog.text, hidden


def test_a_groq_answer_is_logged_without_its_content(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None
) -> None:
    use_providers(monkeypatch, [gemini_error(503)], [groq_reply('{"answer": "REPLY-TEXT"}')])
    with caplog.at_level(logging.INFO):
        llm_client.generate_json(SYSTEM, USER)

    assert "Groq answered in" in caplog.text and f"({groq_client.MODEL})" in caplog.text
    assert "REPLY-TEXT" not in caplog.text and "USER-PROMPT" not in caplog.text and GROQ_KEY not in caplog.text


# --- the same structured validation ----------------------------------------------------------


def test_a_groq_reply_passes_the_same_structured_validation(monkeypatch: pytest.MonkeyPatch, groq_key: None) -> None:
    use_providers(monkeypatch, [gemini_error(429)], [groq_reply(LLM_REPLY_OK)])
    idea = call_structured(SYSTEM, USER, ExtractedIdea, caller=llm_client.generate_json)
    assert idea == ExtractedIdea(**VALID_EXTRACTION)


def test_an_unusable_groq_reply_gets_the_one_retry_then_fails(monkeypatch: pytest.MonkeyPatch, groq_key: None) -> None:
    providers = use_providers(monkeypatch, [gemini_error(429)], [groq_reply("Sure! Here is the idea.")])
    with pytest.raises(LLMInvalidResponseError):
        call_structured(SYSTEM, USER, ExtractedIdea, caller=llm_client.generate_json)

    assert len(providers.groq.requests) == 2
    assert len(providers.gemini.calls) == 1, "Gemini failed on the first attempt, so the retry asks Groq only"
    retry_prompt = providers.groq.requests[1].body["messages"][1]["content"]
    assert retry_prompt.startswith(USER) and RETRY_INSTRUCTION.split("{")[0] in retry_prompt


def test_a_groq_reply_with_a_missing_field_is_repaired_like_a_gemini_one(
    monkeypatch: pytest.MonkeyPatch, groq_key: None
) -> None:
    missing = json.dumps({key: value for key, value in VALID_EXTRACTION.items() if key != "problem"})
    providers = use_providers(monkeypatch, [gemini_error(429)], [groq_reply(missing), groq_reply(LLM_REPLY_OK)])

    assert call_structured(SYSTEM, USER, ExtractedIdea, caller=llm_client.generate_json) == ExtractedIdea(**VALID_EXTRACTION)
    assert "problem" in providers.groq.requests[1].body["messages"][1]["content"]


# --- the run's time limit and the 10-second minimum ------------------------------------------


@pytest.mark.parametrize(("left", "groq_timeout"), [(45.0, 30.0), (20.0, 20.0), (10.0, 10.0)])
def test_groq_waits_at_most_the_time_left(
    monkeypatch: pytest.MonkeyPatch, groq_key: None, clock: Clock, left: float, groq_timeout: float
) -> None:
    providers = use_providers(monkeypatch, [gemini_error(429)], [groq_reply("{}")], clock)
    with time_limit(100):
        clock.advance(100 - left)
        assert llm_client.generate_json(SYSTEM, USER) == "{}"
    assert [request.timeout for request in providers.groq.requests] == [groq_timeout]


@pytest.mark.parametrize(
    ("error", "message"),
    [(gemini_error(503), llm_client.MSG_BUSY), (gemini_error(429, "RESOURCE_EXHAUSTED"), llm_client.MSG_RATE_LIMIT)],
    ids=["503", "429"],
)
def test_with_less_than_10_seconds_left_after_gemini_groq_is_not_tried(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    groq_key: None,
    clock: Clock,
    error: Exception,
    message: str,
) -> None:
    providers = use_providers(monkeypatch, [Slow(6.0, error)], [groq_reply("{}")], clock)
    with time_limit(100), caplog.at_level(logging.WARNING):
        clock.advance(85)
        with pytest.raises(LLMAPIError) as info:
            llm_client.generate_json(SYSTEM, USER)

    assert info.value.user_message == message, "the Gemini failure is reported"
    assert providers.groq.requests == []
    assert "no Groq fallback: 9.0s left, below the 10s minimum deadline" in caplog.text


def test_a_gemini_timeout_leaves_groq_only_the_time_left(
    monkeypatch: pytest.MonkeyPatch, groq_key: None, clock: Clock
) -> None:
    providers = use_providers(monkeypatch, [Slow(60.0, "{}")], [Slow(5.0, groq_reply('{"ok": 1}'))], clock)
    with time_limit(50):
        assert llm_client.generate_json(SYSTEM, USER) == '{"ok": 1}'

    assert providers.gemini.calls == [30.0]
    assert [request.timeout for request in providers.groq.requests] == [20.0]
    assert clock.now == 35.0


def test_the_fallback_never_runs_past_the_run_limit(monkeypatch: pytest.MonkeyPatch, groq_key: None, clock: Clock) -> None:
    providers = use_providers(monkeypatch, [Slow(60.0, "{}")], [Slow(60.0, groq_reply("{}"))], clock)
    with time_limit(40):
        with pytest.raises(LLMAPIError) as info:
            llm_client.generate_json(SYSTEM, USER)

    assert info.value.user_message == llm_client.MSG_TIMEOUT
    assert providers.gemini.calls == [30.0] and [request.timeout for request in providers.groq.requests] == [10.0]
    assert clock.now == 40.0, "Gemini's 30 s, then Groq's 10 s: the limit, and not beyond"
    assert time_left() is None


@pytest.mark.parametrize(("configured", "groq_timeout"), [("30", 30.0), ("45", 45.0), ("5", 10.0)])
def test_without_a_limit_groq_gets_the_llm_timeout_with_the_10_second_floor(
    monkeypatch: pytest.MonkeyPatch, groq_key: None, configured: str, groq_timeout: float
) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_S", configured)
    providers = use_providers(monkeypatch, [gemini_error(429)], [groq_reply("{}")])
    llm_client.generate_json(SYSTEM, USER)
    assert [request.timeout for request in providers.groq.requests] == [groq_timeout]


# --- the whole pipeline through the API ------------------------------------------------------


def answering(outcome: Any, clock: Clock | None = None, seconds: float = 0.0) -> Any:
    def fake(*args: Any, **kwargs: Any) -> Any:
        if clock is not None:
            clock.advance(seconds)
        return outcome

    return fake


def use_searches(monkeypatch: pytest.MonkeyPatch, clock: Clock | None = None, seconds: tuple = (0, 0, 0)) -> None:
    """The standard, market-size and competitor searches, faked as in the other pipeline tests."""
    monkeypatch.setattr(orchestrator, "run_web_search", answering(PIPELINE_SEARCH, clock, seconds[0]))
    monkeypatch.setattr(market_size, "run_queries", answering(NO_MARKET_SIZE_RESULTS, clock, seconds[1]))
    monkeypatch.setattr(competitor_agent, "run_queries", answering(COMPETITOR_TARGETED, clock, seconds[2]))


def post(client: TestClient, url: str = FULL_URL) -> PipelineResult:
    response = client.post(url, json=BODY)
    assert response.status_code == 200, response.text
    assert GROQ_KEY not in response.text and "test-llm-key" not in response.text
    return PipelineResult.model_validate(response.json())


def test_with_gemini_out_of_quota_the_full_pipeline_runs_on_groq(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, groq_key: None
) -> None:
    use_searches(monkeypatch)
    providers = use_providers(
        monkeypatch, [gemini_error(429, "RESOURCE_EXHAUSTED")], [groq_reply(reply) for reply in PIPELINE_REPLIES]
    )
    on_groq = post(client)
    use_providers(monkeypatch, list(PIPELINE_REPLIES))
    on_gemini = post(client)

    assert on_groq.status == "complete" and on_groq.errors == []
    assert on_groq.market is not None and on_groq.competitors is not None
    assert on_groq.model_dump(exclude={"timings", "usage"}) == on_gemini.model_dump(exclude={"timings", "usage"}), (
        "the same checked result, audit fields included, whichever provider answered"
    )
    assert len(providers.gemini.calls) == 4 and len(providers.groq.requests) == 4


def test_a_groq_failure_mid_run_keeps_the_finished_stages(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, groq_key: None
) -> None:
    use_searches(monkeypatch)
    use_providers(
        monkeypatch,
        [gemini_error(429, "RESOURCE_EXHAUSTED")],
        [groq_reply(LLM_REPLY_OK), groq_reply(market_reply()), groq_error(429, "rate_limit_exceeded"), groq_error(503)],
    )
    result = post(client)

    assert result.status == "partial"
    assert result.idea is not None and result.search == PIPELINE_SEARCH and result.market is not None
    assert result.competitors is None and result.competitor_search is None
    assert [(error.stage, error.message) for error in result.errors] == [("competitor_analysis", llm_client.MSG_BUSY)]


def test_a_milestone_1_request_falls_back_too(client: TestClient, monkeypatch: pytest.MonkeyPatch, groq_key: None) -> None:
    use_searches(monkeypatch)
    providers = use_providers(monkeypatch, [gemini_error(429, "RESOURCE_EXHAUSTED")], [groq_reply(LLM_REPLY_OK)])
    body = client.post(URL, json=BODY).json()

    assert body["status"] == "complete" and body["idea"] == VALID_EXTRACTION
    assert body["market"] is None and set(body["timings"]) == {"extraction", "search", "total"}
    assert len(providers.groq.requests) == 1


def test_without_a_groq_key_a_gemini_quota_error_fails_the_run_as_before(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_searches(monkeypatch)
    providers = use_providers(monkeypatch, [gemini_error(429, "RESOURCE_EXHAUSTED")])
    result = post(client)

    assert result.status == "failed"
    assert [(error.stage, error.message) for error in result.errors] == [("extraction", llm_client.MSG_RATE_LIMIT)]
    assert providers.groq.requests == []


def test_under_the_run_limit_the_fallback_stops_at_the_limit_and_keeps_what_finished(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, groq_key: None, clock: Clock
) -> None:
    """Every Gemini call times out and Groq answers in 2 s. Phase C starts with 23 s left: Gemini
    gets those 23 s, times out at the limit, and Groq is not tried with nothing left."""
    use_searches(monkeypatch, clock, seconds=(15, 8, 20))
    candidates, _ = competitor_replies()
    providers = use_providers(
        monkeypatch,
        [Slow(60.0, "{}")],
        [Slow(2.0, groq_reply(LLM_REPLY_OK)), Slow(2.0, groq_reply(market_reply())), Slow(2.0, groq_reply(candidates))],
        clock,
    )
    result = post(client)

    assert clock.now == orchestrator.analysis_time_limit_s() == 162.0, "the reply comes at the limit, not after"
    assert providers.gemini.calls == [30.0, 30.0, 30.0, 23.0]
    assert [request.timeout for request in providers.groq.requests] == [30.0, 30.0, 30.0]
    assert result.status == "partial" and result.market is not None and result.competitors is None
    assert [(error.stage, error.message) for error in result.errors] == [("competitor_analysis", llm_client.MSG_TIMEOUT)]


# --- scripts/check_groq.py -------------------------------------------------------------------


def test_the_check_script_stops_without_a_key(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    providers = use_providers(monkeypatch, ["{}"])
    assert check_groq.main() == 1

    out = capsys.readouterr().out
    assert "GROQ_API_KEY set: no" in out and "the Groq fallback is off" in out
    assert providers.groq.requests == []


EMPTY_ANALYSIS = json.dumps(
    {
        "competitors": [],
        "comparison": {"features": [], "rows": []},
        "market_gaps": [],
        "differentiation_opportunities": [],
        "data_quality": {"evidence_level": "insufficient", "notes": []},
    }
)


def test_the_check_script_tries_the_strict_competitor_schema_and_reports_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, groq_key: None
) -> None:
    from models.schemas import CompetitorAnalysisDraft

    providers = use_providers(monkeypatch, ["{}"], [groq_reply(EMPTY_ANALYSIS)])
    assert check_groq.main() == 0

    out = capsys.readouterr().out
    assert "GROQ_API_KEY set: yes" in out and f"Groq model:       {groq_client.MODEL}" in out
    assert "Result: SUCCESS. Groq accepted the strict competitor-analysis schema" in out
    assert GROQ_KEY not in out
    (request,) = providers.groq.requests
    assert providers.gemini.calls == [] and request.timeout == 30.0
    assert request.body["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "CompetitorAnalysisDraft",
            "strict": True,
            "schema": groq_client.strict_schema(CompetitorAnalysisDraft),
        },
    }


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (groq_error(401, "invalid_api_key"), "Result: FAILED (auth, HTTP 401, code invalid_api_key)."),
        (groq_error(429, "rate_limit_exceeded"), "Result: FAILED (rate_limit, HTTP 429, code rate_limit_exceeded)."),
        (groq_error(400, "json_validate_failed"), "Result: FAILED (invalid_json, HTTP 400, code json_validate_failed)."),
        (groq_error(400), "Result: FAILED (invalid_request, HTTP 400)."),
        (groq_reply("not json"), "but not with a valid competitor analysis."),
        (groq_reply('{"ok": true}'), "but not with a valid competitor analysis."),
    ],
    ids=["auth", "rate_limit", "invalid_json", "schema_rejected", "not_json", "wrong_shape"],
)
def test_the_check_script_reports_a_failure_plainly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, groq_key: None, outcome: Any, expected: str
) -> None:
    use_providers(monkeypatch, ["{}"], [outcome])
    assert check_groq.main() == 1

    out = capsys.readouterr().out
    assert expected in out and GROQ_KEY not in out and "Traceback" not in out

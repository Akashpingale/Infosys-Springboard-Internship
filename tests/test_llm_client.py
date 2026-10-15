import gc
import weakref
from typing import Any

import httpx
import pytest
from google.genai import errors as genai_errors

from utils import llm_client
from utils.errors import LLMAPIError, LLMConfigError


class FakeModels:
    """Yields `outcomes` in order (the last one repeats). Exceptions are raised."""

    def __init__(self, *outcomes: Any, models: Any = ()) -> None:
        self._outcomes = outcomes or ("{}",)
        self._models = models
        self.calls: list[dict] = []
        self.list_calls = 0

    def _next(self, index: int) -> Any:
        outcome = self._outcomes[min(index, len(self._outcomes) - 1)]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        text = self._next(len(self.calls) - 1)
        return type("FakeResponse", (), {"text": text})()

    def list(self) -> Any:
        self.list_calls += 1
        if isinstance(self._models, BaseException):
            raise self._models
        return self._models


class FakeClientRecord:
    def __init__(self, models: FakeModels) -> None:
        self.models = models
        self.client_kwargs: dict = {}
        self.clients_created = 0
        self.closes = 0


def fake_model(name: str | None, *actions: str) -> Any:
    return type("FakeModel", (), {"name": name, "supported_actions": list(actions)})()


def install_fake_client(
    monkeypatch: pytest.MonkeyPatch, *outcomes: Any, models: Any = ()
) -> FakeClientRecord:
    """Replace genai.Client so no request leaves the machine."""
    record = FakeClientRecord(FakeModels(*outcomes, models=models))

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            record.client_kwargs = kwargs
            record.clients_created += 1
            self.models = record.models

        def close(self) -> None:
            record.closes += 1

    monkeypatch.setattr(llm_client.genai, "Client", FakeClient)
    return record


def api_error(code: int, message: str = "error", status: str = "ERROR") -> genai_errors.APIError:
    body = {"error": {"code": code, "message": message, "status": status}}
    cls = genai_errors.ServerError if code >= 500 else genai_errors.ClientError
    return cls(code, body)


@pytest.fixture
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the retry logic but remove the waiting."""
    monkeypatch.setattr(llm_client, "RETRY_BACKOFF_S", (0.0, 0.0))


# --- happy path and settings -------------------------------------------------


def test_returns_text_and_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_S", "12")
    record = install_fake_client(monkeypatch, '{"ok": true}')
    assert llm_client.generate_json("system", "user") == '{"ok": true}'

    call = record.models.calls[0]
    assert call["model"] == "test-model"
    assert call["contents"] == "user"
    assert call["config"].system_instruction == "system"
    assert call["config"].temperature == llm_client.TEMPERATURE
    assert call["config"].response_mime_type == "application/json"
    assert record.client_kwargs["api_key"] == "test-llm-key"
    assert record.client_kwargs["http_options"].timeout == 12000


def test_none_text_becomes_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_client(monkeypatch, None)
    assert llm_client.generate_json("system", "user") == ""


@pytest.mark.parametrize("missing", ["LLM_API_KEY", "LLM_MODEL"])
def test_missing_config_raises_config_error(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    record = install_fake_client(monkeypatch, "{}")
    monkeypatch.delenv(missing)
    with pytest.raises(LLMConfigError, match="not configured"):
        llm_client.generate_json("system", "user")
    assert record.clients_created == 0 and record.models.calls == []


# --- error translation -------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (api_error(401, "Request had invalid authentication"), llm_client.MSG_KEY_REJECTED),
        (api_error(403, "Permission denied"), llm_client.MSG_KEY_REJECTED),
        (api_error(400, "API key not valid.", "INVALID_ARGUMENT"), llm_client.MSG_KEY_REJECTED),
        (api_error(400, "API_KEY_INVALID", "INVALID_ARGUMENT"), llm_client.MSG_KEY_REJECTED),
        (api_error(429, "Resource exhausted"), llm_client.MSG_RATE_LIMIT),
        (httpx.ReadTimeout("timed out"), llm_client.MSG_TIMEOUT),
        (httpx.ConnectTimeout("timed out"), llm_client.MSG_TIMEOUT),
        (api_error(500, "Internal error"), llm_client.MSG_BUSY),
        (api_error(502, "Bad gateway"), llm_client.MSG_BUSY),
        (api_error(503, "High demand"), llm_client.MSG_BUSY),
        (api_error(504, "Deadline exceeded"), llm_client.MSG_BUSY),
        (api_error(400, "Invalid argument"), llm_client.MSG_GENERIC),
        (httpx.ConnectError("no route"), llm_client.MSG_GENERIC),
        (RuntimeError("something odd"), llm_client.MSG_GENERIC),
    ],
)
def test_provider_errors_become_readable_api_errors(
    monkeypatch: pytest.MonkeyPatch, fast_retries: None, error: BaseException, expected: str
) -> None:
    install_fake_client(monkeypatch, error)
    with pytest.raises(LLMAPIError) as info:
        llm_client.generate_json("system", "user")
    assert info.value.user_message == expected
    assert "test-llm-key" not in info.value.user_message


def test_model_not_found_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_client(monkeypatch, api_error(404, "models/x is not found"))
    with pytest.raises(LLMConfigError) as info:
        llm_client.generate_json("system", "user")
    assert info.value.user_message == llm_client.MSG_MODEL_NOT_FOUND
    assert info.value.status_code == 503


def test_error_messages_are_distinct() -> None:
    messages = [
        llm_client.MSG_MODEL_NOT_FOUND,
        llm_client.MSG_KEY_REJECTED,
        llm_client.MSG_RATE_LIMIT,
        llm_client.MSG_TIMEOUT,
        llm_client.MSG_BUSY,
        llm_client.MSG_GENERIC,
    ]
    assert len(set(messages)) == len(messages)


def test_failure_is_logged_with_class_and_status_but_no_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    install_fake_client(monkeypatch, api_error(429, "Resource exhausted", "RESOURCE_EXHAUSTED"))
    with caplog.at_level("WARNING", logger="utils.llm_client"):
        with pytest.raises(LLMAPIError):
            llm_client.generate_json("system", "user")
    logged = caplog.text
    assert "ClientError" in logged and "429" in logged and "RESOURCE_EXHAUSTED" in logged
    assert "test-llm-key" not in logged


# --- bounded retry for transient failures ------------------------------------


def test_transient_failure_then_success(monkeypatch: pytest.MonkeyPatch, fast_retries: None) -> None:
    record = install_fake_client(monkeypatch, api_error(503, "High demand"), '{"ok": 1}')
    assert llm_client.generate_json("system", "user") == '{"ok": 1}'
    assert len(record.models.calls) == 2


def test_transient_failure_is_retried_a_bounded_number_of_times(
    monkeypatch: pytest.MonkeyPatch, fast_retries: None
) -> None:
    record = install_fake_client(monkeypatch, api_error(503, "High demand"))
    with pytest.raises(LLMAPIError, match="busy right now"):
        llm_client.generate_json("system", "user")
    assert len(record.models.calls) == len(llm_client.RETRY_BACKOFF_S) + 1 == 3


@pytest.mark.parametrize(
    "error",
    [
        api_error(401, "bad key"),
        api_error(404, "no such model"),
        api_error(429, "quota"),
        api_error(400, "Invalid argument"),
        httpx.ReadTimeout("timed out"),
    ],
)
def test_permanent_errors_are_not_retried(
    monkeypatch: pytest.MonkeyPatch, fast_retries: None, error: BaseException
) -> None:
    record = install_fake_client(monkeypatch, error)
    with pytest.raises((LLMAPIError, LLMConfigError)):
        llm_client.generate_json("system", "user")
    assert len(record.models.calls) == 1


def test_retry_waits_use_the_configured_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr(llm_client, "RETRY_BACKOFF_S", (0.25, 0.75))
    monkeypatch.setattr(llm_client.time, "sleep", waits.append)
    install_fake_client(monkeypatch, api_error(503, "High demand"))
    with pytest.raises(LLMAPIError):
        llm_client.generate_json("system", "user")
    assert waits == [0.25, 0.75]


def test_default_backoff_is_small_bounded_and_increasing() -> None:
    backoff = llm_client.RETRY_BACKOFF_S
    assert len(backoff) == 2
    assert list(backoff) == sorted(backoff)
    assert sum(backoff) <= 5


# --- client lifecycle --------------------------------------------------------


class WeaklyOwnedModels:
    """Mirrors the real SDK: client.models does not strongly reference the client, so a
    client left unreferenced is collected mid-call and its connection is closed."""

    def __init__(self, owner: Any) -> None:
        self._owner_ref = weakref.ref(owner)

    def _check_client_alive(self) -> None:
        gc.collect()
        if self._owner_ref() is None:
            raise RuntimeError("Cannot send a request, as the client has been closed.")

    def generate_content(self, **kwargs: Any) -> Any:
        self._check_client_alive()
        return type("FakeResponse", (), {"text": "{}"})()

    def list(self) -> Any:
        self._check_client_alive()
        return [fake_model("models/gemini-test-flash", "generateContent")]


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (lambda: llm_client.generate_json("system", "user"), "{}"),
        (lambda: llm_client.generate_text("Reply with the word OK"), "{}"),
        (lambda: llm_client.list_text_models(), ["gemini-test-flash"]),
    ],
)
def test_client_stays_alive_for_the_whole_call(
    monkeypatch: pytest.MonkeyPatch, call: Any, expected: Any
) -> None:
    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            self.models = WeaklyOwnedModels(self)

        def close(self) -> None:
            pass

    monkeypatch.setattr(llm_client.genai, "Client", FakeClient)
    assert call() == expected


def test_client_is_closed_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    record = install_fake_client(monkeypatch, "{}")
    llm_client.generate_json("system", "user")
    assert record.clients_created == 1 and record.closes == 1


def test_client_is_closed_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    record = install_fake_client(monkeypatch, api_error(401, "bad key"))
    with pytest.raises(LLMAPIError):
        llm_client.generate_json("system", "user")
    assert record.closes == 1


def test_every_retry_attempt_closes_its_client(
    monkeypatch: pytest.MonkeyPatch, fast_retries: None
) -> None:
    record = install_fake_client(monkeypatch, api_error(503, "High demand"))
    with pytest.raises(LLMAPIError):
        llm_client.generate_json("system", "user")
    assert record.clients_created == 3 and record.closes == 3


def test_a_client_without_close_is_tolerated(monkeypatch: pytest.MonkeyPatch) -> None:
    class ClientWithoutClose:
        def __init__(self, **kwargs: Any) -> None:
            self.models = FakeModels("{}")

    monkeypatch.setattr(llm_client.genai, "Client", ClientWithoutClose)
    assert llm_client.generate_json("system", "user") == "{}"


def test_a_failing_close_does_not_break_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    class ClientWithBadClose:
        def __init__(self, **kwargs: Any) -> None:
            self.models = FakeModels("{}")

        def close(self) -> None:
            raise RuntimeError("close blew up")

    monkeypatch.setattr(llm_client.genai, "Client", ClientWithBadClose)
    assert llm_client.generate_json("system", "user") == "{}"


# --- text call and model listing ---------------------------------------------


def test_generate_text_sends_plain_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    record = install_fake_client(monkeypatch, "OK")
    assert llm_client.generate_text("Reply with the word OK") == "OK"
    call = record.models.calls[0]
    assert call["contents"] == "Reply with the word OK"
    assert call["config"].response_mime_type is None


def test_generate_text_translates_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_client(monkeypatch, api_error(401, "bad key"))
    with pytest.raises(LLMAPIError, match="rejected the API key"):
        llm_client.generate_text("hi")


def test_list_text_models_filters_and_strips_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_client(
        monkeypatch,
        "{}",
        models=[
            fake_model("models/gemini-test-flash", "generateContent", "countTokens"),
            fake_model("models/embedding-test", "embedContent"),
            fake_model("models/gemini-test-pro", "generateContent"),
            fake_model(None, "generateContent"),
        ],
    )
    assert llm_client.list_text_models() == ["gemini-test-flash", "gemini-test-pro"]


def test_list_text_models_reports_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_client(monkeypatch, "{}", models=api_error(403, "Permission denied"))
    with pytest.raises(LLMAPIError, match="rejected the API key"):
        llm_client.list_text_models()


def test_model_exists_checks_the_listing_only(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_client(
        monkeypatch, "{}", models=[fake_model("models/gemini-test-flash", "generateContent")]
    )
    assert llm_client.model_exists("gemini-test-flash") is True
    assert llm_client.model_exists("models/gemini-test-flash") is True
    assert llm_client.model_exists("gemini-missing") is False


def test_short_model_name() -> None:
    assert llm_client.short_model_name("models/gemini-x") == "gemini-x"
    assert llm_client.short_model_name("gemini-x") == "gemini-x"

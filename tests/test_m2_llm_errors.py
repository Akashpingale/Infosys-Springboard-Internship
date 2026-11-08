"""The LLM client after the localhost run of 2026-10-27 (utils/llm_client.py).

That run's HTTP 400 INVALID_ARGUMENT could not be diagnosed, because only the error class and the
HTTP status were logged. The provider's own message is now logged too. These tests pin what that
log line may carry: one line, no key, token or authorization value, nothing repeated from the
prompt, nothing from the response body or headers, and at most PROVIDER_MESSAGE_MAX characters.
The messages users see are unchanged. They also pin the 10-second minimum deadline when no run
time limit is active. The provider is faked, so nothing touches the network.
"""

import logging
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google.genai import errors as genai_errors

from utils import llm_client
from utils.errors import LLMAPIError, LLMConfigError

KEY = "test-llm-key"  # the fake keys tests/conftest.py sets
SEARCH_KEY = "test-tavily-key"
# Fake values in the shape of real ones, joined at run time so that no key-shaped literal is
# stored in the repository for a secret scanner to flag.
GOOGLE_KEY = "AIza" + "SyFAKE0FAKE1FAKE2FAKE3FAKE4FAKE5FAK"
NEW_KEY = "AQ." + "FAKE0FAKE1FAKE2FAKE3FAKE4FAKE5"
TOKEN = "ya29" + ".FAKE-access-token-for-tests"
DEADLINE = "Manually set deadline 8s is too short. Minimum allowed deadline is 10s."
PROMPT = (
    "Extract the startup idea from the founder's submission below.\n<submission>\n"
    "Idea description: A mobile app that detects crop diseases from a photo of a leaf "
    "and suggests a treatment for small farmers in Maharashtra.\n</submission>"
)


def api_error(code: int, message: Any, status: str = "INVALID_ARGUMENT", **extra: Any) -> genai_errors.APIError:
    body = {"error": {"code": code, "message": message, "status": status, **extra}}
    cls = genai_errors.ServerError if code >= 500 else genai_errors.ClientError
    return cls(code, body)


def use_client(monkeypatch: pytest.MonkeyPatch, outcome: Any) -> list[int]:
    """genai.Client whose calls return `outcome`, or raise it. Returns the timeouts (ms) it got."""
    timeouts: list[int] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            timeouts.append(kwargs["http_options"].timeout)
            self.models = self

        def generate_content(self, **kwargs: Any) -> Any:
            if isinstance(outcome, BaseException):
                raise outcome
            return SimpleNamespace(text=outcome)

        def close(self) -> None:
            pass

    monkeypatch.setattr(llm_client.genai, "Client", FakeClient)
    monkeypatch.setattr(llm_client, "RETRY_BACKOFF_S", (0.0, 0.0))
    return timeouts


def failure_line(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    error: BaseException,
    prompt: str = "user",
) -> tuple[str, Exception]:
    """The one 'LLM call failed' log line a failing call writes, and the app error it raised."""
    use_client(monkeypatch, error)
    with caplog.at_level(logging.WARNING, logger="utils.llm_client"):
        with pytest.raises((LLMAPIError, LLMConfigError)) as info:
            llm_client.generate_json("system", prompt)
    lines = [
        record.getMessage()
        for record in caplog.records
        if record.name == "utils.llm_client" and record.getMessage().startswith("LLM call failed")
    ]
    assert len(lines) == 1, lines
    return lines[0], info.value


def message_part(line: str) -> str:
    return line.split("): ", 1)[1]


# --- what is logged ----------------------------------------------------------------------------


def test_the_provider_message_is_logged_so_a_400_can_be_diagnosed(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    line, error = failure_line(caplog, monkeypatch, api_error(400, DEADLINE))

    assert line == f"LLM call failed: ClientError (HTTP 400, INVALID_ARGUMENT): {DEADLINE}"
    assert error.user_message == llm_client.MSG_GENERIC, "what the user sees is unchanged"


@pytest.mark.parametrize(
    ("message", "secret"),
    [
        (f"API key {KEY} is not valid for this project.", KEY),
        (f"The web search key {SEARCH_KEY} reached the AI service.", SEARCH_KEY),
        (f"Invalid credential {GOOGLE_KEY} for this project.", GOOGLE_KEY),
        (f"Credential {NEW_KEY} was denied.", NEW_KEY),
        (f"Header x-goog-api-key: {GOOGLE_KEY} was rejected.", GOOGLE_KEY),
        (f"Authorization: Bearer {TOKEN} has expired.", TOKEN),
        (f'Got {{"access_token": "{TOKEN}"}} instead.', TOKEN),
        (f"POST https://generativelanguage.googleapis.com/v1beta/models?key={GOOGLE_KEY}&alt=json failed.", GOOGLE_KEY),
    ],
)
def test_keys_tokens_and_authorization_values_are_redacted(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, message: str, secret: str
) -> None:
    line, _ = failure_line(caplog, monkeypatch, api_error(400, message))

    assert secret not in caplog.text
    assert llm_client.REDACTED in message_part(line)
    for kept in ("was", "for this project", "expired", "instead", "failed", "reached"):
        if kept in message:
            assert kept in line, "the rest of the message is kept for diagnosis"


def test_the_message_is_one_line_and_cut_to_200_characters(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    message = "First line\nSecond line\r\nFAKE LOG LINE\x1b[31m red" + " word" * 300 + " TAIL-MARKER"
    line, _ = failure_line(caplog, monkeypatch, api_error(400, message))
    logged = message_part(line)

    assert "\n" not in line and "\r" not in line and "\x1b" not in line, "it cannot forge another log line"
    assert logged.startswith("First line Second line FAKE LOG LINE")
    assert len(logged) <= llm_client.PROVIDER_MESSAGE_MAX and logged.endswith("...")
    assert "TAIL-MARKER" not in caplog.text


def test_a_message_that_repeats_the_prompt_is_withheld(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    echo = "Invalid value at contents[0]: A mobile app that detects crop diseases from a photo"
    line, _ = failure_line(caplog, monkeypatch, api_error(400, echo), prompt=PROMPT)

    assert message_part(line) == llm_client.WITHHELD
    assert "crop diseases" not in caplog.text


def test_a_short_phrase_shared_with_the_prompt_is_not_withheld(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    message = "Request contains an invalid argument for the submission below."
    line, _ = failure_line(caplog, monkeypatch, api_error(400, message), prompt=PROMPT)

    assert message_part(line) == message, "fewer than PROMPT_ECHO_CHARS shared characters"


def test_the_response_body_and_headers_are_never_logged(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = {
        "error": {
            "code": 400,
            "message": "Request contains an invalid argument.",
            "status": "INVALID_ARGUMENT",
            "details": [{"@type": "type.googleapis.com/google.rpc.DebugInfo", "detail": "BODY-ONLY-DETAIL"}],
        }
    }
    response = SimpleNamespace(headers={"x-goog-api-key": GOOGLE_KEY}, text="BODY-ONLY-TEXT")
    line, _ = failure_line(caplog, monkeypatch, genai_errors.ClientError(400, body, response))

    assert message_part(line) == "Request contains an invalid argument."
    for hidden in ("BODY-ONLY-DETAIL", "BODY-ONLY-TEXT", GOOGLE_KEY, "DebugInfo"):
        assert hidden not in caplog.text


@pytest.mark.parametrize(
    "error",
    [httpx.ReadTimeout(f"timed out, key={GOOGLE_KEY}"), RuntimeError(f"odd state with {KEY}")],
    ids=["read_timeout", "unexpected"],
)
def test_an_error_without_a_provider_message_logs_only_its_class(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    line, _ = failure_line(caplog, monkeypatch, error)

    assert line == f"LLM call failed: {type(error).__name__} (HTTP None, None)"
    assert GOOGLE_KEY not in caplog.text and KEY not in caplog.text


@pytest.mark.parametrize("message", [None, "", "   ", {"nested": "not text"}], ids=["none", "empty", "blank", "dict"])
def test_a_missing_or_odd_message_adds_nothing(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, message: Any
) -> None:
    line, _ = failure_line(caplog, monkeypatch, api_error(400, message))
    assert line == "LLM call failed: ClientError (HTTP 400, INVALID_ARGUMENT)"


def test_the_prompt_never_reaches_the_log_on_any_path(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transient failure, its retries and the final failure: the prompt is in no log line."""
    use_client(monkeypatch, api_error(503, "The model is overloaded.", "UNAVAILABLE"))
    with caplog.at_level(logging.DEBUG, logger="utils.llm_client"):
        with pytest.raises(LLMAPIError):
            llm_client.generate_json("system prompt text", PROMPT)

    assert "retry 1 of 2" in caplog.text and "The model is overloaded." in caplog.text
    assert "crop diseases" not in caplog.text and "system prompt text" not in caplog.text


# --- the minimum deadline without a run time limit --------------------------------------------


@pytest.mark.parametrize(
    ("configured", "sent_ms"),
    [("5", 10000), ("9.99", 10000), ("0.0004", 10000), ("10", 10000), ("12", 12000), (None, 30000)],
)
def test_a_configured_llm_timeout_under_10_seconds_is_raised_to_the_minimum(
    monkeypatch: pytest.MonkeyPatch, configured: str | None, sent_ms: int
) -> None:
    if configured is not None:
        monkeypatch.setenv("LLM_TIMEOUT_S", configured)
    timeouts = use_client(monkeypatch, '{"ok": true}')

    assert llm_client.generate_json("system", "user") == '{"ok": true}'
    assert timeouts == [sent_ms]
    assert llm_client.MIN_DEADLINE_S == 10.0

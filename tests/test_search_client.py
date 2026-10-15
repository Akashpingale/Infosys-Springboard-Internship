import pytest
import requests

from tests.fakes import (
    TAVILY_CONNECTION_ERROR,
    TAVILY_OK_RESPONSE,
    TAVILY_TIMEOUT,
    FakeHTTPResponse,
    make_sequence,
    tavily_empty,
    tavily_not_json,
    tavily_status,
)
from utils import search_client
from utils.errors import SearchAPIError, SearchConfigError, SearchError


def use_fake_post(monkeypatch: pytest.MonkeyPatch, *outcomes: object):
    fake = make_sequence(*outcomes)
    monkeypatch.setattr(search_client.requests, "post", fake)
    return fake


def test_returns_parsed_body_and_sends_expected_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_TIMEOUT_S", "15")
    fake = use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))

    assert search_client.search("crop disease market size") == TAVILY_OK_RESPONSE

    args, kwargs = fake.calls[0]
    assert args[0] == search_client.API_URL
    assert kwargs["json"] == {
        "query": "crop disease market size",
        "search_depth": "basic",
        "max_results": 3,
        "include_answer": True,
    }
    assert kwargs["timeout"] == 15


def test_request_options_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))
    search_client.search("q", max_results=5, depth="advanced", include_answer=False)
    body = fake.calls[0][1]["json"]
    assert body["max_results"] == 5 and body["search_depth"] == "advanced"
    assert body["include_answer"] is False


def test_key_is_sent_in_the_header_not_the_url(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))
    search_client.search("q")
    args, kwargs = fake.calls[0]
    assert kwargs["headers"]["Authorization"] == "Bearer test-tavily-key"
    assert "test-tavily-key" not in args[0]


def test_key_is_read_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))
    monkeypatch.setenv("TAVILY_API_KEY", "second-key")
    search_client.search("q")
    assert fake.calls[0][1]["headers"]["Authorization"] == "Bearer second-key"


def test_missing_key_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))
    monkeypatch.delenv("TAVILY_API_KEY")
    with pytest.raises(SearchConfigError) as info:
        search_client.search("q")
    assert "TAVILY_API_KEY is not set" in info.value.user_message
    assert info.value.status_code == 503
    assert fake.calls == []


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (tavily_status(401), search_client.MSG_KEY_REJECTED),
        (tavily_status(403), search_client.MSG_KEY_REJECTED),
        (tavily_status(429), search_client.MSG_RATE_LIMIT),
        (tavily_status(500), search_client.MSG_BUSY),
        (tavily_status(503), search_client.MSG_BUSY),
        (tavily_status(400), search_client.MSG_REJECTED_QUERY),
        (tavily_not_json(), search_client.MSG_BAD_REPLY),
        (FakeHTTPResponse(200, ["not", "an", "object"]), search_client.MSG_BAD_REPLY),
        (TAVILY_TIMEOUT, search_client.MSG_TIMEOUT),
        (TAVILY_CONNECTION_ERROR, search_client.MSG_UNREACHABLE),
        (requests.TooManyRedirects("loop"), search_client.MSG_UNREACHABLE),
    ],
)
def test_failures_give_readable_messages(
    monkeypatch: pytest.MonkeyPatch, outcome: object, expected: str
) -> None:
    use_fake_post(monkeypatch, outcome)
    with pytest.raises(SearchAPIError) as info:
        search_client.search("q")
    assert info.value.user_message == expected
    assert "test-tavily-key" not in info.value.user_message


def test_error_messages_are_distinct() -> None:
    messages = [
        search_client.MSG_KEY_REJECTED,
        search_client.MSG_RATE_LIMIT,
        search_client.MSG_TIMEOUT,
        search_client.MSG_UNREACHABLE,
        search_client.MSG_BAD_REPLY,
        search_client.MSG_BUSY,
    ]
    assert len(set(messages)) == len(messages)


def test_empty_results_are_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, tavily_empty())
    assert search_client.search("q")["results"] == []


def test_search_errors_share_the_week1_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, tavily_status(429))
    with pytest.raises(SearchError):
        search_client.search("q")


def test_failure_logs_status_but_never_the_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    use_fake_post(monkeypatch, tavily_status(429))
    with caplog.at_level("WARNING", logger="utils.search_client"):
        with pytest.raises(SearchAPIError):
            search_client.search("q")
    assert "429" in caplog.text and "test-tavily-key" not in caplog.text

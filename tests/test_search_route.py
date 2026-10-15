import pytest
from fastapi.testclient import TestClient

from models.schemas import SearchBundle
from tests.fakes import (
    TAVILY_OK_RESPONSE,
    TAVILY_TIMEOUT,
    VALID_EXTRACTION,
    FakeHTTPResponse,
    make_sequence,
    tavily_empty,
    tavily_status,
)
from utils import search_client

URL = "/api/search"


def use_fake_post(monkeypatch: pytest.MonkeyPatch, *outcomes: object):
    fake = make_sequence(*outcomes)
    monkeypatch.setattr(search_client.requests, "post", fake)
    return fake


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status
    body = response.json()
    assert body["error"]["code"] == code
    assert "Traceback" not in response.text and "test-tavily-key" not in response.text
    return body["error"]


def test_search_returns_a_bundle(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())
    response = client.post(URL, json=VALID_EXTRACTION)

    assert response.status_code == 200
    bundle = SearchBundle.model_validate(response.json())
    assert len(bundle.sections) == 4
    assert bundle.total_results == 2
    assert bundle.sections[0].results[0].url.startswith("https://")


def test_partial_failure_still_returns_200(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fake_post(
        monkeypatch,
        tavily_status(429),
        FakeHTTPResponse(200, TAVILY_OK_RESPONSE),
        tavily_empty(),
    )
    body = client.post(URL, json=VALID_EXTRACTION).json()
    assert body["queries_failed"] == 1
    assert body["sections"][0]["error"] == search_client.MSG_RATE_LIMIT


def test_all_queries_failing_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fake_post(monkeypatch, TAVILY_TIMEOUT)
    error = assert_error(client.post(URL, json=VALID_EXTRACTION), 502, "search_api_error")
    assert error["message"] == "Web search could not be completed. Please try again."


def test_missing_key_returns_502_after_every_query_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))
    monkeypatch.delenv("TAVILY_API_KEY")
    assert_error(client.post(URL, json=VALID_EXTRACTION), 502, "search_api_error")
    assert fake.calls == []


@pytest.mark.parametrize(
    "bad_idea",
    [
        {**VALID_EXTRACTION, "problem": "   "},
        {**VALID_EXTRACTION, "key_features": []},
        {**VALID_EXTRACTION, "market_size": "USD 5 billion"},
        {k: v for k, v in VALID_EXTRACTION.items() if k != "industry"},
    ],
)
def test_invalid_idea_returns_422_without_searching(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, bad_idea: dict
) -> None:
    fake = use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))
    assert_error(client.post(URL, json=bad_idea), 422, "invalid_input")
    assert fake.calls == []


def test_unexpected_crash_returns_generic_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fake_post(monkeypatch, RuntimeError("provider internals"))
    error = assert_error(client.post(URL, json=VALID_EXTRACTION), 500, "internal_error")
    assert error["message"] == "Something went wrong. Please try again."


def test_route_listed_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert URL in paths and "/api/ideas/extract" in paths

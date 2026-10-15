"""End-to-end route tests: the real orchestrator and agents, with the LLM and Tavily mocked."""

import pytest
from fastapi.testclient import TestClient

import orchestrator
from agents import extraction_agent
from models.schemas import PipelineResult
from tests.fakes import (
    LLM_REPLY_NOT_JSON,
    LLM_REPLY_OK,
    TAVILY_OK_RESPONSE,
    TAVILY_TIMEOUT,
    VALID_EXTRACTION,
    FakeHTTPResponse,
    make_sequence,
    tavily_empty,
    tavily_status,
)
from utils import search_client

URL = "/api/validate"
BODY = {
    "idea_description": "An AI app that detects crop diseases from phone photos for small farmers.",
    "industry": "Agriculture / AgriTech",
    "target_customers": "Small farmers in India",
    "relevant_details": "Pilot in Maharashtra",
}


def fake_llm(monkeypatch: pytest.MonkeyPatch, *replies: object):
    fake = make_sequence(*replies)
    monkeypatch.setattr(extraction_agent, "generate_json", fake)
    return fake


def fake_tavily(monkeypatch: pytest.MonkeyPatch, *outcomes: object):
    fake = make_sequence(*outcomes)
    monkeypatch.setattr(search_client.requests, "post", fake)
    return fake


def post(client: TestClient, body: dict | None = None):
    return client.post(URL, json=BODY if body is None else body)


def assert_no_leaks(response) -> None:
    assert "Traceback" not in response.text
    assert "test-llm-key" not in response.text and "test-tavily-key" not in response.text


def test_complete_pipeline_returns_idea_and_search(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())

    response = post(client)
    assert response.status_code == 200
    assert_no_leaks(response)

    result = PipelineResult.model_validate(response.json())
    assert result.status == "complete"
    assert result.idea is not None and result.idea.model_dump() == VALID_EXTRACTION
    assert result.search is not None and len(result.search.sections) == 4
    assert result.search.total_results == 2
    assert result.errors == []
    assert set(result.timings) == {"extraction", "search", "total"}


def test_partly_failed_search_returns_partial(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(
        monkeypatch, tavily_status(429), FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty()
    )

    result = PipelineResult.model_validate(post(client).json())
    assert result.status == "partial"
    assert result.idea is not None
    assert result.search is not None and result.search.queries_failed == 1
    assert result.warnings and "web searches failed" in result.warnings[0]
    assert result.errors == []


def test_total_search_failure_returns_partial_with_the_idea(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(monkeypatch, TAVILY_TIMEOUT)

    response = post(client)
    assert response.status_code == 200
    result = PipelineResult.model_validate(response.json())
    assert result.status == "partial"
    assert result.idea is not None and result.search is None
    assert result.warnings == [orchestrator.WARNING_SEARCH_UNAVAILABLE]
    assert result.errors[0].stage == "search"


def test_missing_llm_key_returns_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LLM_API_KEY")
    fake_search = fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))

    response = post(client)
    assert response.status_code == 200
    assert_no_leaks(response)

    result = PipelineResult.model_validate(response.json())
    assert result.status == "failed"
    assert result.idea is None and result.search is None
    assert result.errors[0].stage == "extraction"
    assert result.errors[0].message == "The AI service is not configured."
    assert fake_search.calls == []


def test_invalid_llm_reply_returns_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_NOT_JSON)
    fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))

    result = PipelineResult.model_validate(post(client).json())
    assert result.status == "failed"
    assert result.errors[0].code == "llm_invalid_response"


def test_missing_search_key_returns_partial(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    monkeypatch.delenv("TAVILY_API_KEY")

    result = PipelineResult.model_validate(post(client).json())
    assert result.status == "partial"
    assert result.idea is not None
    assert result.errors[0].stage == "search"


@pytest.mark.parametrize(
    "bad_body",
    [
        {**BODY, "idea_description": "   "},
        {**BODY, "idea_description": "too short"},
        {**BODY, "target_customers": ""},
        {k: v for k, v in BODY.items() if k != "industry"},
        {**BODY, "extra_key": "nope"},
    ],
)
def test_invalid_submission_returns_422_without_running_any_stage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, bad_body: dict
) -> None:
    llm = fake_llm(monkeypatch, LLM_REPLY_OK)
    search = fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))

    response = post(client, bad_body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert_no_leaks(response)
    assert llm.calls == [] and search.calls == []


def test_unexpected_crash_returns_generic_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, RuntimeError("provider internals"))
    response = post(client)

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong. Please try again."}
    }
    assert "provider internals" not in response.text
    assert_no_leaks(response)


def test_route_is_published_in_openapi(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert URL in spec["paths"]
    assert "PipelineResult" in spec["components"]["schemas"]

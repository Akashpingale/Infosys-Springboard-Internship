import pytest
from fastapi.testclient import TestClient

from agents import extraction_agent
from tests.fakes import LLM_REPLY_NOT_JSON, LLM_REPLY_OK, VALID_EXTRACTION, make_sequence
from utils import llm_client
from utils.errors import LLMAPIError, LLMConfigError

URL = "/api/ideas/extract"
BODY = {
    "idea_description": "An AI app that detects crop diseases from phone photos for small farmers.",
    "industry": "Agriculture / AgriTech",
    "target_customers": "Small farmers in India",
    "relevant_details": "Pilot in Maharashtra",
}


def use_fake(monkeypatch: pytest.MonkeyPatch, *outcomes: object):
    fake = make_sequence(*outcomes)
    monkeypatch.setattr(extraction_agent, "generate_json", fake)
    return fake


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status
    body = response.json()
    assert body["error"]["code"] == code
    assert "Traceback" not in response.text and "test-llm-key" not in response.text
    return body["error"]


def test_extract_returns_structured_idea(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake(monkeypatch, LLM_REPLY_OK)
    response = client.post(URL, json=BODY)
    assert response.status_code == 200
    assert response.json() == VALID_EXTRACTION


def test_invalid_input_returns_422_without_calling_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = use_fake(monkeypatch, LLM_REPLY_OK)
    response = client.post(URL, json={**BODY, "idea_description": "   "})
    assert_error(response, 422, "invalid_input")
    assert fake.calls == []


def test_missing_field_returns_422(client: TestClient) -> None:
    body = {k: v for k, v in BODY.items() if k != "target_customers"}
    error = assert_error(client.post(URL, json=body), 422, "invalid_input")
    assert "target_customers" in error["message"]


def test_missing_llm_key_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY")
    error = assert_error(client.post(URL, json=BODY), 503, "llm_not_configured")
    assert error["message"] == "The AI service is not configured."


def test_llm_api_error_returns_502(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake(monkeypatch, LLMAPIError(llm_client.MSG_RATE_LIMIT))
    error = assert_error(client.post(URL, json=BODY), 502, "llm_api_error")
    assert error["message"] == llm_client.MSG_RATE_LIMIT


def test_invalid_reply_twice_returns_502(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake(monkeypatch, LLM_REPLY_NOT_JSON)
    error = assert_error(client.post(URL, json=BODY), 502, "llm_invalid_response")
    assert error["message"] == "Could not understand the AI reply. Please try again."


def test_unexpected_crash_returns_generic_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fake(monkeypatch, RuntimeError("provider internals"))
    error = assert_error(client.post(URL, json=BODY), 500, "internal_error")
    assert error["message"] == "Something went wrong. Please try again."


def test_route_listed_in_openapi(client: TestClient) -> None:
    assert URL in client.get("/openapi.json").json()["paths"]


def test_model_not_found_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake(monkeypatch, LLMConfigError(llm_client.MSG_MODEL_NOT_FOUND))
    error = assert_error(client.post(URL, json=BODY), 503, "llm_not_configured")
    assert error["message"] == "The configured AI model was not found. Check LLM_MODEL in .env."

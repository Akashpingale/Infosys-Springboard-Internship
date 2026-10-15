import pytest
from fastapi.testclient import TestClient

from app import create_app
from models.schemas import IdeaSubmission
from utils.errors import LLMConfigError


@pytest.fixture
def app_with_test_routes() -> TestClient:
    app = create_app()

    @app.get("/raise-app-error")
    def raise_app_error() -> None:
        raise LLMConfigError()

    @app.get("/raise-unexpected")
    def raise_unexpected() -> None:
        raise RuntimeError("secret internal detail")

    @app.post("/echo")
    def echo(body: IdeaSubmission) -> IdeaSubmission:
        return body

    return TestClient(app, raise_server_exceptions=False)


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "llm_configured": True, "search_configured": True}


def test_health_reports_missing_keys_without_values(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TAVILY_API_KEY")
    body = client.get("/health").json()
    assert body["search_configured"] is False
    assert "test-llm-key" not in str(body)


def test_app_error_returns_error_json(app_with_test_routes: TestClient) -> None:
    response = app_with_test_routes.get("/raise-app-error")
    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "llm_not_configured", "message": "The AI service is not configured."}
    }


def test_unexpected_error_hides_details(app_with_test_routes: TestClient) -> None:
    response = app_with_test_routes.get("/raise-unexpected")
    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Something went wrong. Please try again."
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text


def test_invalid_body_returns_readable_422(app_with_test_routes: TestClient) -> None:
    response = app_with_test_routes.post(
        "/echo",
        json={
            "idea_description": "one two",
            "industry": "Agriculture / AgriTech",
            "target_customers": "Farmers",
        },
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert error["message"].startswith("idea_description:")


def test_unknown_route_uses_error_json(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "http_404", "message": "Not Found"}}

"""The run API and CORS (KIRO_UI_UPGRADE_SPEC.md Sections 10.1, 10.5 and 10.6).

The application gets a run manager whose pipeline is a fake and whose history is a temporary file,
so no route here reaches an LLM, a search API or `data/runs.db`.
"""

import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from config import DEFAULT_CORS_ORIGINS
from models.api import RUN_STATES, STAGE_STATUSES
from models.schemas import PipelineResult
from orchestrator import STAGE_EXTRACTION, STAGE_SEARCH
from tests.run_fakes import (
    REVIEWED_IDEA,
    SUBMISSION,
    FakePipeline,
    failing_result,
    manager_with,
    result,
    store_in,
)
from utils.run_store import RunStore

RUNS = "/api/runs"
BODY = {"submission": SUBMISSION.model_dump(mode="json")}
SECRETS = ("test-llm-key", "test-tavily-key")


@pytest.fixture
def pipeline() -> FakePipeline:
    return FakePipeline()


@pytest.fixture
def client(tmp_path: Path, pipeline: FakePipeline) -> TestClient:
    """A client whose runs go through the fake pipeline and a temporary history file."""
    app = create_app()
    app.state.run_manager = manager_with(store_in(tmp_path), pipeline)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.state.run_manager.shutdown()


def start(client: TestClient, body: dict | None = None) -> str:
    response = client.post(RUNS, json=body or BODY)
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def wait_for(client: TestClient, run_id: str, timeout: float = 10.0) -> dict:
    manager = client.app.state.run_manager
    assert manager.wait(run_id, timeout), "the run did not finish in time"
    response = client.get(f"{RUNS}/{run_id}")
    assert response.status_code == 200, response.text
    return response.json()


# --- starting and polling --------------------------------------------------------------------


def test_a_run_starts_at_once_and_reports_its_id(client: TestClient) -> None:
    response = client.post(RUNS, json=BODY)

    assert response.status_code == 202, "the run is accepted, not awaited"
    body = response.json()
    assert set(body) == {"run_id", "state"} and body["state"] in RUN_STATES
    assert body["run_id"]


def test_polling_shows_the_stages_and_then_the_result(client: TestClient) -> None:
    run_id = start(client)

    body = wait_for(client, run_id)

    assert body["state"] == "done" and body["id"] == run_id
    assert [stage["key"] for stage in body["stages"]] == [
        "extraction", "search", "market_opportunity", "competitor_analysis"
    ]
    assert all(stage["status"] in STAGE_STATUSES for stage in body["stages"])
    assert [stage["label"] for stage in body["stages"]] == [
        "Understanding your idea", "Searching the web", "Analysing the market", "Comparing competitors"
    ]
    assert PipelineResult.model_validate(body["result"]).status == "complete"
    assert body["submission"]["industry"] == SUBMISSION.industry


def test_polling_the_same_run_twice_does_not_start_another(client: TestClient, pipeline: FakePipeline) -> None:
    run_id = start(client)
    wait_for(client, run_id)

    for _ in range(3):
        assert client.get(f"{RUNS}/{run_id}").json()["id"] == run_id

    assert len(pipeline.calls) == 1, "polling never runs the pipeline again"
    assert len(client.get(RUNS).json()["runs"]) == 1


def test_a_reviewed_idea_is_sent_through_and_extraction_is_not_repeated(
    client: TestClient, pipeline: FakePipeline
) -> None:
    run_id = start(client, {**BODY, "idea_override": REVIEWED_IDEA.model_dump(mode="json")})

    body = wait_for(client, run_id)

    assert pipeline.calls[0]["idea"] == REVIEWED_IDEA
    assert STAGE_EXTRACTION not in pipeline.started_stages
    assert body["idea_override"]["idea_title"] == REVIEWED_IDEA.idea_title


def test_an_unknown_run_is_a_plain_404(client: TestClient) -> None:
    response = client.get(f"{RUNS}/absent")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"
    assert "Traceback" not in response.text


def test_a_bad_body_is_rejected_with_the_error_shape(client: TestClient) -> None:
    response = client.post(RUNS, json={"submission": {"idea_description": "too short"}})

    assert response.status_code == 422
    assert set(response.json()) == {"error"} and response.json()["error"]["code"] == "invalid_input"


def test_an_unknown_field_in_the_body_is_refused(client: TestClient) -> None:
    response = client.post(RUNS, json={**BODY, "surprise": 1})
    assert response.status_code == 422


def test_a_third_run_is_refused_while_two_are_going(tmp_path: Path) -> None:
    gate = threading.Event()
    pipeline = FakePipeline(block=gate, block_at=STAGE_EXTRACTION)
    app = create_app()
    app.state.run_manager = manager_with(store_in(tmp_path), pipeline)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            start(client), start(client)

            response = client.post(RUNS, json=BODY)

            assert response.status_code == 409
            assert response.json()["error"]["code"] == "run_limit_reached"
            assert "already running" in response.json()["error"]["message"]
    finally:
        gate.set()
        app.state.run_manager.shutdown()


# --- cancelling ------------------------------------------------------------------------------


def test_cancelling_is_accepted_and_the_run_ends_as_cancelled(tmp_path: Path) -> None:
    gate = threading.Event()
    pipeline = FakePipeline(result(status="partial"), block=gate, block_at=STAGE_SEARCH)
    app = create_app()
    app.state.run_manager = manager_with(store_in(tmp_path), pipeline)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            run_id = start(client)
            assert pipeline.reached.wait(10)

            response = client.post(f"{RUNS}/{run_id}/cancel")
            assert response.status_code == 200
            assert response.json()["cancel_requested"] is True

            gate.set()
            body = wait_for(client, run_id)
            assert body["state"] == "cancelled"
            assert body["result"] is not None, "what finished is kept"
    finally:
        gate.set()
        app.state.run_manager.shutdown()


def test_cancelling_an_unknown_run_is_a_404(client: TestClient) -> None:
    assert client.post(f"{RUNS}/absent/cancel").status_code == 404


# --- history ---------------------------------------------------------------------------------


def test_the_history_lists_finished_runs_newest_first(client: TestClient) -> None:
    first = start(client)
    wait_for(client, first)
    second = start(client)
    wait_for(client, second)

    rows = client.get(RUNS).json()["runs"]

    assert [row["id"] for row in rows] == [second, first]
    assert all(row["status"] == "complete" and row["state"] == "done" for row in rows)


def test_the_history_starts_empty(client: TestClient) -> None:
    assert client.get(RUNS).json() == {"runs": []}


def test_a_run_can_be_renamed(client: TestClient) -> None:
    run_id = start(client)
    wait_for(client, run_id)

    response = client.patch(f"{RUNS}/{run_id}", json={"title": "  Leaf scanner  "})

    assert response.status_code == 200
    assert response.json()["title"] == "Leaf scanner", "the title is trimmed"
    assert client.get(f"{RUNS}/{run_id}").json()["title"] == "Leaf scanner"


@pytest.mark.parametrize("title", ["", "   ", "x" * 121])
def test_a_bad_title_is_refused(client: TestClient, title: str) -> None:
    run_id = start(client)
    wait_for(client, run_id)
    assert client.patch(f"{RUNS}/{run_id}", json={"title": title}).status_code == 422


def test_renaming_an_unknown_run_is_a_404(client: TestClient) -> None:
    assert client.patch(f"{RUNS}/absent", json={"title": "x"}).status_code == 404


def test_a_finished_run_can_be_deleted(client: TestClient) -> None:
    run_id = start(client)
    wait_for(client, run_id)

    response = client.delete(f"{RUNS}/{run_id}")

    assert response.status_code == 204 and response.content == b""
    assert client.get(f"{RUNS}/{run_id}").status_code == 404
    assert client.get(RUNS).json() == {"runs": []}


def test_deleting_a_going_run_is_refused_until_it_is_cancelled(tmp_path: Path) -> None:
    gate = threading.Event()
    pipeline = FakePipeline(block=gate, block_at=STAGE_SEARCH)
    app = create_app()
    app.state.run_manager = manager_with(store_in(tmp_path), pipeline)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            run_id = start(client)
            assert pipeline.reached.wait(10)

            response = client.delete(f"{RUNS}/{run_id}")

            assert response.status_code == 409 and response.json()["error"]["code"] == "run_active"
            gate.set()
            wait_for(client, run_id)
            assert client.delete(f"{RUNS}/{run_id}").status_code == 204
    finally:
        gate.set()
        app.state.run_manager.shutdown()


def test_deleting_an_unknown_run_is_a_404(client: TestClient) -> None:
    assert client.delete(f"{RUNS}/absent").status_code == 404


# --- the Markdown report ----------------------------------------------------------------------


def test_the_report_is_served_as_a_markdown_download(client: TestClient) -> None:
    run_id = start(client)
    wait_for(client, run_id)

    response = client.get(f"{RUNS}/{run_id}/report.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.startswith("# ")
    assert all(secret not in response.text for secret in SECRETS)


def test_the_report_of_a_run_with_no_analysis_still_explains_itself(tmp_path: Path) -> None:
    """The Section 10.5 fix: a failed run used to produce an empty download."""
    app = create_app()
    app.state.run_manager = manager_with(store_in(tmp_path), FakePipeline(failing_result(), fail_at=STAGE_EXTRACTION))
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            run_id = start(client)
            wait_for(client, run_id)

            response = client.get(f"{RUNS}/{run_id}/report.md")

            assert response.status_code == 200 and response.text.strip()
            assert "Status: Failed" in response.text
            assert "The AI service is busy right now." in response.text
            assert "No market opportunity analysis" in response.text
    finally:
        app.state.run_manager.shutdown()


def test_the_report_is_not_ready_before_a_stage_has_finished(tmp_path: Path) -> None:
    gate = threading.Event()
    pipeline = FakePipeline(block=gate, block_at=STAGE_EXTRACTION)
    app = create_app()
    app.state.run_manager = manager_with(store_in(tmp_path), pipeline)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            run_id = start(client)
            assert pipeline.reached.wait(10)

            response = client.get(f"{RUNS}/{run_id}/report.md")

            assert response.status_code == 409
            assert response.json()["error"]["code"] == "report_not_ready"
    finally:
        gate.set()
        app.state.run_manager.shutdown()


def test_the_report_of_an_unknown_run_is_a_404(client: TestClient) -> None:
    assert client.get(f"{RUNS}/absent/report.md").status_code == 404


# --- history unavailable ----------------------------------------------------------------------


def test_without_history_the_run_routes_answer_503_and_the_rest_keeps_working(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    path.write_bytes(b"not a database")
    app = create_app()
    app.state.run_manager = manager_with(RunStore(path), FakePipeline())
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            for response in (client.post(RUNS, json=BODY), client.get(RUNS)):
                assert response.status_code == 503
                assert response.json()["error"]["code"] == "history_unavailable"
                assert "Traceback" not in response.text

            assert client.get("/health").status_code == 200, "the rest of the API is unaffected"
            assert client.get("/api/meta").status_code == 200
    finally:
        app.state.run_manager.shutdown()


# --- CORS (Section 10.5) ----------------------------------------------------------------------


@pytest.mark.parametrize("origin", DEFAULT_CORS_ORIGINS)
def test_the_new_front_end_origins_are_allowed(client: TestClient, origin: str) -> None:
    response = client.get("/api/meta", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_a_preflight_for_a_run_is_answered(client: TestClient) -> None:
    response = client.options(
        RUNS,
        headers={
            "Origin": DEFAULT_CORS_ORIGINS[0],
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == DEFAULT_CORS_ORIGINS[0]
    assert "POST" in response.headers["access-control-allow-methods"]


def test_another_site_is_not_allowed(client: TestClient) -> None:
    response = client.get("/api/meta", headers={"Origin": "https://evil.example"})

    assert response.status_code == 200, "the API still answers"
    assert "access-control-allow-origin" not in response.headers, "but the browser will block it"


def test_credentials_are_never_allowed(client: TestClient) -> None:
    response = client.get("/api/meta", headers={"Origin": DEFAULT_CORS_ORIGINS[0]})
    assert "access-control-allow-credentials" not in response.headers


def test_the_origins_can_be_configured_and_a_wildcard_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:4173/ , *")
    with TestClient(create_app()) as client:
        allowed = client.get("/health", headers={"Origin": "http://localhost:4173"})
        wildcard = client.get("/health", headers={"Origin": "http://anything.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:4173"
    assert "access-control-allow-origin" not in wildcard.headers


def test_creating_the_app_writes_no_database_file() -> None:
    """A guard: the history file is opened only when a run route is used, never on import or
    startup. It may already exist from running the server by hand, so this checks that building
    the app leaves it exactly as it was.
    """
    real = Path(__file__).resolve().parent.parent / "data" / "runs.db"
    before = real.stat().st_mtime_ns if real.exists() else None

    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200

    after = real.stat().st_mtime_ns if real.exists() else None
    assert after == before, "building the app must not create or write the run database"

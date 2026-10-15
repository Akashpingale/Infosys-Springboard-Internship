"""Task 5 integration tests: every test idea through /api/validate, LLM and Tavily mocked."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents import extraction_agent
from models.schemas import IdeaSubmission, PipelineResult
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

IDEAS_DIR = Path(__file__).resolve().parent.parent / "data" / "test_ideas"
IDEA_FILES = sorted(IDEAS_DIR.glob("*.json"))
IDEA_NAMES = [path.stem for path in IDEA_FILES]
URL = "/api/validate"


def load_idea(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fake_llm(monkeypatch: pytest.MonkeyPatch, *replies: object):
    fake = make_sequence(*replies)
    monkeypatch.setattr(extraction_agent, "generate_json", fake)
    return fake


def fake_tavily(monkeypatch: pytest.MonkeyPatch, *outcomes: object):
    fake = make_sequence(*outcomes)
    monkeypatch.setattr(search_client.requests, "post", fake)
    return fake


# --- the test ideas themselves ----------------------------------------------


def test_at_least_three_test_ideas_exist() -> None:
    assert len(IDEA_FILES) >= 3, f"expected 3+ idea files in {IDEAS_DIR}"


def test_the_expected_industries_are_covered() -> None:
    industries = {load_idea(path)["industry"] for path in IDEA_FILES}
    assert {
        "Agriculture / AgriTech",
        "Healthcare / HealthTech",
        "Finance / FinTech",
    } <= industries
    assert len(industries) == len(IDEA_FILES), "each idea should use a different industry"


@pytest.mark.parametrize("path", IDEA_FILES, ids=IDEA_NAMES)
def test_each_idea_file_matches_the_submission_schema(path: Path) -> None:
    submission = IdeaSubmission(**load_idea(path))
    assert submission.relevant_details
    assert len(submission.idea_description.split()) >= 3


# --- the whole pipeline through the API -------------------------------------


@pytest.mark.parametrize("path", IDEA_FILES, ids=IDEA_NAMES)
def test_every_idea_completes_through_the_api(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, path: Path
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())

    response = client.post(URL, json=load_idea(path))
    assert response.status_code == 200

    result = PipelineResult.model_validate(response.json())
    assert result.status == "complete"
    assert result.errors == []

    idea = result.idea
    assert idea is not None
    assert idea.idea_title and idea.problem and idea.solution and idea.industry
    assert len(idea.target_customers) >= 1 and len(idea.key_features) >= 3

    search = result.search
    assert search is not None and len(search.sections) == 4
    assert search.total_results == 2
    labels = [section.label for section in search.sections]
    assert labels == [
        "Market size and trends",
        "Competitors",
        "Customer demand and pain points",
        "Recent news and funding",
    ]
    assert set(result.timings) == {"extraction", "search", "total"}


@pytest.mark.parametrize("path", IDEA_FILES, ids=IDEA_NAMES)
def test_every_idea_sends_four_queries_built_from_its_own_fields(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, path: Path
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    search = fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())

    client.post(URL, json=load_idea(path))
    queries = [call[1]["json"]["query"] for call in search.calls]
    assert len(queries) == 4
    assert len(set(queries)) == 4
    assert all(query.strip() for query in queries)


def test_extracted_fields_reach_the_response_unchanged(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())
    body = client.post(URL, json=load_idea(IDEAS_DIR / "agritech.json")).json()
    assert body["idea"] == VALID_EXTRACTION


# --- the response contract --------------------------------------------------


@pytest.mark.parametrize(
    ("llm", "tavily"),
    [
        (LLM_REPLY_OK, FakeHTTPResponse(200, TAVILY_OK_RESPONSE)),
        (LLM_REPLY_OK, tavily_status(429)),
        (LLM_REPLY_OK, TAVILY_TIMEOUT),
        (LLM_REPLY_OK, tavily_empty()),
        (LLM_REPLY_NOT_JSON, FakeHTTPResponse(200, TAVILY_OK_RESPONSE)),
    ],
)
def test_the_response_always_validates_as_a_pipeline_result(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, llm: object, tavily: object
) -> None:
    fake_llm(monkeypatch, llm)
    fake_tavily(monkeypatch, tavily)

    response = client.post(URL, json=load_idea(IDEAS_DIR / "healthtech.json"))
    assert response.status_code == 200

    result = PipelineResult.model_validate(response.json())
    assert result.status in {"complete", "partial", "failed"}
    assert "total" in result.timings
    assert "test-llm-key" not in response.text and "test-tavily-key" not in response.text

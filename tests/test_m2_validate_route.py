"""Task 3 through the API: POST /api/validate with and without the analysis stages.

The real orchestrator, stages and agents run; only the LLM and the searches are faked
(tests/pipeline_fakes.py), so nothing touches the network.
"""

import pytest
from fastapi.testclient import TestClient

import orchestrator
from models.schemas import PipelineResult
from tests.fakes import LLM_REPLY_NOT_JSON, VALID_EXTRACTION
from tests.m2_fakes import NO_MARKET_SIZE_RESULTS
from tests.pipeline_fakes import (
    NO_MARKET_CONTEXT_LINE,
    PIPELINE_SEARCH,
    PIPELINE_SUBMISSION,
    evidence_urls,
    use_full_pipeline,
)
from utils.errors import LLMAPIError, SearchAPIError

URL = "/api/validate"
FULL_URL = f"{URL}?include_analysis=true"
BODY = PIPELINE_SUBMISSION.model_dump(mode="json")
MILESTONE_1_FIELDS = {"status", "idea", "search", "warnings", "errors", "timings"}


def post(client: TestClient, url: str = FULL_URL):
    return client.post(url, json=BODY)


def assert_no_leaks(response) -> None:
    assert "Traceback" not in response.text
    assert "test-llm-key" not in response.text and "test-tavily-key" not in response.text


def full_run(client: TestClient) -> PipelineResult:
    response = post(client)
    assert response.status_code == 200, response.text
    assert_no_leaks(response)
    return PipelineResult.model_validate(response.json())


def test_the_full_pipeline_returns_both_analyses_and_the_milestone_1_fields(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_full_pipeline(monkeypatch)
    response = post(client)
    assert response.status_code == 200
    assert_no_leaks(response)

    body = response.json()
    assert MILESTONE_1_FIELDS <= set(body)
    result = PipelineResult.model_validate(body)
    assert result.status == "complete" and result.errors == []
    assert body["idea"] == VALID_EXTRACTION
    assert result.search == PIPELINE_SEARCH
    assert result.market is not None and result.competitors is not None
    assert set(result.timings) == {"extraction", "search", "market_opportunity", "competitor_analysis", "total"}


def test_every_url_in_the_response_comes_from_the_search_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_full_pipeline(monkeypatch)
    result = full_run(client)
    assert result.market is not None and result.competitors is not None

    urls = evidence_urls(NO_MARKET_SIZE_RESULTS)
    cited = [source.url for source in [*result.market.sources, *result.competitors.sources]]
    assert cited and set(cited) <= urls
    for competitor in result.competitors.competitors:
        assert competitor.website is None or any(url.startswith(competitor.website) for url in urls)


def test_without_the_parameter_only_the_milestone_1_stages_run(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    response = post(client, URL)
    assert response.status_code == 200

    body = response.json()
    assert body["market"] is None and body["competitors"] is None
    assert body["status"] == "complete" and body["idea"] == VALID_EXTRACTION
    assert set(body["timings"]) == {"extraction", "search", "total"}
    assert fakes.analysis_calls() == 0


def test_include_analysis_false_is_the_milestone_1_pipeline(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    body = post(client, f"{URL}?include_analysis=false").json()
    assert body["market"] is None and body["competitors"] is None
    assert fakes.analysis_calls() == 0


def test_an_invalid_parameter_value_returns_422_without_running_any_stage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    response = post(client, f"{URL}?include_analysis=maybe")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert "include_analysis" in response.json()["error"]["message"]
    assert fakes.extraction_llm.calls == [] and fakes.analysis_calls() == 0
    assert_no_leaks(response)


def test_a_market_failure_is_partial_and_keeps_the_competitors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch, market_llm=(LLMAPIError("The AI service is busy right now."),))
    result = full_run(client)

    assert result.status == "partial"
    assert result.market is None and result.competitors is not None
    assert result.errors[0].stage == "market_opportunity"
    assert result.errors[0].message == "The AI service is busy right now."
    assert NO_MARKET_CONTEXT_LINE in fakes.phase_c_prompt()


def test_a_search_failure_skips_both_analysis_stages(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch, search=(SearchAPIError("Web search could not be completed. Please try again."),))
    result = full_run(client)

    assert result.status == "partial" and result.idea is not None and result.search is None
    assert result.warnings == [
        orchestrator.WARNING_SEARCH_UNAVAILABLE,
        "Market opportunity: skipped because the web search did not complete.",
        "Competitor analysis: skipped because the web search did not complete.",
    ]
    assert result.market is None and result.competitors is None
    assert fakes.analysis_calls() == 0


def test_an_extraction_failure_is_failed_and_runs_nothing_else(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch, extraction=(LLM_REPLY_NOT_JSON,))
    result = full_run(client)

    assert result.status == "failed" and result.errors[0].stage == "extraction"
    assert result.warnings == [] and result.market is None and result.competitors is None
    assert fakes.search.calls == [] and fakes.analysis_calls() == 0


def test_an_unexpected_crash_in_an_analysis_stage_is_a_safe_partial_result(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_full_pipeline(monkeypatch, market_llm=(RuntimeError("provider internals"),))
    response = post(client)

    assert response.status_code == 200
    assert "provider internals" not in response.text
    result = PipelineResult.model_validate(response.json())
    assert result.status == "partial" and result.competitors is not None
    assert (result.errors[0].stage, result.errors[0].code) == ("market_opportunity", "internal_error")
    assert result.errors[0].message == "Something went wrong. Please try again."


def test_the_parameter_and_the_new_fields_are_published_in_openapi(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    parameters = spec["paths"][URL]["post"]["parameters"]
    assert [(p["name"], p["in"], p["required"]) for p in parameters] == [("include_analysis", "query", False)]
    properties = spec["components"]["schemas"]["PipelineResult"]["properties"]
    assert MILESTONE_1_FIELDS | {"market", "competitors"} <= set(properties)
    assert set(spec["components"]["schemas"]["PipelineResult"].get("required", [])) == {"status"}

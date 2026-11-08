"""Milestone 1 + 2 integration: the analysis evidence PipelineResult returns.

`market_search`, `competitor_candidates` and `competitor_search` travel from the agent context
into PipelineResult, so a client holding only the JSON response can rebuild the evidence each
agent worked from (market_evidence and competitor_evidence) and re-run the integrity checks on
`market` and `competitors`. The three fields are optional, so a Milestone 1 run and a Milestone 1
payload are unaffected.

The real orchestrator, stages, agents, guards and integrity checks run; only the LLM and the
searches are faked (tests/pipeline_fakes.py), so nothing touches the network.
"""

import json

import pytest
from fastapi.testclient import TestClient

import orchestrator
from agents.competitor_analysis_agent import competitor_evidence
from agents.evidence import render_evidence_for_prompt
from agents.integrity import check_competitor_integrity, check_market_integrity
from agents.market_size import market_evidence
from models.schemas import CompetitorCandidate, PipelineResult, SearchBundle
from orchestrator import FULL_STAGES
from tests.fakes import VALID_EXTRACTION
from tests.m2_fakes import COMPETITOR_TARGETED, MARKET_SIZE_SEARCH, NO_MARKET_SIZE_RESULTS
from tests.pipeline_fakes import PIPELINE_SEARCH, PIPELINE_SUBMISSION, use_full_pipeline
from utils.errors import LLMAPIError, SearchAPIError

URL = "/api/validate"
FULL_URL = f"{URL}?include_analysis=true"
BODY = PIPELINE_SUBMISSION.model_dump(mode="json")
AUDIT_FIELDS = ("market_search", "competitor_candidates", "competitor_search")
# The fake keys tests/conftest.py sets, and the names they are read from.
SECRETS = ("test-llm-key", "test-tavily-key", "LLM_API_KEY", "TAVILY_API_KEY")
EMPTY = (None, [], None)


def post(client: TestClient, url: str = FULL_URL):
    response = client.post(url, json=BODY)
    assert response.status_code == 200, response.text
    assert "Traceback" not in response.text
    for secret in SECRETS:
        assert secret not in response.text
    return response


def from_api(client: TestClient, url: str = FULL_URL) -> PipelineResult:
    """What a client has after the call: the result parsed from the JSON body alone."""
    return PipelineResult.model_validate(post(client, url).json())


def audit_fields(result: PipelineResult) -> tuple:
    return (result.market_search, result.competitor_candidates, result.competitor_search)


# --- the fields survive the pipeline ---------------------------------------------------------


def test_a_full_run_returns_the_evidence_each_analysis_stage_worked_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_full_pipeline(monkeypatch)
    run = orchestrator.run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert run.status == "complete" and run.market is not None and run.competitors is not None
    assert run.market_search is NO_MARKET_SIZE_RESULTS, "the market agent's own targeted searches"
    assert run.competitor_search is COMPETITOR_TARGETED, "the competitor agent's own searches"
    assert run.competitor_candidates and all(
        isinstance(candidate, CompetitorCandidate) for candidate in run.competitor_candidates
    )
    assert {candidate.name for candidate in run.competitor_candidates} >= {"Plantix", "LeafDoc"}
    assert [c.basis for c in run.competitor_candidates if c.name == "LeafDoc"] == ["user_provided"]


def test_the_fields_survive_the_json_response(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    body = post(client).json()

    assert set(AUDIT_FIELDS) <= set(body)
    result = PipelineResult.model_validate(body)
    assert result.market_search == NO_MARKET_SIZE_RESULTS, "labels, queries and search errors kept"
    assert result.competitor_search == COMPETITOR_TARGETED
    assert body["competitor_candidates"] == [c.model_dump(mode="json") for c in result.competitor_candidates]
    assert body["competitor_candidates"], "the Phase A candidates the agent kept"


# --- the returned evidence is enough to re-check the results ---------------------------------


def test_the_market_evidence_rebuilt_from_the_response_is_the_evidence_the_agent_used(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch, market_search=(MARKET_SIZE_SEARCH,))
    result = from_api(client)
    assert result.market is not None

    rebuilt = market_evidence(result.search, result.market_search, result.idea)
    prompt = fakes.market_llm.calls[0][0][1]
    assert render_evidence_for_prompt(rebuilt) in prompt, "the same items, ids and snippets"
    assert check_market_integrity(result.market, rebuilt) == []


def test_the_competitor_evidence_rebuilt_from_the_response_is_the_evidence_the_agent_used(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    result = from_api(client)
    assert result.competitors is not None

    rebuilt = competitor_evidence(result.search, result.competitor_search, result.competitor_candidates)
    assert render_evidence_for_prompt(rebuilt) in fakes.phase_c_prompt()
    assert check_competitor_integrity(result.competitors, rebuilt) == []


def test_every_source_the_results_cite_reappears_in_the_rebuilt_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_full_pipeline(monkeypatch)
    result = from_api(client)
    assert result.market is not None and result.competitors is not None

    pairs = (
        (result.market, market_evidence(result.search, result.market_search, result.idea)),
        (
            result.competitors,
            competitor_evidence(result.search, result.competitor_search, result.competitor_candidates),
        ),
    )
    for analysis, rebuilt in pairs:
        by_id = {item.id.upper(): item.url for item in rebuilt}
        assert analysis.sources, "the result cited something"
        for source in analysis.sources:
            assert by_id.get(source.id.upper()) == source.url, f"{source.id} rebuilt from the response"


def test_the_market_targeted_results_are_part_of_the_rebuilt_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the returned market_search the targeted pages are missing, so the field is
    load-bearing rather than decoration."""
    use_full_pipeline(monkeypatch, market_search=(MARKET_SIZE_SEARCH,))
    result = from_api(client)

    targeted = {r.url for section in MARKET_SIZE_SEARCH.sections for r in section.results}
    standard = {r.url for section in PIPELINE_SEARCH.sections for r in section.results}
    rebuilt = {item.url for item in market_evidence(result.search, result.market_search, result.idea)}
    without = {item.url for item in market_evidence(result.search, None, result.idea)}
    assert targeted - standard, "the fake adds pages the standard search did not have"
    assert targeted - standard <= rebuilt
    assert (targeted - standard) & without == set()


def test_dropping_a_returned_field_breaks_the_competitor_re_check(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same guard for the competitor fields: both are needed to rebuild the evidence, so a
    passing re-check is not an accident of the ids lining up."""
    use_full_pipeline(monkeypatch)
    result = from_api(client)
    assert result.competitors is not None

    used = competitor_evidence(result.search, result.competitor_search, result.competitor_candidates)
    no_targeted = competitor_evidence(result.search, None, result.competitor_candidates)
    no_candidates = competitor_evidence(result.search, result.competitor_search, None)

    assert check_competitor_integrity(result.competitors, used) == []
    for incomplete in (no_targeted, no_candidates):
        assert incomplete != used
        assert check_competitor_integrity(result.competitors, incomplete) != []


# --- Milestone 1 stays as it was -------------------------------------------------------------


def test_the_milestone_1_pipeline_leaves_the_fields_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = use_full_pipeline(monkeypatch)
    run = orchestrator.run_pipeline(PIPELINE_SUBMISSION)

    assert run.status == "complete" and run.market is None and run.competitors is None
    assert audit_fields(run) == EMPTY
    assert fakes.analysis_calls() == 0


def test_a_milestone_1_request_returns_the_fields_empty(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    body = post(client, URL).json()

    assert body["market_search"] is None and body["competitor_search"] is None
    assert body["competitor_candidates"] == []
    assert body["market"] is None and body["competitors"] is None
    assert body["idea"] == VALID_EXTRACTION and set(body["timings"]) == {"extraction", "search", "total"}
    assert fakes.analysis_calls() == 0


def test_a_milestone_1_payload_without_the_new_keys_still_validates() -> None:
    """An older client's stored response: the fields are optional, so nothing breaks."""
    result = PipelineResult.model_validate(
        {
            "status": "complete",
            "idea": VALID_EXTRACTION,
            "search": PIPELINE_SEARCH.model_dump(mode="json"),
            "warnings": [],
            "errors": [],
            "timings": {"extraction": 0.1, "search": 0.2, "total": 0.3},
        }
    )
    assert audit_fields(result) == EMPTY and result.market is None and result.competitors is None


def test_the_fields_are_published_as_optional_in_the_schema(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()["components"]["schemas"]["PipelineResult"]

    assert set(AUDIT_FIELDS) <= set(schema["properties"])
    assert set(schema.get("required", [])) == {"status"}, "only status stays required"


# --- a stage that did not finish returns no evidence for it ----------------------------------


def test_skipped_analysis_stages_return_no_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_full_pipeline(monkeypatch, search=(SearchAPIError("Web search could not be completed."),))
    result = from_api(client)

    assert result.status == "partial" and result.search is None
    assert audit_fields(result) == EMPTY, "no placeholder evidence for a stage that never ran"


def test_a_failed_market_stage_still_returns_the_searches_it_ran(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_full_pipeline(monkeypatch, market_llm=(LLMAPIError("The AI service is busy right now."),))
    result = from_api(client)

    assert result.status == "partial" and result.market is None
    assert result.market_search == NO_MARKET_SIZE_RESULTS, "the targeted searches ran before the call failed"
    assert result.competitors is not None and result.competitor_candidates


def test_a_failed_competitor_stage_returns_no_competitor_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_full_pipeline(monkeypatch, competitor_llm=(LLMAPIError("The AI service is busy right now."),))
    result = from_api(client)

    assert result.status == "partial" and result.competitors is None
    assert result.competitor_candidates == [] and result.competitor_search is None
    assert result.market is not None and result.market_search is not None


# --- nothing else rides along ----------------------------------------------------------------


def test_the_fields_carry_no_keys_and_no_internals(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_full_pipeline(monkeypatch)
    body = post(client).json()
    dumped = json.dumps({name: body[name] for name in AUDIT_FIELDS})

    for secret in SECRETS:
        assert secret not in dumped
    assert set(body["market_search"]) == set(SearchBundle.model_fields)
    assert set(body["competitor_search"]) == set(SearchBundle.model_fields)
    for candidate in body["competitor_candidates"]:
        assert set(candidate) == set(CompetitorCandidate.model_fields)

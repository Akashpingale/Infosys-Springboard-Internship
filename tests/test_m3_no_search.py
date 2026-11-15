from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents import web_search_agent
from agents.gtm_agent import GtmAgent
from agents.mvp_agent import MvpAgent
from agents.swot_risk_agent import SwotRiskAgent
from app import create_app
from orchestrator import STAGE_GTM, STAGE_MVP, STAGE_SWOT, STRATEGY_ONLY_STAGES, TOTAL_KEY, StageEvent, run_pipeline
from tests.m3_fakes import CONSTRAINTS, STRATEGY_KEYS, full_result, outside_calls
from tests.pipeline_fakes import PIPELINE_SUBMISSION, PipelineFakes, use_full_pipeline
from tests.run_fakes import store_in
from tests.test_m3_gtm_agent import draft as gtm_draft
from tests.test_m3_gtm_agent import use_mvp_reply, use_swot_reply
from tests.test_m3_gtm_agent import use_reply as use_gtm_reply
from tests.test_m3_mvp_agent import as_reply
from tests.test_m3_mvp_agent import draft as mvp_draft
from tests.test_m3_swot_agent import draft as swot_draft
from utils import search_client
from utils.run_manager import RunManager

RUNS = "/api/runs"
BODY = {"submission": PIPELINE_SUBMISSION.model_dump(mode="json")}
FOUR = ["extraction", "search", "market_opportunity", "competitor_analysis"]


class Spy:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise RuntimeError("a strategy stage must not search")


class Spies:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, fakes: PipelineFakes) -> None:
        self.search = Spy()
        self.http = Spy()
        self.fakes = fakes
        monkeypatch.setattr(web_search_agent, "search", self.search)
        monkeypatch.setattr(search_client.requests, "post", self.http)

    def searches(self) -> int:
        return len(self.search.calls) + len(self.http.calls) + len(self.fakes.search.calls) + len(
            self.fakes.market_search.calls) + len(self.fakes.competitor_search.calls)


class Replies:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.swot = use_swot_reply(monkeypatch, as_reply(swot_draft()))
        self.mvp = use_mvp_reply(monkeypatch, as_reply(mvp_draft()))
        self.gtm = use_gtm_reply(monkeypatch, as_reply(gtm_draft()))

    def counts(self) -> dict[str, int]:
        return {STAGE_SWOT: len(self.swot.calls), STAGE_MVP: len(self.mvp.calls), STAGE_GTM: len(self.gtm.calls)}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    manager = RunManager(store_in(tmp_path))
    app = create_app()
    app.state.run_manager = manager
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    manager.shutdown()


def wait_for(client: TestClient, run_id: str) -> dict:
    assert client.app.state.run_manager.wait(run_id, 10), "the run did not finish in time"
    return client.get(f"{RUNS}/{run_id}").json()


def start(client: TestClient, body: dict = BODY) -> str:
    response = client.post(RUNS, json=body)
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def test_the_real_agents_are_the_ones_under_test() -> None:
    assert [type(stage.agent) for stage in STRATEGY_ONLY_STAGES] == [SwotRiskAgent, MvpAgent, GtmAgent]


def test_a_strategy_job_in_either_mode_makes_no_search_and_does_not_rerun_stages_1_to_4(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    spies = Spies(monkeypatch, fakes)
    run_id = start(client)
    before = wait_for(client, run_id)
    earlier_calls = outside_calls(fakes)
    earlier_searches = spies.searches()
    replies = Replies(monkeypatch)

    for mode, expected in (("missing", 1), ("all", 2)):
        response = client.post(f"{RUNS}/{run_id}/strategy", json={"mode": mode, "constraints": CONSTRAINTS.model_dump(mode="json")})
        assert response.status_code == 202, response.text
        body = wait_for(client, run_id)

        assert spies.search.calls == [] and spies.http.calls == [], mode
        assert spies.searches() == earlier_searches, mode
        assert outside_calls(fakes) == earlier_calls, f"{mode}: no extraction, search or analysis call"
        assert replies.counts() == {key: expected for key in STRATEGY_KEYS}, mode
        assert body["stages"][:4] == before["stages"], mode
        assert body["result"]["status"] == "complete", mode
        assert all(body["result"][field] is not None for field in ("swot", "mvp", "gtm")), mode
        for key in ("idea", "search", "market", "competitors", "market_search", "competitor_search"):
            assert body["result"][key] == before["result"][key], (mode, key)


def test_a_run_with_strategy_searches_only_in_the_first_four_stages(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    fakes = use_full_pipeline(monkeypatch)
    spies = Spies(monkeypatch, fakes)
    replies = Replies(monkeypatch)
    plain = wait_for(client, start(client))
    four_stage = spies.searches()
    assert plain["result"]["status"] == "complete" and four_stage > 0

    body = wait_for(client, start(client, {**BODY, "include_strategy": True}))

    assert body["result"]["status"] == "complete" and [stage["key"] for stage in body["stages"]][4:] == list(STRATEGY_KEYS)
    assert spies.searches() == 2 * four_stage, "the strategy stages add no search"
    assert spies.search.calls == [] and spies.http.calls == []
    assert replies.counts() == {key: 1 for key in STRATEGY_KEYS}


def test_a_subset_of_the_strategy_stages_keeps_the_others_and_makes_no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    prior, fakes = full_result(monkeypatch)
    replies = Replies(monkeypatch)
    prior = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=prior)
    assert prior.status == "complete"
    prior = prior.model_copy(update={"mvp": None, "gtm": None, "status": "partial"})
    spies = Spies(monkeypatch, fakes)
    searches = spies.searches()
    calls = outside_calls(fakes)
    events: list[StageEvent] = []

    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES[1:], prior=prior, on_event=events.append)

    assert sorted({event.stage for event in events}) == sorted([STAGE_MVP, STAGE_GTM])
    assert spies.searches() == searches and outside_calls(fakes) == calls
    assert spies.search.calls == [] and spies.http.calls == []
    assert replies.counts() == {STAGE_SWOT: 1, STAGE_MVP: 2, STAGE_GTM: 2}
    assert result.status == "complete" and result.swot == prior.swot
    assert result.mvp is not None and result.gtm is not None
    assert result.timings[STAGE_SWOT] == prior.timings[STAGE_SWOT]
    assert result.timings[TOTAL_KEY] >= prior.timings[TOTAL_KEY]
    assert {key: result.timings[key] for key in FOUR} == {key: prior.timings[key] for key in FOUR}

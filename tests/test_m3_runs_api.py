import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from config import DEFAULT_CHAT_MAX_MESSAGE_CHARS, DEFAULT_CHAT_MAX_USER_TURNS, DEFAULT_STRATEGY_TIME_LIMIT_S
from models.api import MetaResponse, RunDetail
from models.schemas import (
    BUDGET_LEVELS,
    LAUNCH_REGION_MAX,
    MONTHS_TO_MVP_RANGE,
    TEAM_SIZE_RANGE,
    TECHNICAL_SKILLS,
    PipelineResult,
    StrategyConstraints,
)
from orchestrator import STAGE_MVP, STAGE_SWOT, STRATEGY_ONLY_STAGES, PendingStrategyAgent
from tests.m3_fakes import (
    CONSTRAINTS,
    GTM,
    MVP,
    STRATEGY_KEYS,
    SWOT,
    FakeStrategyAgent,
    outside_calls,
    use_fake_strategy,
)
from tests.pipeline_fakes import PIPELINE_SUBMISSION, use_full_pipeline
from tests.run_fakes import SUBMISSION, FakePipeline, manager_with, store_in
from utils.errors import LLMAPIError
from utils.run_manager import RunManager

RUNS = "/api/runs"
META = "/api/meta"
BODY = {"submission": SUBMISSION.model_dump(mode="json")}
STRATEGY_BODY = {"submission": PIPELINE_SUBMISSION.model_dump(mode="json")}
FOUR = ["extraction", "search", "market_opportunity", "competitor_analysis"]
FOUR_LABELS = ["Understanding your idea", "Searching the web", "Analysing the market", "Comparing competitors"]
SEVEN = [*FOUR, *STRATEGY_KEYS]
SEVEN_LABELS = [*FOUR_LABELS, "Assessing strengths and risks", "Recommending MVP features", "Planning go-to-market"]
DETAIL_KEYS_BEFORE = {
    "cancel_requested", "created_at", "duration_s", "elapsed_s", "finished_at", "id", "idea_override", "industry",
    "message", "result", "stages", "started_at", "state", "submission", "title",
}
STAGE_ENTRY_KEYS = {"duration_s", "elapsed_s", "key", "label", "message", "started_at", "status"}
ROW_KEYS_BEFORE = {"created_at", "duration_s", "id", "industry", "state", "status", "title"}
META_KEYS_BEFORE = {"app_name", "examples", "industries", "limits", "providers", "run_limits", "stages", "version"}
SECRETS = ("test-llm-key", "test-tavily-key")


@pytest.fixture
def pipeline() -> FakePipeline:
    return FakePipeline()


@pytest.fixture
def client(tmp_path: Path, pipeline: FakePipeline) -> TestClient:
    app = create_app()
    app.state.run_manager = manager_with(store_in(tmp_path), pipeline)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.state.run_manager.shutdown()


@pytest.fixture
def manager(tmp_path: Path) -> RunManager:
    created = RunManager(store_in(tmp_path))
    yield created
    created.shutdown()


@pytest.fixture
def strategy_client(manager: RunManager) -> TestClient:
    app = create_app()
    app.state.run_manager = manager
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def start(client: TestClient, body: dict) -> str:
    response = client.post(RUNS, json=body)
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def wait_for(client: TestClient, run_id: str) -> dict:
    assert client.app.state.run_manager.wait(run_id, 10), "the run did not finish in time"
    response = client.get(f"{RUNS}/{run_id}")
    assert response.status_code == 200, response.text
    return response.json()


def row_of(client: TestClient, run_id: str) -> dict:
    return next(row for row in client.get(RUNS).json()["runs"] if row["id"] == run_id)


def comparable(body: dict) -> dict:
    kept = {key: value for key, value in body.items() if key not in {"id", "created_at", "started_at", "finished_at"}}
    kept["stages"] = [{key: value for key, value in stage.items() if key != "started_at"} for stage in body["stages"]]
    return kept


def error_of(response) -> dict:
    assert set(response.json()) == {"error"}, response.text
    return response.json()["error"]


# --- the default request is unchanged ------------------------------------------------------------


def test_a_default_run_answers_exactly_as_before(client: TestClient, pipeline: FakePipeline) -> None:
    response = client.post(RUNS, json=BODY)

    assert response.status_code == 202
    assert response.json() == {"run_id": response.json()["run_id"], "state": "queued"}
    body = wait_for(client, response.json()["run_id"])

    assert set(body) == DETAIL_KEYS_BEFORE | {"constraints"} and body["constraints"] is None
    assert [stage["key"] for stage in body["stages"]] == FOUR
    assert [stage["label"] for stage in body["stages"]] == FOUR_LABELS
    assert all(set(stage) == STAGE_ENTRY_KEYS and stage["status"] == "done" for stage in body["stages"])
    assert body["state"] == "done" and body["message"] is None
    assert PipelineResult.model_validate(body["result"]) == pipeline.final
    assert [set(call) for call in pipeline.calls] == [{"submission", "idea", "time_limit_s"}]


def test_the_explicit_defaults_are_the_same_as_leaving_them_out(client: TestClient, pipeline: FakePipeline) -> None:
    plain = wait_for(client, start(client, BODY))
    explicit = wait_for(client, start(client, {**BODY, "include_strategy": False, "constraints": None}))

    assert comparable(plain) == comparable(explicit)
    assert row_of(client, plain["id"])["has_strategy"] is row_of(client, explicit["id"])["has_strategy"] is False
    assert len(pipeline.calls) == 2


def test_a_default_run_row_only_gains_has_strategy(client: TestClient) -> None:
    run_id = start(client, BODY)
    wait_for(client, run_id)

    row = row_of(client, run_id)

    assert set(row) == ROW_KEYS_BEFORE | {"has_strategy"}
    assert row["has_strategy"] is False and row["status"] == "complete" and row["state"] == "done"


def test_constraints_without_strategy_are_kept_and_the_run_has_four_stages(
    client: TestClient, pipeline: FakePipeline
) -> None:
    run_id = start(client, {**BODY, "constraints": {"team_size": 3}})
    body = wait_for(client, run_id)

    assert [stage["key"] for stage in body["stages"]] == FOUR
    assert body["constraints"] == StrategyConstraints(team_size=3).model_dump(mode="json")
    assert row_of(client, run_id)["has_strategy"] is False
    assert [set(call) for call in pipeline.calls] == [{"submission", "idea", "time_limit_s"}]


# --- include_strategy ----------------------------------------------------------------------------


def test_a_run_with_strategy_has_seven_stages_and_the_same_start_reply(
    monkeypatch: pytest.MonkeyPatch, strategy_client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    fakes = use_fake_strategy(monkeypatch)
    response = strategy_client.post(
        RUNS, json={**STRATEGY_BODY, "include_strategy": True, "constraints": CONSTRAINTS.model_dump(mode="json")}
    )

    assert response.status_code == 202
    assert set(response.json()) == {"run_id", "state"} and response.json()["state"] == "queued"
    body = wait_for(strategy_client, response.json()["run_id"])

    assert [stage["key"] for stage in body["stages"]] == SEVEN
    assert [stage["label"] for stage in body["stages"]] == SEVEN_LABELS
    assert all(stage["status"] == "done" for stage in body["stages"])
    assert body["state"] == "done" and body["result"]["status"] == "complete"
    result = PipelineResult.model_validate(body["result"])
    assert (result.swot, result.mvp, result.gtm, result.constraints) == (SWOT, MVP, GTM, CONSTRAINTS)
    assert body["constraints"] == CONSTRAINTS.model_dump(mode="json")
    assert fakes[STAGE_SWOT].seen[0]["constraints"] == CONSTRAINTS
    assert row_of(strategy_client, body["id"])["has_strategy"] is True


def test_a_run_with_strategy_without_constraints_reports_none(
    monkeypatch: pytest.MonkeyPatch, strategy_client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    body = wait_for(strategy_client, start(strategy_client, {**STRATEGY_BODY, "include_strategy": True}))

    assert body["constraints"] is None and body["result"]["constraints"] is None
    assert [stage["key"] for stage in body["stages"]] == SEVEN


def test_a_failed_strategy_stage_makes_the_run_partial_with_seven_entries(
    monkeypatch: pytest.MonkeyPatch, strategy_client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch, mvp=FakeStrategyAgent(STAGE_MVP, error=LLMAPIError()))
    body = wait_for(strategy_client, start(strategy_client, {**STRATEGY_BODY, "include_strategy": True}))

    assert body["state"] == "done" and body["result"]["status"] == "partial"
    assert {stage["key"]: stage["status"] for stage in body["stages"]}[STAGE_MVP] == "failed"
    assert row_of(strategy_client, body["id"])["has_strategy"] is True


def test_the_saved_detail_carries_the_constraints_after_a_restart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, manager: RunManager, strategy_client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    run_id = start(strategy_client, {**STRATEGY_BODY, "include_strategy": True,
                                     "constraints": CONSTRAINTS.model_dump(mode="json")})
    wait_for(strategy_client, run_id)
    again = RunManager(store_in(tmp_path))
    try:
        detail = again.get(run_id)
        rows = again.list()
    finally:
        again.shutdown()

    assert detail.constraints == CONSTRAINTS and [stage.key for stage in detail.stages] == SEVEN
    assert [(row.id, row.has_strategy) for row in rows] == [(run_id, True)]


def test_the_detail_still_matches_its_model(monkeypatch: pytest.MonkeyPatch, strategy_client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    body = wait_for(strategy_client, start(strategy_client, {**STRATEGY_BODY, "include_strategy": True}))

    assert RunDetail.model_validate(body).result.gtm == GTM


def test_a_run_with_strategy_searches_only_in_the_search_stages(
    monkeypatch: pytest.MonkeyPatch, strategy_client: TestClient
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    wait_for(strategy_client, start(strategy_client, STRATEGY_BODY))
    four_stage_calls = outside_calls(fakes)
    wait_for(strategy_client, start(strategy_client, {**STRATEGY_BODY, "include_strategy": True}))

    assert outside_calls(fakes) == 2 * four_stage_calls


# --- has_strategy ----------------------------------------------------------------------------------


def test_has_strategy_follows_the_run(monkeypatch: pytest.MonkeyPatch, strategy_client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    plain = start(strategy_client, STRATEGY_BODY)
    wait_for(strategy_client, plain)
    with_strategy = start(strategy_client, {**STRATEGY_BODY, "include_strategy": True})
    wait_for(strategy_client, with_strategy)

    rows = {row["id"]: row["has_strategy"] for row in strategy_client.get(RUNS).json()["runs"]}
    assert rows == {plain: False, with_strategy: True}

    response = strategy_client.post(f"{RUNS}/{plain}/strategy", json={})
    assert response.status_code == 202, response.text
    wait_for(strategy_client, plain)

    assert row_of(strategy_client, plain)["has_strategy"] is True


def test_has_strategy_is_in_the_reply_of_a_rename(monkeypatch: pytest.MonkeyPatch, strategy_client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    plain = start(strategy_client, STRATEGY_BODY)
    with_strategy = start(strategy_client, {**STRATEGY_BODY, "include_strategy": True})
    wait_for(strategy_client, plain), wait_for(strategy_client, with_strategy)

    renamed = [strategy_client.patch(f"{RUNS}/{run_id}", json={"title": "Renamed"}).json() for run_id in (plain, with_strategy)]

    assert [row["has_strategy"] for row in renamed] == [False, True]
    assert all(set(row) == ROW_KEYS_BEFORE | {"has_strategy"} for row in renamed)


def test_an_old_row_without_the_new_columns_reads_as_without_strategy(client: TestClient) -> None:
    run_id = start(client, BODY)
    wait_for(client, run_id)
    manager = client.app.state.run_manager
    manager._store.update(run_id, include_strategy=0, constraints_json=None)

    assert row_of(client, run_id)["has_strategy"] is False
    assert client.get(f"{RUNS}/{run_id}").json()["constraints"] is None


# --- constraints validation (Section 12.3) -------------------------------------------------------


@pytest.mark.parametrize(
    "constraints",
    [
        {"team_size": TEAM_SIZE_RANGE[0] - 1},
        {"team_size": TEAM_SIZE_RANGE[1] + 1},
        {"months_to_mvp": MONTHS_TO_MVP_RANGE[0] - 1},
        {"months_to_mvp": MONTHS_TO_MVP_RANGE[1] + 1},
        {"team_size": "two"},
        {"budget_level": "unlimited"},
        {"technical_skill": "expert"},
        {"launch_region": "x" * (LAUNCH_REGION_MAX + 1)},
        {"launch_region": 5},
        {"team_size": 2, "surprise": True},
        "small team",
    ],
)
def test_bad_constraints_are_refused_with_the_error_shape(client: TestClient, pipeline: FakePipeline, constraints) -> None:
    response = client.post(RUNS, json={**BODY, "include_strategy": True, "constraints": constraints})

    assert response.status_code == 422
    assert error_of(response)["code"] == "invalid_input"
    assert "constraints" in error_of(response)["message"] and "Traceback" not in response.text
    assert pipeline.calls == [] and client.get(RUNS).json() == {"runs": []}


@pytest.mark.parametrize("include_strategy", ["maybe", None, 2, [True]])
def test_a_bad_include_strategy_is_refused(client: TestClient, include_strategy) -> None:
    response = client.post(RUNS, json={**BODY, "include_strategy": include_strategy})

    assert response.status_code == 422 and error_of(response)["code"] == "invalid_input"


def test_constraints_at_their_limits_are_accepted(monkeypatch: pytest.MonkeyPatch, strategy_client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    for team, months, budget, skill in zip(TEAM_SIZE_RANGE, MONTHS_TO_MVP_RANGE, BUDGET_LEVELS, TECHNICAL_SKILLS):
        constraints = {"team_size": team, "months_to_mvp": months, "budget_level": budget,
                       "technical_skill": skill, "launch_region": "r" * LAUNCH_REGION_MAX}
        body = wait_for(strategy_client, start(strategy_client, {**STRATEGY_BODY, "include_strategy": True,
                                                                 "constraints": constraints}))
        assert body["constraints"] == constraints


def test_control_characters_are_stripped_from_the_region(
    monkeypatch: pytest.MonkeyPatch, manager: RunManager, strategy_client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    fakes = use_fake_strategy(monkeypatch)
    run_id = start(strategy_client, {**STRATEGY_BODY, "include_strategy": True,
                                     "constraints": {"launch_region": "Pune,\x00 India\x1b[31m\x7f"}})
    body = wait_for(strategy_client, run_id)

    assert body["constraints"]["launch_region"] == "Pune, India [31m"
    assert fakes[STAGE_SWOT].seen[0]["constraints"].launch_region == "Pune, India [31m"
    assert json.loads(manager._store.get(run_id)["constraints_json"])["launch_region"] == "Pune, India [31m"


def test_a_region_of_control_characters_only_becomes_none(client: TestClient) -> None:
    body = wait_for(client, start(client, {**BODY, "constraints": {"launch_region": "\x00\x01\t\n"}}))

    assert body["constraints"] == StrategyConstraints().model_dump(mode="json")


# --- /api/meta (Section 12.1) --------------------------------------------------------------------


@pytest.fixture
def meta(client: TestClient) -> dict:
    response = client.get(META)
    assert response.status_code == 200, response.text
    return response.json()


def test_meta_keeps_its_keys_and_gains_strategy_and_chat(meta: dict) -> None:
    assert set(meta) == META_KEYS_BEFORE | {"strategy", "chat"}
    assert [stage["key"] for stage in meta["stages"]] == FOUR, "the four stages are unchanged"
    assert MetaResponse.model_validate(meta).strategy.available is True


def test_meta_publishes_the_constraint_limits_and_choices_the_backend_enforces(meta: dict) -> None:
    strategy = meta["strategy"]

    assert strategy == {
        "available": True,
        "time_limit_s": DEFAULT_STRATEGY_TIME_LIMIT_S,
        "constraints": {
            "team_size": {"min_value": TEAM_SIZE_RANGE[0], "max_value": TEAM_SIZE_RANGE[1]},
            "months_to_mvp": {"min_value": MONTHS_TO_MVP_RANGE[0], "max_value": MONTHS_TO_MVP_RANGE[1]},
            "launch_region": {"min_chars": None, "max_chars": LAUNCH_REGION_MAX, "min_words": None},
            "budget_levels": list(BUDGET_LEVELS),
            "technical_skills": list(TECHNICAL_SKILLS),
        },
    }
    assert (TEAM_SIZE_RANGE, MONTHS_TO_MVP_RANGE, LAUNCH_REGION_MAX) == ((1, 10), (1, 12), 60)
    assert BUDGET_LEVELS == ("bootstrapped", "small", "funded")
    assert TECHNICAL_SKILLS == ("non_technical", "some", "strong")


def test_the_published_constraint_limits_are_usable(meta: dict) -> None:
    limits = meta["strategy"]["constraints"]
    for bound in ("min_value", "max_value"):
        StrategyConstraints(team_size=limits["team_size"][bound], months_to_mvp=limits["months_to_mvp"][bound])
    for budget, skill in zip(limits["budget_levels"], limits["technical_skills"]):
        StrategyConstraints(budget_level=budget, technical_skill=skill)
    StrategyConstraints(launch_region="r" * limits["launch_region"]["max_chars"])
    with pytest.raises(ValueError):
        StrategyConstraints(team_size=limits["team_size"]["max_value"] + 1)


def test_meta_publishes_the_chat_limits(meta: dict) -> None:
    assert meta["chat"] == {"max_message_chars": DEFAULT_CHAT_MAX_MESSAGE_CHARS, "max_user_turns": DEFAULT_CHAT_MAX_USER_TURNS}
    assert (DEFAULT_CHAT_MAX_MESSAGE_CHARS, DEFAULT_CHAT_MAX_USER_TURNS) == (1000, 25)


def test_meta_follows_the_configured_strategy_and_chat_settings(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRATEGY_TIME_LIMIT_S", "200")
    monkeypatch.setenv("CHAT_MAX_USER_TURNS", "10")
    monkeypatch.setenv("CHAT_MAX_MESSAGE_CHARS", "500")

    meta = client.get(META).json()

    assert meta["strategy"]["time_limit_s"] == 200.0
    assert meta["chat"] == {"max_message_chars": 500, "max_user_turns": 10}


def test_meta_says_strategy_is_unavailable_without_a_registered_agent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[2], "agent", PendingStrategyAgent(STRATEGY_ONLY_STAGES[2].name))

    assert client.get(META).json()["strategy"]["available"] is False


def test_meta_still_names_no_key(client: TestClient) -> None:
    body = client.get(META).text

    assert all(secret not in body for secret in SECRETS)
    for field in ("api_key", "apikey", "token", "authorization", "bearer", "secret", "password", "key_length"):
        assert field not in body.lower(), field


# --- the published schema --------------------------------------------------------------------------


def test_the_schema_keeps_the_start_reply_and_adds_the_strategy_route(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    runs = schema["paths"]["/api/runs"]["post"]
    strategy = schema["paths"]["/api/runs/{run_id}/strategy"]["post"]

    assert set(runs["responses"]) == {"202", "409", "422", "503"}
    assert runs["responses"]["202"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/RunStarted"}
    assert strategy["responses"]["202"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/RunStarted"}
    assert set(strategy["responses"]) == {"202", "404", "409", "422", "503"}
    assert set(schema["components"]["schemas"]["RunStarted"]["properties"]) == {"run_id", "state"}
    for name, added in (("RunDetail", "constraints"), ("RunSummary", "has_strategy"), ("MetaResponse", "strategy")):
        model = schema["components"]["schemas"][name]
        assert added in model["properties"] and added not in model.get("required", []), name

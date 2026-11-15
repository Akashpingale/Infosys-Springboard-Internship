import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import orchestrator
from app import create_app
from models.schemas import PipelineResult, StrategyConstraints
from orchestrator import STAGE_GTM, STAGE_MVP, STAGE_SWOT
from tests.m3_fakes import (
    CONSTRAINTS,
    FIELDS,
    GTM,
    MVP,
    STRATEGY_KEYS,
    SWOT,
    VALUES,
    FakeStrategyAgent,
    gate_agent,
    outside_calls,
    use_clock,
    use_fake_strategy,
)
from tests.pipeline_fakes import PIPELINE_SEARCH, PIPELINE_SUBMISSION, use_full_pipeline
from tests.run_fakes import FakePipeline, failing_result, manager_with, result, store_in
from utils.errors import (
    LLMAPIError,
    RunLimitError,
    RunNotFinishedError,
    RunNotFoundError,
    StrategyAlreadyCompleteError,
    StrategyNotReadyError,
)
from utils.run_manager import RunManager
from utils.run_store import RunStore

RUNS = "/api/runs"
BODY = {"submission": PIPELINE_SUBMISSION.model_dump(mode="json")}
WITH_STRATEGY = {**BODY, "include_strategy": True}
FOUR = ["extraction", "search", "market_opportunity", "competitor_analysis"]
SEVEN = [*FOUR, *STRATEGY_KEYS]
SWOT_2 = SWOT.model_copy(update={"summary": "Second synthetic SWOT."})
MVP_2 = MVP.model_copy(update={"summary": "Second synthetic MVP."})
GTM_2 = GTM.model_copy(update={"summary": "Second synthetic go-to-market plan."})
SECOND = {STAGE_SWOT: SWOT_2, STAGE_MVP: MVP_2, STAGE_GTM: GTM_2}


@pytest.fixture
def manager(tmp_path: Path) -> RunManager:
    created = RunManager(store_in(tmp_path))
    yield created
    created.shutdown()


@pytest.fixture
def client(manager: RunManager) -> TestClient:
    app = create_app()
    app.state.run_manager = manager
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def client_for(manager: RunManager) -> TestClient:
    app = create_app()
    app.state.run_manager = manager
    return TestClient(app, raise_server_exceptions=False)


def start(client: TestClient, body: dict = BODY) -> str:
    response = client.post(RUNS, json=body)
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def wait_for(client: TestClient, run_id: str) -> dict:
    assert client.app.state.run_manager.wait(run_id, 10), "the run did not finish in time"
    response = client.get(f"{RUNS}/{run_id}")
    assert response.status_code == 200, response.text
    return response.json()


def strategy(client: TestClient, run_id: str, body: dict | None = None):
    return client.post(f"{RUNS}/{run_id}/strategy", json={} if body is None else body)


def run_strategy(client: TestClient, run_id: str, body: dict | None = None) -> dict:
    response = strategy(client, run_id, body)
    assert response.status_code == 202, response.text
    return wait_for(client, run_id)


def error_of(response) -> dict:
    assert set(response.json()) == {"error"}, response.text
    return response.json()["error"]


def stage(body: dict, key: str) -> dict:
    return next(item for item in body["stages"] if item["key"] == key)


def strategy_of(body: dict) -> dict:
    return {key: body["result"][FIELDS[key]] for key in STRATEGY_KEYS}


def dumped(value) -> dict:
    return value.model_dump(mode="json")


def ordered_fakes(monkeypatch: pytest.MonkeyPatch, order: list[str], values: dict | None = None) -> dict:
    values = values or VALUES
    agents = {
        FIELDS[key]: FakeStrategyAgent(key, value=values[key], before=lambda key=key: order.append(key))
        for key in STRATEGY_KEYS
    }
    return use_fake_strategy(monkeypatch, **agents)


def calls(fakes: dict) -> dict[str, int]:
    return {key: fake.calls for key, fake in fakes.items()}


# --- the reply is that of POST /api/runs --------------------------------------------------------


def test_strategy_on_a_saved_run_answers_like_starting_a_run(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    run_id = start(client)
    before = wait_for(client, run_id)
    use_fake_strategy(monkeypatch)

    response = strategy(client, run_id, {"mode": "missing", "constraints": dumped(CONSTRAINTS)})

    assert response.status_code == 202
    assert response.json() == {"run_id": run_id, "state": "running"}
    body = wait_for(client, run_id)
    assert [item["key"] for item in body["stages"]] == SEVEN
    assert body["stages"][:4] == before["stages"], "the first four stages are untouched"
    assert body["state"] == "done" and body["result"]["status"] == "complete" and body["message"] is None
    assert strategy_of(body) == {key: dumped(value) for key, value in VALUES.items()}
    assert body["constraints"] == body["result"]["constraints"] == dumped(CONSTRAINTS)
    assert body["created_at"] == before["created_at"] and body["started_at"] == before["started_at"]


def test_an_empty_body_means_missing(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    run_id = start(client)
    wait_for(client, run_id)
    fakes = use_fake_strategy(monkeypatch)

    body = run_strategy(client, run_id)

    assert calls(fakes) == {key: 1 for key in STRATEGY_KEYS}
    assert body["result"]["status"] == "complete"


# --- rule 1: 404 ---------------------------------------------------------------------------------


def test_rule_1_an_unknown_run_is_a_404(client: TestClient) -> None:
    response = strategy(client, "no-such-run")

    assert response.status_code == 404
    assert error_of(response) == {"code": RunNotFoundError.code, "message": RunNotFoundError.default_message}


# --- rule 2: run_not_finished ------------------------------------------------------------------


def test_rule_2_a_running_run_is_refused(tmp_path: Path) -> None:
    gate = threading.Event()
    pipeline = FakePipeline(block=gate)
    manager = manager_with(store_in(tmp_path), pipeline)
    try:
        with client_for(manager) as client:
            run_id = start(client)
            assert pipeline.reached.wait(10)

            response = strategy(client, run_id, {"mode": "all"})

            assert response.status_code == 409
            assert error_of(response) == {"code": "run_not_finished", "message": "This validation is still running."}
            assert RunNotFinishedError.default_message == "This validation is still running."
            gate.set()
            assert wait_for(client, run_id)["state"] == "done"
    finally:
        gate.set()
        manager.shutdown()


# --- rule 3: strategy_not_ready ----------------------------------------------------------------


@pytest.mark.parametrize(
    "pipeline",
    [
        pytest.param(lambda: FakePipeline(result(status="partial")), id="no-market-and-no-competitors"),
        pytest.param(lambda: FakePipeline(failing_result(), fail_at="extraction"), id="no-idea"),
    ],
)
def test_rule_3_a_run_without_an_idea_or_an_analysis_is_refused(tmp_path: Path, pipeline) -> None:
    fake = pipeline()
    manager = manager_with(store_in(tmp_path), fake)
    try:
        with client_for(manager) as client:
            run_id = start(client)
            before = wait_for(client, run_id)

            response = strategy(client, run_id)

            assert response.status_code == 409
            assert error_of(response) == {
                "code": "strategy_not_ready",
                "message": "There is no market or competitor analysis to build a strategy on.",
            }
            assert StrategyNotReadyError.default_message == error_of(response)["message"]
            assert client.get(f"{RUNS}/{run_id}").json() == before
            assert len(fake.calls) == 1
    finally:
        manager.shutdown()


def test_rule_3_one_finished_analysis_is_enough(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_full_pipeline(monkeypatch, competitor_llm=(LLMAPIError(),))
    run_id = start(client)
    before = wait_for(client, run_id)
    assert before["result"]["competitors"] is None and before["result"]["market"] is not None
    use_fake_strategy(monkeypatch)

    body = run_strategy(client, run_id)

    assert body["state"] == "done" and body["result"]["status"] == "partial", "the earlier failure still counts"
    assert strategy_of(body) == {key: dumped(value) for key, value in VALUES.items()}


# --- rule 4: run_limit_reached -----------------------------------------------------------------


def test_rule_4_the_run_limit_is_shared_with_normal_runs(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    saved = start(client)
    wait_for(client, saved)
    complete = start(client, WITH_STRATEGY)
    wait_for(client, complete)
    gate, entered = threading.Event(), threading.Semaphore(0)

    def held_search(idea):
        entered.release()
        gate.wait(10)
        return PIPELINE_SEARCH

    monkeypatch.setattr(orchestrator, "run_web_search", held_search)
    try:
        running = [start(client), start(client)]
        assert entered.acquire(timeout=10) and entered.acquire(timeout=10)

        response = strategy(client, saved)

        assert response.status_code == 409
        assert error_of(response)["code"] == RunLimitError.code == "run_limit_reached"
        assert error_of(response)["message"] == RunLimitError.default_message
        assert error_of(strategy(client, complete))["code"] == "strategy_already_complete"
    finally:
        gate.set()
    for run_id in running:
        wait_for(client, run_id)
    assert [item["key"] for item in client.get(f"{RUNS}/{saved}").json()["stages"]] == FOUR
    assert strategy(client, saved).status_code == 202
    wait_for(client, saved)


# --- rule 5: strategy_already_complete ---------------------------------------------------------


@pytest.mark.parametrize("body", [None, {"mode": "missing"}, {"mode": "missing", "constraints": {"team_size": 4}}])
def test_rule_5_missing_with_nothing_missing_is_refused(
    monkeypatch: pytest.MonkeyPatch, manager: RunManager, client: TestClient, body: dict | None
) -> None:
    use_full_pipeline(monkeypatch)
    fakes = use_fake_strategy(monkeypatch)
    run_id = start(client, {**WITH_STRATEGY, "constraints": dumped(CONSTRAINTS)})
    before = wait_for(client, run_id)
    row = manager._store.get(run_id)

    response = strategy(client, run_id, body)

    assert response.status_code == 409
    assert error_of(response) == {"code": "strategy_already_complete", "message": "This validation already has a strategy."}
    assert StrategyAlreadyCompleteError.default_message == "This validation already has a strategy."
    assert calls(fakes) == {key: 1 for key in STRATEGY_KEYS}, "no stage ran again"
    assert client.get(f"{RUNS}/{run_id}").json() == before
    assert manager._store.get(run_id) == row, "nothing was written"


def test_rule_5_a_strategy_job_that_completed_the_run_also_counts(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    run_id = start(client)
    wait_for(client, run_id)
    use_fake_strategy(monkeypatch)
    run_strategy(client, run_id)

    assert error_of(strategy(client, run_id))["code"] == "strategy_already_complete"


# --- rule 6: all replaces everything, in order ------------------------------------------------


def test_rule_6_all_replaces_the_three_results_and_the_constraints_in_order(
    monkeypatch: pytest.MonkeyPatch, manager: RunManager, client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    run_id = start(client, {**WITH_STRATEGY, "constraints": dumped(CONSTRAINTS)})
    before = wait_for(client, run_id)
    order: list[str] = []
    fakes = ordered_fakes(monkeypatch, order, SECOND)
    other = StrategyConstraints(team_size=5, launch_region="Kenya")

    body = run_strategy(client, run_id, {"mode": "all", "constraints": dumped(other)})

    assert order == list(STRATEGY_KEYS), "SWOT, then MVP, then go-to-market"
    assert strategy_of(body) == {key: dumped(value) for key, value in SECOND.items()}
    assert body["constraints"] == body["result"]["constraints"] == dumped(other)
    assert json.loads(manager._store.get(run_id)["constraints_json"]) == dumped(other)
    assert all(fake.seen[0]["constraints"] == other for fake in fakes.values())
    assert fakes[STAGE_SWOT].seen[0]["swot"] is None, "the old results are not carried into the new run"
    assert fakes[STAGE_MVP].seen[0]["swot"] == SWOT_2 and fakes[STAGE_MVP].seen[0]["mvp"] is None
    assert fakes[STAGE_GTM].seen[0]["mvp"] == MVP_2 and fakes[STAGE_GTM].seen[0]["gtm"] is None
    assert [item["key"] for item in body["stages"]] == SEVEN and body["stages"][:4] == before["stages"][:4]
    assert all(item["status"] == "done" for item in body["stages"][4:])
    assert body["result"]["status"] == "complete" and body["result"]["errors"] == []


def test_rule_6_all_without_constraints_drops_the_stored_ones(
    monkeypatch: pytest.MonkeyPatch, manager: RunManager, client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    run_id = start(client, {**WITH_STRATEGY, "constraints": dumped(CONSTRAINTS)})
    wait_for(client, run_id)
    fakes = use_fake_strategy(monkeypatch)

    body = run_strategy(client, run_id, {"mode": "all", "constraints": None})

    assert body["constraints"] is None and body["result"]["constraints"] is None
    assert manager._store.get(run_id)["constraints_json"] is None
    assert all(fake.seen[0]["constraints"] is None for fake in fakes.values())


def test_rule_6_all_drops_the_old_errors_and_warnings_of_the_strategy_stages(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch, mvp=FakeStrategyAgent(STAGE_MVP, error=LLMAPIError("The AI service is busy right now.")))
    run_id = start(client, WITH_STRATEGY)
    before = wait_for(client, run_id)
    assert [error["stage"] for error in before["result"]["errors"]] == [STAGE_MVP]
    fakes = use_fake_strategy(monkeypatch)

    body = run_strategy(client, run_id, {"mode": "all"})

    assert calls(fakes) == {key: 1 for key in STRATEGY_KEYS}
    assert body["result"]["errors"] == [] and body["result"]["status"] == "complete" and body["message"] is None
    assert stage(body, STAGE_MVP)["status"] == "done" and stage(body, STAGE_MVP)["message"] is None


def test_rule_6_the_old_strategy_is_not_shown_while_all_runs(
    monkeypatch: pytest.MonkeyPatch, manager: RunManager, client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    run_id = start(client, WITH_STRATEGY)
    wait_for(client, run_id)
    gate, reached = threading.Event(), threading.Event()
    use_fake_strategy(monkeypatch, swot=gate_agent(STAGE_SWOT, gate, reached))
    try:
        assert strategy(client, run_id, {"mode": "all"}).status_code == 202
        assert reached.wait(10)
        running = client.get(f"{RUNS}/{run_id}").json()

        assert running["state"] == "running"
        assert all(running["result"][FIELDS[key]] is None for key in STRATEGY_KEYS)
        assert [item["status"] for item in running["stages"][4:]] == ["running", "waiting", "waiting"]
    finally:
        gate.set()
    assert wait_for(client, run_id)["result"]["status"] == "complete"


# --- mode = missing runs only the absent stages ----------------------------------------------


@pytest.mark.parametrize("failed", STRATEGY_KEYS)
def test_missing_runs_only_the_failed_stage(monkeypatch: pytest.MonkeyPatch, client: TestClient, failed: str) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch, **{FIELDS[failed]: FakeStrategyAgent(failed, error=LLMAPIError())})
    run_id = start(client, WITH_STRATEGY)
    before = wait_for(client, run_id)
    assert before["result"]["status"] == "partial" and before["result"][FIELDS[failed]] is None
    fakes = use_fake_strategy(monkeypatch, **{FIELDS[key]: FakeStrategyAgent(key, value=SECOND[key]) for key in STRATEGY_KEYS})

    body = run_strategy(client, run_id)

    assert calls(fakes) == {key: int(key == failed) for key in STRATEGY_KEYS}
    assert body["result"][FIELDS[failed]] == dumped(SECOND[failed])
    for key in STRATEGY_KEYS:
        if key != failed:
            assert body["result"][FIELDS[key]] == before["result"][FIELDS[key]], key
            assert stage(body, key) == stage(before, key), "a stage that is not run again keeps its entry"
    assert stage(body, failed)["status"] == "done"
    assert [item["key"] for item in body["stages"]] == SEVEN and body["stages"][:4] == before["stages"][:4]
    assert body["result"]["status"] == "complete" and body["result"]["errors"] == [] and body["message"] is None
    for key in ("idea", "search", "market", "competitors"):
        assert body["result"][key] == before["result"][key]


def test_missing_runs_the_absent_stages_in_order_and_the_later_ones_see_the_kept_results(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(
        monkeypatch,
        mvp=FakeStrategyAgent(STAGE_MVP, error=LLMAPIError()),
        gtm=FakeStrategyAgent(STAGE_GTM, error=LLMAPIError()),
    )
    run_id = start(client, WITH_STRATEGY)
    wait_for(client, run_id)
    order: list[str] = []
    fakes = ordered_fakes(monkeypatch, order, SECOND)

    body = run_strategy(client, run_id)

    assert order == [STAGE_MVP, STAGE_GTM]
    assert fakes[STAGE_MVP].seen[0]["swot"] == SWOT, "the kept SWOT feeds the MVP stage"
    assert fakes[STAGE_GTM].seen[0]["mvp"] == MVP_2
    assert strategy_of(body) == {STAGE_SWOT: dumped(SWOT), STAGE_MVP: dumped(MVP_2), STAGE_GTM: dumped(GTM_2)}


def test_missing_on_a_run_without_strategy_runs_all_three(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    fakes_before = use_full_pipeline(monkeypatch)
    run_id = start(client)
    wait_for(client, run_id)
    before = outside_calls(fakes_before)
    order: list[str] = []
    ordered_fakes(monkeypatch, order)

    body = run_strategy(client, run_id)

    assert order == list(STRATEGY_KEYS)
    assert [item["key"] for item in body["stages"]] == SEVEN
    assert outside_calls(fakes_before) == before


def test_missing_runs_the_stages_a_cancel_stopped(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    gate, reached = threading.Event(), threading.Event()
    use_fake_strategy(monkeypatch, swot=gate_agent(STAGE_SWOT, gate, reached))
    run_id = start(client, WITH_STRATEGY)
    assert reached.wait(10)
    client.post(f"{RUNS}/{run_id}/cancel")
    gate.set()
    before = wait_for(client, run_id)
    assert before["state"] == "cancelled"
    assert [item["status"] for item in before["stages"][4:]] == ["done", "cancelled", "cancelled"]
    fakes = use_fake_strategy(monkeypatch)

    body = run_strategy(client, run_id)

    assert calls(fakes) == {STAGE_SWOT: 0, STAGE_MVP: 1, STAGE_GTM: 1}
    assert body["state"] == "done" and [item["status"] for item in body["stages"][4:]] == ["done"] * 3


def test_missing_runs_the_stages_the_time_limit_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clock = use_clock(monkeypatch)
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch, swot=FakeStrategyAgent(STAGE_SWOT, before=lambda: clock.advance(500)))
    manager = RunManager(store_in(tmp_path), time_limit=lambda: 100.0, strategy_time_limit=lambda: 50.0)
    try:
        with client_for(manager) as client:
            run_id = start(client, WITH_STRATEGY)
            before = wait_for(client, run_id)
            assert [item["status"] for item in before["stages"][4:]] == ["done", "skipped", "skipped"]
            fakes = use_fake_strategy(monkeypatch)

            body = run_strategy(client, run_id)
    finally:
        manager.shutdown()

    assert calls(fakes) == {STAGE_SWOT: 0, STAGE_MVP: 1, STAGE_GTM: 1}
    assert body["result"]["status"] == "complete" and body["result"]["warnings"] == [
        warning for warning in before["result"]["warnings"] if not warning.startswith(("Recommending", "Planning"))
    ]


def test_missing_keeps_the_stored_constraints_unless_new_ones_are_given(
    monkeypatch: pytest.MonkeyPatch, manager: RunManager, client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch, gtm=FakeStrategyAgent(STAGE_GTM, error=LLMAPIError()))
    run_id = start(client, {**WITH_STRATEGY, "constraints": dumped(CONSTRAINTS)})
    wait_for(client, run_id)
    fakes = use_fake_strategy(monkeypatch, gtm=FakeStrategyAgent(STAGE_GTM, error=LLMAPIError()))

    kept = run_strategy(client, run_id)

    assert calls(fakes) == {STAGE_SWOT: 0, STAGE_MVP: 0, STAGE_GTM: 1}
    assert fakes[STAGE_GTM].seen[0]["constraints"] == CONSTRAINTS and kept["constraints"] == dumped(CONSTRAINTS)
    assert kept["result"]["constraints"] == dumped(CONSTRAINTS) and kept["result"]["gtm"] is None
    fakes = use_fake_strategy(monkeypatch)
    other = StrategyConstraints(team_size=4)

    replaced = run_strategy(client, run_id, {"constraints": dumped(other)})

    assert calls(fakes) == {STAGE_SWOT: 0, STAGE_MVP: 0, STAGE_GTM: 1}
    assert fakes[STAGE_GTM].seen[0]["constraints"] == other
    assert replaced["constraints"] == replaced["result"]["constraints"] == dumped(other)
    assert json.loads(manager._store.get(run_id)["constraints_json"]) == dumped(other)


# --- the request body --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"mode": "some"},
        {"mode": None},
        {"mode": "missing", "surprise": 1},
        {"constraints": {"team_size": 11}},
        {"constraints": {"months_to_mvp": 0}},
        {"constraints": {"budget_level": "rich"}},
        {"constraints": {"technical_skill": "guru"}},
        {"constraints": {"launch_region": "x" * 61}},
        {"constraints": {"team_size": 2, "unknown": "x"}},
        [],
    ],
)
def test_a_bad_body_is_refused_with_the_error_shape_and_starts_nothing(
    monkeypatch: pytest.MonkeyPatch, manager: RunManager, client: TestClient, body
) -> None:
    use_full_pipeline(monkeypatch)
    run_id = start(client)
    wait_for(client, run_id)
    row = manager._store.get(run_id)
    fakes = use_fake_strategy(monkeypatch)

    response = client.post(f"{RUNS}/{run_id}/strategy", json=body)

    assert response.status_code == 422
    assert error_of(response)["code"] == "invalid_input" and "Traceback" not in response.text
    assert calls(fakes) == {key: 0 for key in STRATEGY_KEYS}
    assert manager._store.get(run_id) == row


def test_a_request_without_a_body_is_refused(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    run_id = start(client)
    wait_for(client, run_id)

    response = client.post(f"{RUNS}/{run_id}/strategy")

    assert response.status_code == 422 and error_of(response)["code"] == "invalid_input"


def test_control_characters_are_stripped_from_the_region_of_a_strategy_job(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    use_full_pipeline(monkeypatch)
    run_id = start(client)
    wait_for(client, run_id)
    fakes = use_fake_strategy(monkeypatch)

    body = run_strategy(client, run_id, {"constraints": {"launch_region": "\x07East\x00 Africa\r\n"}})

    assert body["constraints"]["launch_region"] == "East Africa"
    assert fakes[STAGE_SWOT].seen[0]["constraints"].launch_region == "East Africa"


def test_without_history_the_route_answers_503(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    path.write_bytes(b"not a database")
    manager = manager_with(RunStore(path), FakePipeline())
    try:
        with client_for(manager) as client:
            response = strategy(client, "any-run")
    finally:
        manager.shutdown()

    assert response.status_code == 503 and error_of(response)["code"] == "history_unavailable"


def test_the_result_still_validates_after_each_mode(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_full_pipeline(monkeypatch)
    run_id = start(client)
    wait_for(client, run_id)
    use_fake_strategy(monkeypatch)

    for body in (None, {"mode": "all"}):
        detail = run_strategy(client, run_id, body)
        assert PipelineResult.model_validate(detail["result"]).swot == SWOT

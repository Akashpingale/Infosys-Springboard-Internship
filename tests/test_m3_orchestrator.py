import hashlib
import json
import threading
from pathlib import Path

import pytest
from google.genai import types

import orchestrator
from agents import competitor_analysis_agent as competitor_agent
from agents import market_opportunity_agent as market_agent
from agents.notices import build_notices
from models.schemas import PipelineResult, StageError
from orchestrator import (
    CODE_CANCELLED,
    EVENT_FAILED,
    EVENT_FINISHED,
    EVENT_SKIPPED,
    EVENT_STARTED,
    FULL_STAGES,
    SKIP_CANCELLED,
    SKIP_NO_ANALYSIS,
    SKIP_NO_TIME,
    STAGE_COMPETITOR,
    STAGE_EXTRACTION,
    STAGE_GTM,
    STAGE_MARKET,
    STAGE_MVP,
    STAGE_SEARCH,
    STAGE_SWOT,
    STAGES,
    STRATEGY_MAX_OUTPUT_TOKENS,
    STRATEGY_ONLY_STAGES,
    STRATEGY_STAGES,
    TOTAL_KEY,
    StageEvent,
    StrategyStage,
    run_pipeline,
)
from tests.fakes import LLM_REPLY_NOT_JSON
from tests.m3_fakes import (
    CONSTRAINTS,
    GTM,
    MVP,
    STRATEGY_KEYS,
    SWOT,
    SYSTEM,
    USER,
    FakeStrategyAgent,
    calling_llm,
    full_result,
    gate_agent,
    gemini_rate_limit,
    outside_calls,
    strategy_stage_labels,
    use_capturing_providers,
    use_clock,
    use_fake_strategy,
)
from tests.pipeline_fakes import PIPELINE_SEARCH, PIPELINE_SUBMISSION, use_full_pipeline
from tests.run_fakes import FakePipeline, finished, manager_with, stage_statuses, store_in
from utils import deadline, groq_client, llm_client
from utils.errors import (
    LLMAPIError,
    RunLimitError,
    RunNotFinishedError,
    RunNotFoundError,
    SearchAPIError,
    StrategyNotReadyError,
)
from utils.run_manager import MSG_PARTIAL, MSG_STAGE_CANCELLED, RunManager

FOUR = (STAGE_EXTRACTION, STAGE_SEARCH, STAGE_MARKET, STAGE_COMPETITOR)
SEVEN = (*FOUR, *STRATEGY_KEYS)
BASELINE_RESULT_SHA256 = "EA97276944FC16D80D335C8E241FE907BAA7F0FBCFBB4654C769AAEDB6D2F37A"
BASELINE_EVENTS = [(stage, kind) for stage in FOUR for kind in (EVENT_STARTED, EVENT_FINISHED)]
BASELINE_MANAGER_STAGES = [
    [STAGE_EXTRACTION, "Understanding your idea", "done", None],
    [STAGE_SEARCH, "Searching the web", "done", None],
    [STAGE_MARKET, "Analysing the market", "done", None],
    [STAGE_COMPETITOR, "Comparing competitors", "done", None],
]
LABELS = {
    STAGE_SWOT: "Assessing strengths and risks",
    STAGE_MVP: "Recommending MVP features",
    STAGE_GTM: "Planning go-to-market",
}


def digest(result: PipelineResult) -> str:
    data = result.model_dump(mode="json", exclude={"timings"})
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest().upper()


def collect(events: list[StageEvent]):
    return lambda event: events.append(event)


def kinds(events: list[StageEvent]) -> list[tuple[str, str]]:
    return [(event.stage, event.kind) for event in events]


def strategy_run(**options) -> tuple[PipelineResult, list[StageEvent]]:
    events: list[StageEvent] = []
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_STAGES, on_event=collect(events), **options)
    return result, events


@pytest.fixture
def manager(tmp_path: Path) -> RunManager:
    created = RunManager(store_in(tmp_path))
    yield created
    created.shutdown()


# --- the stage sets ---------------------------------------------------------------------------


def test_the_existing_stage_sets_are_unchanged() -> None:
    assert [stage.name for stage in STAGES] == [STAGE_EXTRACTION, STAGE_SEARCH]
    assert [stage.name for stage in FULL_STAGES] == list(FOUR)


def test_the_strategy_sets_add_three_stages_after_the_four() -> None:
    assert [stage.name for stage in STRATEGY_STAGES] == list(SEVEN)
    assert STRATEGY_STAGES[:4] == FULL_STAGES
    assert STRATEGY_STAGES[4:] == STRATEGY_ONLY_STAGES
    assert [stage.name for stage in STRATEGY_ONLY_STAGES] == list(STRATEGY_KEYS)


def test_every_strategy_stage_continues_on_failure_and_carries_its_label() -> None:
    assert all(isinstance(stage, StrategyStage) and stage.stop_on_failure is False for stage in STRATEGY_ONLY_STAGES)
    assert strategy_stage_labels() == LABELS


def test_without_a_registered_agent_a_strategy_stage_fails_plainly(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[0], "agent", orchestrator.PendingStrategyAgent(STAGE_SWOT))
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[1], "agent", orchestrator.PendingStrategyAgent(STAGE_MVP))
    monkeypatch.setattr(STRATEGY_ONLY_STAGES[2], "agent", orchestrator.PendingStrategyAgent(STAGE_GTM))
    result, _ = strategy_run()

    assert result.status == "partial"
    assert [error.stage for error in result.errors] == list(STRATEGY_KEYS)
    assert {error.message for error in result.errors} == {orchestrator.MSG_STRATEGY_PENDING}
    assert result.market is not None and result.competitors is not None


# --- FULL_STAGES as before ---------------------------------------------------------------------


def test_a_full_stages_run_is_identical_to_before(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    events: list[StageEvent] = []
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, on_event=collect(events))

    assert kinds(events) == BASELINE_EVENTS
    assert all(event.code is None and event.message is None for event in events)
    assert result.status == "complete"
    assert sorted(result.timings) == sorted([*FOUR, TOTAL_KEY])
    assert digest(result) == BASELINE_RESULT_SHA256
    assert result.swot is None and result.mvp is None and result.gtm is None and result.constraints is None


def test_a_default_background_run_is_identical_to_before(monkeypatch: pytest.MonkeyPatch, manager: RunManager) -> None:
    use_full_pipeline(monkeypatch)
    detail = finished(manager, manager.start(PIPELINE_SUBMISSION).id)

    assert detail.state == "done" and detail.message is None
    assert [[s.key, s.label, s.status, s.message] for s in detail.stages] == BASELINE_MANAGER_STAGES
    assert detail.result.status == "complete" and digest(detail.result) == BASELINE_RESULT_SHA256
    row = manager._store.get(detail.id)
    assert row["include_strategy"] == 0 and row["constraints_json"] is None


# --- order and status ----------------------------------------------------------------------------


def test_a_seven_stage_run_runs_in_order_and_is_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    result, events = strategy_run(constraints=CONSTRAINTS)

    assert kinds(events) == [(stage, kind) for stage in SEVEN for kind in (EVENT_STARTED, EVENT_FINISHED)]
    assert result.status == "complete" and result.errors == []
    assert (result.swot, result.mvp, result.gtm, result.constraints) == (SWOT, MVP, GTM, CONSTRAINTS)
    assert set(STRATEGY_KEYS) <= set(result.timings)
    finished_events = [event for event in events if event.kind == EVENT_FINISHED]
    assert finished_events[-1].result.gtm == GTM, "every ended stage carries the result so far"


def test_each_strategy_stage_reads_the_ones_before_it(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    fakes = use_fake_strategy(monkeypatch)
    strategy_run(constraints=CONSTRAINTS)

    swot, mvp, gtm = (fakes[key].seen[0] for key in STRATEGY_KEYS)
    assert swot["market"] is not None and swot["competitors"] is not None and swot["idea"] is not None
    assert swot["swot"] is None and swot["constraints"] == CONSTRAINTS
    assert mvp["swot"] == SWOT and mvp["mvp"] is None
    assert gtm["swot"] == SWOT and gtm["mvp"] == MVP


def test_a_failed_strategy_stage_makes_the_run_partial_and_keeps_everything_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_full_pipeline(monkeypatch)
    fakes = use_fake_strategy(monkeypatch, swot=FakeStrategyAgent(STAGE_SWOT, error=LLMAPIError("The AI service is busy right now.")))
    result, events = strategy_run()

    assert result.status == "partial"
    assert result.errors == [StageError(stage=STAGE_SWOT, code="llm_api_error", message="The AI service is busy right now.")]
    assert (STAGE_SWOT, EVENT_FAILED) in kinds(events)
    assert result.swot is None and result.mvp == MVP and result.gtm == GTM
    assert fakes[STAGE_MVP].seen[0]["swot"] is None, "MVP runs without SWOT"
    assert result.market is not None and result.competitors is not None and result.idea is not None


def test_go_to_market_runs_without_an_mvp(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    fakes = use_fake_strategy(monkeypatch, mvp=FakeStrategyAgent(STAGE_MVP, error=LLMAPIError()))
    result, _ = strategy_run()

    assert result.status == "partial" and result.mvp is None and result.gtm == GTM
    assert fakes[STAGE_GTM].seen[0]["mvp"] is None and fakes[STAGE_GTM].seen[0]["swot"] == SWOT


def test_an_unexpected_error_in_a_strategy_agent_becomes_the_generic_stage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch, swot=FakeStrategyAgent(STAGE_SWOT, error=RuntimeError("raw internals")))
    result, _ = strategy_run()

    (error,) = result.errors
    assert error.stage == STAGE_SWOT and error.code == "internal_error" and "raw internals" not in error.message
    assert result.status == "partial" and result.gtm == GTM


# --- the skip rules of Section 5.2 ------------------------------------------------------------


@pytest.mark.parametrize(
    ("options", "has_market", "has_competitors"),
    [
        pytest.param({"competitor_llm": (LLMAPIError(),)}, True, False, id="market_only"),
        pytest.param({"market_llm": (LLMAPIError(),)}, False, True, id="competitors_only"),
    ],
)
def test_one_finished_analysis_is_enough(
    monkeypatch: pytest.MonkeyPatch, options: dict, has_market: bool, has_competitors: bool
) -> None:
    use_full_pipeline(monkeypatch, **options)
    fakes = use_fake_strategy(monkeypatch)
    result, _ = strategy_run()

    assert (result.market is not None, result.competitors is not None) == (has_market, has_competitors)
    assert all(fakes[key].calls == 1 for key in STRATEGY_KEYS)
    assert result.swot == SWOT and result.mvp == MVP and result.gtm == GTM
    assert result.status == "partial", "the failed analysis stage still makes the run partial"


def test_without_any_finished_analysis_every_strategy_stage_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch, search=(SearchAPIError("Web search could not be completed."),))
    fakes = use_fake_strategy(monkeypatch)
    result, events = strategy_run()

    assert all(fakes[key].calls == 0 for key in STRATEGY_KEYS)
    skipped = [event for event in events if event.stage in STRATEGY_KEYS]
    assert [(event.stage, event.kind) for event in skipped] == [(key, EVENT_SKIPPED) for key in STRATEGY_KEYS]
    for key in STRATEGY_KEYS:
        assert SKIP_NO_ANALYSIS.format(label=LABELS[key]) in result.warnings
    assert result.status == "partial" and result.idea is not None


def test_a_failed_extraction_runs_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = use_full_pipeline(monkeypatch, extraction=(LLM_REPLY_NOT_JSON,))
    strategy = use_fake_strategy(monkeypatch)
    result, events = strategy_run()

    assert result.status == "failed"
    assert {event.stage for event in events} == {STAGE_EXTRACTION}
    assert fakes.search.calls == [] and all(strategy[key].calls == 0 for key in STRATEGY_KEYS)


# --- cancel and the time limit -----------------------------------------------------------------


def test_a_cancel_between_strategy_stages_skips_the_rest_and_keeps_what_finished(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_full_pipeline(monkeypatch)
    stop = threading.Event()
    fakes = use_fake_strategy(monkeypatch, swot=FakeStrategyAgent(STAGE_SWOT, before=stop.set))
    result, events = strategy_run(should_stop=stop.is_set)

    assert result.swot == SWOT and result.mvp is None and result.gtm is None
    assert fakes[STAGE_MVP].calls == 0 and fakes[STAGE_GTM].calls == 0
    cancelled = [event for event in events if event.code == CODE_CANCELLED]
    assert [(event.stage, event.kind) for event in cancelled] == [(STAGE_MVP, EVENT_SKIPPED), (STAGE_GTM, EVENT_SKIPPED)]
    assert SKIP_CANCELLED.format(label=LABELS[STAGE_MVP]) in result.warnings
    assert result.status == "partial"


def test_a_strategy_stage_after_the_time_limit_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = use_clock(monkeypatch)
    use_full_pipeline(monkeypatch)
    fakes = use_fake_strategy(monkeypatch, swot=FakeStrategyAgent(STAGE_SWOT, before=lambda: clock.advance(200)))
    result, events = strategy_run(time_limit_s=100, strategy_time_limit_s=50)

    assert result.swot == SWOT and fakes[STAGE_MVP].calls == 0 and fakes[STAGE_GTM].calls == 0
    assert SKIP_NO_TIME.format(label=LABELS[STAGE_MVP]) in result.warnings
    assert SKIP_NO_TIME.format(label=LABELS[STAGE_GTM]) in result.warnings
    assert (STAGE_GTM, EVENT_SKIPPED) in kinds(events) and result.status == "partial"


def test_the_strategy_time_is_added_only_from_the_first_strategy_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    use_clock(monkeypatch)
    fakes = use_full_pipeline(monkeypatch)
    seen: list[float | None] = []

    def market_llm(*args, **kwargs):
        seen.append(deadline.time_left())
        return fakes.market_llm(*args, **kwargs)

    monkeypatch.setattr(market_agent, "generate_json", market_llm)
    strategy = use_fake_strategy(monkeypatch)
    strategy_run(time_limit_s=100, strategy_time_limit_s=50)

    assert seen == [100], "stages 1 to 4 keep the limit they have today"
    assert [strategy[key].seen[0]["time_left"] for key in STRATEGY_KEYS] == [150, 150, 150]
    assert deadline.time_left() is None, "the limit lasts only for the run"


def test_the_strategy_stages_draw_on_the_second_part_of_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = use_clock(monkeypatch)
    fakes = use_full_pipeline(monkeypatch)

    def slow_competitors(*args, **kwargs):
        clock.advance(60)
        return fakes.competitor_llm(*args, **kwargs)

    monkeypatch.setattr(competitor_agent, "generate_json", slow_competitors)
    strategy = use_fake_strategy(monkeypatch)
    result, _ = strategy_run(time_limit_s=100, strategy_time_limit_s=50)

    assert result.competitors is not None
    assert strategy[STAGE_SWOT].seen[0]["time_left"] == pytest.approx(30)
    assert result.status == "complete"


def test_without_a_time_limit_the_strategy_time_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    fakes = use_fake_strategy(monkeypatch)
    strategy_run(strategy_time_limit_s=50)

    assert fakes[STAGE_SWOT].seen[0]["time_left"] is None


# --- the output-token limit of Section 11.1.3 --------------------------------------------------


def test_only_a_strategy_stage_raises_the_groq_output_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    gemini, groq = use_capturing_providers(monkeypatch, gemini_rate_limit(), '{"ok": true}')
    replies: list[str] = []
    use_fake_strategy(monkeypatch, swot=calling_llm(STAGE_SWOT, replies))
    strategy_run()
    llm_client.generate_json(SYSTEM, USER)

    assert replies == ['{"ok": true}']
    assert [body["max_completion_tokens"] for body in groq.bodies] == [STRATEGY_MAX_OUTPUT_TOKENS, 4096]
    assert STRATEGY_MAX_OUTPUT_TOKENS > groq_client.MAX_COMPLETION_TOKENS == 4096
    assert all(config.max_output_tokens is None for config in gemini.configs)


def test_an_existing_call_sends_the_same_requests_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, groq = use_capturing_providers(monkeypatch, gemini_rate_limit(), "{}")
    llm_client.generate_json(SYSTEM, USER)

    assert gemini.configs == [
        types.GenerateContentConfig(
            system_instruction=SYSTEM, temperature=llm_client.TEMPERATURE, response_mime_type="application/json"
        )
    ]
    assert groq.bodies == [{
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
        "temperature": llm_client.TEMPERATURE,
        "response_format": {"type": "json_object"},
        "reasoning_effort": "low",
        "include_reasoning": False,
        "max_completion_tokens": 4096,
    }]
    assert groq_client.request_body(SYSTEM, USER, 0.2) == groq_client.request_body(SYSTEM, USER, 0.2, None, None)


# --- a strategy-only job in the orchestrator ---------------------------------------------------


def test_a_strategy_only_job_starts_from_the_saved_result_without_searching(monkeypatch: pytest.MonkeyPatch) -> None:
    prior, fakes = full_result(monkeypatch)
    before = outside_calls(fakes)
    strategy = use_fake_strategy(monkeypatch)
    events: list[StageEvent] = []
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=prior, on_event=collect(events))

    assert outside_calls(fakes) == before, "no extraction, search or analysis call"
    assert kinds(events) == [(key, kind) for key in STRATEGY_KEYS for kind in (EVENT_STARTED, EVENT_FINISHED)]
    assert strategy[STAGE_SWOT].seen[0]["market"] == prior.market
    for name in ("idea", "search", "market", "competitors", "market_search", "competitor_candidates", "competitor_search", "warnings"):
        assert getattr(result, name) == getattr(prior, name)
    assert result.status == "complete" and (result.swot, result.mvp, result.gtm) == (SWOT, MVP, GTM)
    assert {key: result.timings[key] for key in FOUR} == {key: prior.timings[key] for key in FOUR}
    assert result.timings[TOTAL_KEY] >= prior.timings[TOTAL_KEY]


def test_a_strategy_only_job_on_a_partial_result_stays_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    prior, _ = full_result(monkeypatch, competitor_llm=(LLMAPIError(),))
    use_fake_strategy(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=prior)

    assert prior.status == "partial" and result.status == "partial"
    assert result.errors == prior.errors and result.gtm == GTM


def test_a_strategy_only_job_with_an_earlier_skipped_stage_is_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    prior, _ = full_result(monkeypatch)
    prior = prior.model_copy(update={"competitors": None, "status": "partial"})
    use_fake_strategy(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=prior)

    assert result.errors == [] and result.status == "partial"


def test_a_strategy_only_job_replaces_earlier_strategy_results_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    prior, _ = full_result(monkeypatch)
    stale = StageError(stage=STAGE_SWOT, code="llm_api_error", message="busy")
    prior = prior.model_copy(update={"status": "partial", "errors": [stale], "mvp": MVP, "constraints": CONSTRAINTS})
    fakes = use_fake_strategy(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=prior)

    assert result.errors == [] and result.status == "complete"
    assert fakes[STAGE_MVP].seen[0]["mvp"] is None, "a stage that runs again starts without its old result"
    assert fakes[STAGE_SWOT].seen[0]["constraints"] == CONSTRAINTS, "the saved constraints are used"
    assert result.constraints == CONSTRAINTS


@pytest.mark.parametrize("ending", ["cancelled", "time_limit"])
def test_a_strategy_only_job_drops_the_old_warnings_of_the_stages_it_runs_again(
    monkeypatch: pytest.MonkeyPatch, ending: str
) -> None:
    use_full_pipeline(monkeypatch)
    if ending == "cancelled":
        stop = threading.Event()
        use_fake_strategy(monkeypatch, swot=FakeStrategyAgent(STAGE_SWOT, before=stop.set))
        prior, _ = strategy_run(should_stop=stop.is_set)
    else:
        clock = use_clock(monkeypatch)
        use_fake_strategy(monkeypatch, swot=FakeStrategyAgent(STAGE_SWOT, before=lambda: clock.advance(200)))
        prior, _ = strategy_run(time_limit_s=100, strategy_time_limit_s=50)
    earlier = "2 of 6 web searches failed, so some sections are empty."
    prior = prior.model_copy(update={"warnings": [earlier, *prior.warnings]})
    assert any(warning.startswith(f"{LABELS[STAGE_MVP]}:") for warning in prior.warnings)
    assert any(notice.stage in STRATEGY_KEYS for notice in prior.notices)
    use_fake_strategy(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=prior)

    assert result.status == "complete" and (result.swot, result.mvp, result.gtm) == (SWOT, MVP, GTM)
    strategy_labels = tuple(f"{label}:" for label in LABELS.values())
    kept = [warning for warning in prior.warnings if not warning.startswith(strategy_labels)]
    assert earlier in kept and len(kept) < len(prior.warnings)
    assert result.warnings == kept, "the warnings of the first four stages are kept"
    assert not any(notice.stage in STRATEGY_KEYS for notice in result.notices)
    assert result.errors == [] and result.notices == build_notices(kept, [])


def test_new_constraints_replace_the_saved_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    prior, _ = full_result(monkeypatch)
    prior = prior.model_copy(update={"constraints": CONSTRAINTS})
    other = CONSTRAINTS.model_copy(update={"team_size": 5})
    fakes = use_fake_strategy(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=prior, constraints=other)

    assert fakes[STAGE_SWOT].seen[0]["constraints"] == other and result.constraints == other


# --- the run manager -----------------------------------------------------------------------------


def test_a_run_with_strategy_has_seven_stage_entries_and_saves_its_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_clock(monkeypatch)
    use_full_pipeline(monkeypatch)
    fakes = use_fake_strategy(monkeypatch)
    manager = RunManager(store_in(tmp_path), time_limit=lambda: 100.0, strategy_time_limit=lambda: 50.0)
    try:
        started = manager.start(PIPELINE_SUBMISSION, include_strategy=True, constraints=CONSTRAINTS)
        assert [(stage.key, stage.status) for stage in started.stages] == [(key, "waiting") for key in SEVEN]
        assert [stage.label for stage in started.stages][4:] == [LABELS[key] for key in STRATEGY_KEYS]
        detail = finished(manager, started.id)
    finally:
        manager.shutdown()

    assert detail.state == "done" and detail.message is None and detail.result.status == "complete"
    assert stage_statuses(detail) == {key: "done" for key in SEVEN}
    assert (detail.result.swot, detail.result.mvp, detail.result.gtm) == (SWOT, MVP, GTM)
    assert fakes[STAGE_SWOT].seen[0]["time_left"] == 150, "PIPELINE_TIME_LIMIT_S + STRATEGY_TIME_LIMIT_S"
    row = manager._store.get(started.id)
    assert row["include_strategy"] == 1 and json.loads(row["constraints_json"]) == CONSTRAINTS.model_dump(mode="json")
    assert [stage["key"] for stage in json.loads(row["stages_json"])] == list(SEVEN)


def test_a_failed_strategy_stage_leaves_the_run_done_and_partial(monkeypatch: pytest.MonkeyPatch, manager: RunManager) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch, mvp=FakeStrategyAgent(STAGE_MVP, error=LLMAPIError("The AI service is busy right now.")))
    detail = finished(manager, manager.start(PIPELINE_SUBMISSION, include_strategy=True).id)

    assert detail.state == "done" and detail.message == MSG_PARTIAL and detail.result.status == "partial"
    statuses = stage_statuses(detail)
    assert statuses[STAGE_MVP] == "failed" and statuses[STAGE_SWOT] == "done" and statuses[STAGE_GTM] == "done"
    assert next(s for s in detail.stages if s.key == STAGE_MVP).message == "The AI service is busy right now."


def test_skipped_strategy_stages_are_shown_as_skipped(monkeypatch: pytest.MonkeyPatch, manager: RunManager) -> None:
    use_full_pipeline(monkeypatch, search=(SearchAPIError("Web search could not be completed."),))
    use_fake_strategy(monkeypatch)
    detail = finished(manager, manager.start(PIPELINE_SUBMISSION, include_strategy=True).id)

    assert detail.state == "done" and detail.result.status == "partial"
    assert all(stage_statuses(detail)[key] == "skipped" for key in STRATEGY_KEYS)
    assert all(stage.message for stage in detail.stages if stage.key in STRATEGY_KEYS)


def test_a_cancel_between_strategy_stages_of_a_run(monkeypatch: pytest.MonkeyPatch, manager: RunManager) -> None:
    use_full_pipeline(monkeypatch)
    gate, reached = threading.Event(), threading.Event()
    use_fake_strategy(monkeypatch, swot=gate_agent(STAGE_SWOT, gate, reached))
    run_id = manager.start(PIPELINE_SUBMISSION, include_strategy=True).id
    assert reached.wait(10)
    manager.cancel(run_id)
    gate.set()
    detail = finished(manager, run_id)

    assert detail.state == "cancelled"
    statuses = stage_statuses(detail)
    assert statuses[STAGE_SWOT] == "done" and statuses[STAGE_MVP] == "cancelled" and statuses[STAGE_GTM] == "cancelled"
    assert detail.result.swot == SWOT and detail.result.market is not None


def done_run(monkeypatch: pytest.MonkeyPatch, manager: RunManager, **options) -> str:
    use_full_pipeline(monkeypatch, **options)
    detail = finished(manager, manager.start(PIPELINE_SUBMISSION).id)
    return detail.id


def test_a_strategy_job_appends_three_stages_and_returns_the_run_to_done(
    monkeypatch: pytest.MonkeyPatch, manager: RunManager
) -> None:
    run_id = done_run(monkeypatch, manager)
    before = manager.get(run_id)
    fakes = use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    started = manager.start_strategy(run_id, CONSTRAINTS)

    assert started.state == "running"
    assert [(stage.key, stage.status) for stage in started.stages][4:] == [(key, "waiting") for key in STRATEGY_KEYS]
    detail = finished(manager, run_id)

    assert outside_calls(fakes) == 0, "the stored idea and analyses are reused"
    assert detail.state == "done" and detail.message is None and detail.result.status == "complete"
    assert [stage.key for stage in detail.stages] == list(SEVEN)
    assert detail.stages[:4] == before.stages, "the earlier stages are untouched"
    assert all(stage.status == "done" for stage in detail.stages[4:])
    assert detail.result.market == before.result.market and detail.result.idea == before.result.idea
    assert (detail.result.swot, detail.result.mvp, detail.result.gtm, detail.result.constraints) == (SWOT, MVP, GTM, CONSTRAINTS)
    assert detail.duration_s >= before.duration_s and detail.created_at == before.created_at
    row = manager._store.get(run_id)
    assert row["state"] == "done" and row["result_status"] == "complete" and row["include_strategy"] == 1
    assert len(json.loads(row["stages_json"])) == 7


def test_a_failed_strategy_job_keeps_the_earlier_result(monkeypatch: pytest.MonkeyPatch, manager: RunManager) -> None:
    run_id = done_run(monkeypatch, manager)
    before = manager.get(run_id)
    use_fake_strategy(
        monkeypatch,
        swot=FakeStrategyAgent(STAGE_SWOT, error=LLMAPIError()),
        mvp=FakeStrategyAgent(STAGE_MVP, error=LLMAPIError()),
        gtm=FakeStrategyAgent(STAGE_GTM, error=LLMAPIError()),
    )
    detail = finished(manager, manager.start_strategy(run_id).id)

    assert detail.state == "done" and detail.message == MSG_PARTIAL and detail.result.status == "partial"
    assert [stage.status for stage in detail.stages[4:]] == ["failed"] * 3
    assert detail.stages[:4] == before.stages
    for name in ("idea", "search", "market", "competitors"):
        assert getattr(detail.result, name) == getattr(before.result, name)


def test_a_strategy_job_that_stops_unexpectedly_keeps_the_earlier_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args, **kwargs):
        raise RuntimeError("unexpected")

    manager = RunManager(store_in(tmp_path), strategy=broken)
    try:
        run_id = done_run(monkeypatch, manager)
        before = manager.get(run_id)
        detail = finished(manager, manager.start_strategy(run_id).id)
    finally:
        manager.shutdown()

    assert detail.state == "done" and detail.result.status == "partial"
    assert detail.result.market == before.result.market and detail.stages[:4] == before.stages
    assert [stage.status for stage in detail.stages[4:]] == ["skipped"] * 3


def test_a_cancelled_strategy_job_returns_the_run_to_done(monkeypatch: pytest.MonkeyPatch, manager: RunManager) -> None:
    run_id = done_run(monkeypatch, manager)
    gate, reached = threading.Event(), threading.Event()
    use_fake_strategy(monkeypatch, swot=gate_agent(STAGE_SWOT, gate, reached))
    manager.start_strategy(run_id)
    assert reached.wait(10)
    manager.cancel(run_id)
    gate.set()
    detail = finished(manager, run_id)

    assert detail.state == "done" and detail.result.status == "partial" and detail.result.swot == SWOT
    statuses = stage_statuses(detail)
    assert statuses[STAGE_MVP] == "cancelled" and statuses[STAGE_GTM] == "cancelled"
    assert next(s for s in detail.stages if s.key == STAGE_GTM).message == MSG_STAGE_CANCELLED


def test_a_strategy_job_on_a_run_with_strategy_resets_its_stages_in_place(
    monkeypatch: pytest.MonkeyPatch, manager: RunManager
) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch, swot=FakeStrategyAgent(STAGE_SWOT, error=LLMAPIError()))
    run_id = finished(manager, manager.start(PIPELINE_SUBMISSION, include_strategy=True).id).id
    use_fake_strategy(monkeypatch)
    detail = finished(manager, manager.start_strategy(run_id).id)

    assert [stage.key for stage in detail.stages] == list(SEVEN)
    assert detail.result.status == "complete" and detail.result.errors == [] and detail.result.swot == SWOT


def test_a_strategy_job_needs_a_saved_finished_run_with_an_analysis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = threading.Event()
    blocked = FakePipeline(block=gate)
    manager = manager_with(store_in(tmp_path), blocked)
    try:
        with pytest.raises(RunNotFoundError):
            manager.start_strategy("no-such-run")
        running = manager.start(PIPELINE_SUBMISSION).id
        assert blocked.reached.wait(10)
        with pytest.raises(RunNotFinishedError):
            manager.start_strategy(running)
        gate.set()
        no_analysis = finished(manager, running).id
        with pytest.raises(StrategyNotReadyError):
            manager.start_strategy(no_analysis)
    finally:
        gate.set()
        manager.shutdown()


def test_a_strategy_job_shares_the_run_limit_with_normal_runs(
    monkeypatch: pytest.MonkeyPatch, manager: RunManager
) -> None:
    first = done_run(monkeypatch, manager)
    second = done_run(monkeypatch, manager)
    gate, reached = threading.Event(), threading.Event()
    use_fake_strategy(monkeypatch, swot=gate_agent(STAGE_SWOT, gate, reached))
    use_full_pipeline(monkeypatch)

    def held_search(idea):
        gate.wait(10)
        return PIPELINE_SEARCH

    monkeypatch.setattr(orchestrator, "run_web_search", held_search)
    try:
        manager.start_strategy(first)
        assert reached.wait(10)
        other = manager.start(PIPELINE_SUBMISSION).id
        with pytest.raises(RunLimitError):
            manager.start(PIPELINE_SUBMISSION)
        with pytest.raises(RunLimitError):
            manager.start_strategy(second)
    finally:
        gate.set()
    assert finished(manager, first).state == "done"
    assert finished(manager, other).state == "done"

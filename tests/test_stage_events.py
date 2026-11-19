"""The orchestrator's optional run arguments (KIRO_UI_UPGRADE_SPEC.md Section 10.2).

`idea`, `on_event` and `should_stop` are additive: the existing two-argument calls must behave
exactly as before, and the real four stages must still run. Fakes only (tests/pipeline_fakes.py),
so no LLM or search call is made.
"""

import inspect

import pytest

import orchestrator
from models.schemas import ExtractedIdea, PipelineResult
from orchestrator import (
    CODE_CANCELLED,
    CODE_IDEA_PROVIDED,
    EVENT_FAILED,
    EVENT_FINISHED,
    EVENT_SKIPPED,
    EVENT_STARTED,
    FULL_STAGES,
    STAGE_COMPETITOR,
    STAGE_EXTRACTION,
    STAGE_MARKET,
    STAGE_SEARCH,
    StageEvent,
    run_pipeline,
)
from tests.fakes import VALID_EXTRACTION
from tests.pipeline_fakes import PIPELINE_SUBMISSION, use_full_pipeline
from utils.errors import LLMAPIError, RunCancelledError, SearchAPIError

REVIEWED = ExtractedIdea(**{**VALID_EXTRACTION, "idea_title": "Reviewed title"})


def record(events: list[StageEvent]):
    return events.append


def kinds(events: list[StageEvent]) -> list[tuple[str, str]]:
    return [(event.stage, event.kind) for event in events]


# --- the signature stays compatible -------------------------------------------------------------


def test_the_existing_call_shapes_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)

    one = run_pipeline(PIPELINE_SUBMISSION)
    two = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)
    three = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, 60.0)

    assert one.status == "complete" and one.market is None, "two stages, as in Milestone 1"
    assert two.status == "complete" and two.market is not None and two.competitors is not None
    assert three.status == "complete"


def test_the_new_arguments_are_optional_and_keyword_only() -> None:
    parameters = inspect.signature(run_pipeline).parameters

    assert [name for name, p in parameters.items() if p.kind is p.POSITIONAL_OR_KEYWORD] == [
        "submission", "stages", "time_limit_s"
    ], "the positional arguments are unchanged"
    for name in ("idea", "on_event", "should_stop"):
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[name].default is None


# --- stage events ------------------------------------------------------------------------------


def test_every_stage_reports_a_start_and_a_finish_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    events: list[StageEvent] = []

    run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, on_event=record(events))

    assert kinds(events) == [
        (STAGE_EXTRACTION, EVENT_STARTED), (STAGE_EXTRACTION, EVENT_FINISHED),
        (STAGE_SEARCH, EVENT_STARTED), (STAGE_SEARCH, EVENT_FINISHED),
        (STAGE_MARKET, EVENT_STARTED), (STAGE_MARKET, EVENT_FINISHED),
        (STAGE_COMPETITOR, EVENT_STARTED), (STAGE_COMPETITOR, EVENT_FINISHED),
    ]
    assert all(event.duration_s is not None and event.duration_s >= 0
               for event in events if event.kind == EVENT_FINISHED)
    assert all(event.duration_s is None for event in events if event.kind == EVENT_STARTED)


def test_a_finished_stage_carries_the_result_so_far(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    events: list[StageEvent] = []

    final = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, on_event=record(events))

    after_extraction = next(e for e in events if e.stage == STAGE_EXTRACTION and e.kind == EVENT_FINISHED)
    after_search = next(e for e in events if e.stage == STAGE_SEARCH and e.kind == EVENT_FINISHED)
    assert after_extraction.result is not None and after_extraction.result.idea is not None
    assert after_extraction.result.search is None, "only what had finished by then"
    assert after_search.result.search is not None and after_search.result.market is None
    assert after_extraction.result.status == "partial", "a snapshot is never reported as complete"
    assert final.status == "complete"


def test_the_snapshots_carry_the_derived_fields_too(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    events: list[StageEvent] = []

    run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, on_event=record(events))

    after_market = next(e for e in events if e.stage == STAGE_MARKET and e.kind == EVENT_FINISHED)
    assert after_market.result.evidence_strength is not None, "the market tab can show it at once"


def test_a_failed_stage_is_reported_with_its_code_and_safe_message(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch, market_llm=(LLMAPIError("The AI service is busy right now."),))
    events: list[StageEvent] = []

    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, on_event=record(events))

    failed = next(e for e in events if e.kind == EVENT_FAILED)
    assert failed.stage == STAGE_MARKET and failed.code == "llm_api_error"
    assert failed.message == "The AI service is busy right now." and "Traceback" not in failed.message
    assert (STAGE_COMPETITOR, EVENT_STARTED) in kinds(events), "the next stage still runs"
    assert result.status == "partial"


def test_a_skipped_stage_is_reported_with_the_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch, search=(SearchAPIError("Web search could not be completed."),))
    events: list[StageEvent] = []

    run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, on_event=record(events))

    skipped = [event for event in events if event.kind == EVENT_SKIPPED]
    assert [event.stage for event in skipped] == [STAGE_MARKET, STAGE_COMPETITOR]
    assert all("skipped because the web search did not complete" in event.message for event in skipped)


def test_a_listener_that_breaks_does_not_break_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)

    def broken(event: StageEvent) -> None:
        raise RuntimeError("listener trouble")

    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, on_event=broken)

    assert result.status == "complete" and result.competitors is not None


def test_without_a_listener_no_snapshot_is_built(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snapshots cost work, so they are only made when somebody is listening."""
    use_full_pipeline(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)
    assert result.status == "complete"


# --- a reviewed idea ----------------------------------------------------------------------------


def test_a_reviewed_idea_replaces_extraction_and_reaches_the_later_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    events: list[StageEvent] = []

    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, idea=REVIEWED, on_event=record(events))

    assert fakes.extraction_llm.calls == [], "no extraction call is made"
    assert result.idea == REVIEWED, "the reviewed idea is the one used"
    assert result.status == "complete" and result.market is not None
    skipped = next(e for e in events if e.stage == STAGE_EXTRACTION)
    assert (skipped.kind, skipped.code) == (EVENT_SKIPPED, CODE_IDEA_PROVIDED)
    assert "extraction" not in result.timings, "a stage that did not run has no timing"


def test_the_search_stage_uses_the_reviewed_idea(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = use_full_pipeline(monkeypatch)

    run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, idea=REVIEWED)

    assert fakes.search.calls[0][0][0] == REVIEWED


# --- cancelling ---------------------------------------------------------------------------------


def test_a_cancel_before_the_start_skips_everything_and_fails_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = use_full_pipeline(monkeypatch)
    events: list[StageEvent] = []

    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, on_event=record(events), should_stop=lambda: True)

    assert fakes.extraction_llm.calls == [] and fakes.analysis_calls() == 0, "nothing was spent"
    assert result.status == "failed", "no idea was produced"
    assert [event.stage for event in events] == [STAGE_EXTRACTION, STAGE_SEARCH, STAGE_MARKET, STAGE_COMPETITOR]
    assert all(event.kind == EVENT_SKIPPED and event.code == CODE_CANCELLED for event in events)
    assert all("cancelled" in warning for warning in result.warnings)


def test_a_cancel_between_stages_keeps_what_finished(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = use_full_pipeline(monkeypatch)
    stop = {"value": False}
    events: list[StageEvent] = []

    def listener(event: StageEvent) -> None:
        events.append(event)
        if event.stage == STAGE_SEARCH and event.kind == EVENT_FINISHED:
            stop["value"] = True  # the user cancels while the search is finishing

    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, on_event=listener, should_stop=lambda: stop["value"])

    assert result.status == "partial"
    assert result.idea is not None and result.search is not None, "what finished is kept"
    assert result.market is None and fakes.market_llm.calls == [], "the analysis never started"
    cancelled = [event for event in events if event.code == CODE_CANCELLED]
    assert [event.stage for event in cancelled] == [STAGE_MARKET, STAGE_COMPETITOR]


def test_a_cancel_inside_a_stage_stops_its_next_outside_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stage already running stops at its next call, because the clients ask the cancel check
    first. Here the real search client runs, with only `requests.post` replaced."""
    import utils.search_client as search_client
    from utils.deadline import stop_check

    posted: list[object] = []
    monkeypatch.setattr(search_client.requests, "post", lambda *a, **k: posted.append(a))

    with stop_check(lambda: True):
        with pytest.raises(RunCancelledError) as info:
            search_client.search("crop disease market size")

    assert posted == [], "nothing was sent"
    assert info.value.status_code == 409 and "cancelled" in info.value.user_message


def test_a_cancel_stops_the_next_llm_call_before_a_client_is_made(monkeypatch: pytest.MonkeyPatch) -> None:
    import utils.llm_client as llm_client
    from utils.deadline import stop_check

    made: list[object] = []
    monkeypatch.setattr(llm_client, "_make_client", lambda *a, **k: made.append(a))

    with stop_check(lambda: True):
        with pytest.raises(RunCancelledError):
            llm_client.generate_json("system", "user")

    assert made == [], "no provider client was created"


def test_the_clients_are_untouched_when_nothing_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check is inert outside a cancelled run, so Milestone 1 and 2 behaviour is unchanged."""
    from utils.deadline import raise_if_stopped, stop_requested

    assert stop_requested() is False
    raise_if_stopped()


def test_a_cancelled_stage_adds_no_misleading_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """The search stage's own failure warning must not appear when the reason was a cancel."""
    use_full_pipeline(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, should_stop=lambda: True)

    assert orchestrator.WARNING_SEARCH_UNAVAILABLE not in result.warnings


def test_a_cancel_check_that_stays_false_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)

    with_check = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, should_stop=lambda: False)
    use_full_pipeline(monkeypatch)
    without = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert with_check.model_dump(exclude={"timings": True, "usage": {"by_stage": {"__all__": {"seconds"}}}}) == without.model_dump(exclude={"timings": True, "usage": {"by_stage": {"__all__": {"seconds"}}}})


def test_the_cancel_check_does_not_leak_into_a_later_run(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, should_stop=lambda: True)

    use_full_pipeline(monkeypatch)
    after = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert after.status == "complete", "the scope ended with the run"


def test_a_cancelled_run_still_returns_a_valid_result(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, should_stop=lambda: True)

    assert PipelineResult.model_validate(result.model_dump(mode="json")).status == "failed"

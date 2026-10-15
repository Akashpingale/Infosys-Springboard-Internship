import pytest

import orchestrator
from agents.base import Agent, AgentContext
from models.schemas import (
    ExtractedIdea,
    IdeaSubmission,
    PipelineResult,
    SearchBundle,
    SearchSection,
)
from tests.fakes import VALID_EXTRACTION, make_sequence
from utils.errors import AppError, LLMConfigError, SearchAPIError, SearchConfigError

SUBMISSION = IdeaSubmission(
    idea_description="An AI app that detects crop diseases from phone photos for small farmers.",
    industry="Agriculture / AgriTech",
    target_customers="Small farmers in India",
)
IDEA = ExtractedIdea(**VALID_EXTRACTION)


def bundle(queries_failed: int = 0, sections: int = 4, results: int = 3) -> SearchBundle:
    return SearchBundle(
        sections=[
            SearchSection(label=f"Section {i}", query=f"query {i}") for i in range(1, sections + 1)
        ],
        total_results=results,
        queries_failed=queries_failed,
    )


def use_fakes(
    monkeypatch: pytest.MonkeyPatch, extraction: object = IDEA, search: object = None
) -> tuple:
    """Replace the two stage functions with fakes. Exceptions are raised, values returned."""
    fake_extract = make_sequence(extraction)
    fake_search = make_sequence(bundle() if search is None else search)
    monkeypatch.setattr(orchestrator, "extract_idea", fake_extract)
    monkeypatch.setattr(orchestrator, "run_web_search", fake_search)
    return fake_extract, fake_search


# --- the contract in agents/base.py -----------------------------------------


def test_agent_context_defaults() -> None:
    context = AgentContext(submission=SUBMISSION)
    assert context.idea is None and context.search is None and context.warnings == []


def test_both_stages_satisfy_the_agent_protocol() -> None:
    for stage in orchestrator.STAGES:
        assert isinstance(stage, Agent)
        assert isinstance(stage.name, str) and stage.name


def test_default_stage_order() -> None:
    assert [stage.name for stage in orchestrator.STAGES] == ["extraction", "search"]


# --- complete run ------------------------------------------------------------


def test_complete_run_returns_idea_and_search(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fakes(monkeypatch)
    result = run = orchestrator.run_pipeline(SUBMISSION)

    assert isinstance(result, PipelineResult)
    assert run.status == "complete"
    assert run.idea == IDEA
    assert run.search is not None and run.search.total_results == 3
    assert run.errors == [] and run.warnings == []


def test_the_same_idea_object_is_passed_to_the_search_stage(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    _, fake_search = use_fakes(monkeypatch)
    result = orchestrator.run_pipeline(SUBMISSION)
    (received_idea,), _ = fake_search.calls[0]
    assert received_idea is IDEA
    assert result.idea is IDEA


def test_the_submission_reaches_the_extraction_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_extract, _ = use_fakes(monkeypatch)
    orchestrator.run_pipeline(SUBMISSION)
    (received,), _ = fake_extract.calls[0]
    assert received is SUBMISSION


def test_timings_recorded_for_every_stage_that_ran(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fakes(monkeypatch)
    timings = orchestrator.run_pipeline(SUBMISSION).timings
    assert set(timings) == {"extraction", "search", "total"}
    assert all(value >= 0 for value in timings.values())
    assert timings["total"] >= max(timings["extraction"], timings["search"])


# --- failed: extraction ------------------------------------------------------


def test_extraction_failure_gives_failed_and_skips_the_search(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    _, fake_search = use_fakes(monkeypatch, extraction=LLMConfigError())
    run = orchestrator.run_pipeline(SUBMISSION)

    assert run.status == "failed"
    assert run.idea is None and run.search is None
    assert len(run.errors) == 1
    assert run.errors[0].stage == "extraction"
    assert run.errors[0].code == "llm_not_configured"
    assert run.errors[0].message == "The AI service is not configured."
    assert fake_search.calls == []
    assert set(run.timings) == {"extraction", "total"}
    assert run.warnings == []


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (LLMConfigError(), "llm_not_configured"),
        (SearchConfigError(), "search_not_configured"),
    ],
)
def test_any_app_error_in_the_first_stage_is_recorded(
    monkeypatch: pytest.MonkeyPatch, error: AppError, code: str
) -> None:
    use_fakes(monkeypatch, extraction=error)
    run = orchestrator.run_pipeline(SUBMISSION)
    assert run.status == "failed" and run.errors[0].code == code


# --- partial: search ---------------------------------------------------------


def test_search_failure_gives_partial_with_the_idea_and_a_warning(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fakes(monkeypatch, search=SearchAPIError("Web search could not be completed."))
    run = orchestrator.run_pipeline(SUBMISSION)

    assert run.status == "partial"
    assert run.idea == IDEA
    assert run.search is None
    assert run.warnings == [orchestrator.WARNING_SEARCH_UNAVAILABLE]
    assert run.errors[0].stage == "search"
    assert run.errors[0].code == "search_api_error"
    assert set(run.timings) == {"extraction", "search", "total"}


def test_partly_failed_search_gives_partial_without_an_error_entry(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fakes(monkeypatch, search=bundle(queries_failed=1))
    run = orchestrator.run_pipeline(SUBMISSION)

    assert run.status == "partial"
    assert run.errors == []
    assert run.search is not None and run.search.queries_failed == 1
    assert run.warnings == ["1 of 4 web searches failed, so some sections are empty."]


def test_all_queries_failed_inside_the_bundle_is_still_partial(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fakes(monkeypatch, search=bundle(queries_failed=4, results=0))
    run = orchestrator.run_pipeline(SUBMISSION)
    assert run.status == "partial" and run.errors == []


# --- extensibility -----------------------------------------------------------


class DummyStage:
    """A future agent. Existing stages do not change to accommodate it."""

    name = "dummy"

    def __init__(self) -> None:
        self.seen: AgentContext | None = None

    def run(self, context: AgentContext) -> AgentContext:
        self.seen = context
        context.warnings.append("dummy ran")
        return context


def test_a_third_stage_runs_without_changing_the_existing_ones(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fakes(monkeypatch)
    dummy = DummyStage()
    run = orchestrator.run_pipeline(SUBMISSION, stages=[*orchestrator.STAGES, dummy])

    assert run.status == "complete"
    assert "dummy" in run.timings
    assert dummy.seen is not None
    assert dummy.seen.idea is IDEA
    assert dummy.seen.search is not None
    assert run.warnings == ["dummy ran"]


def test_a_failing_third_stage_leaves_earlier_output_in_place(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fakes(monkeypatch)

    class FailingStage:
        name = "failing"

        def run(self, context: AgentContext) -> AgentContext:
            raise SearchAPIError("later stage broke")

    run = orchestrator.run_pipeline(SUBMISSION, stages=[*orchestrator.STAGES, FailingStage()])
    assert run.status == "partial"
    assert run.idea is IDEA and run.search is not None
    assert run.errors[0].stage == "failing"


def test_unexpected_exceptions_are_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fakes(monkeypatch, extraction=RuntimeError("provider internals"))
    with pytest.raises(RuntimeError):
        orchestrator.run_pipeline(SUBMISSION)


def test_result_is_json_serialisable(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fakes(monkeypatch)
    run = orchestrator.run_pipeline(SUBMISSION)
    assert PipelineResult.model_validate_json(run.model_dump_json()) == run

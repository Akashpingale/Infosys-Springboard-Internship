import io
import json
import sys
from pathlib import Path

import pytest

from agents import advisor_agent, swot_risk_agent, web_search_agent
from agents.advisor_agent import MSG_MISSING_STRATEGY, MSG_OUT_OF_SCOPE
from config import get_settings
from models.schemas import PipelineResult, StageError
from orchestrator import EVENT_STARTED, STAGE_GTM, STAGE_MVP, STAGE_SWOT, STRATEGY_STAGES, StageEvent, run_pipeline
from scripts import check_advisor_live, check_m3_contracts, run_m3_live, run_m3_retro_live
from tests import m3_live_fakes
from tests.fakes import make_sequence, tavily_ok
from tests.m3_fakes import CONSTRAINTS, full_result, gemini_rate_limit, use_capturing_providers
from tests.pipeline_fakes import PIPELINE_SUBMISSION
from utils import search_client
from utils.errors import ChatUnavailableError, LLMAPIError, StrategyAlreadyCompleteError, StrategyNotReadyError
from utils.run_manager import STRATEGY_ONLY_KEYS, STRATEGY_STAGE_KEYS, run_time_limit_s, strategy_time_limit_s

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "docs" / "test_runs_m3" / "README.md"
IDEAS = ["agritech", "fintech_cashflow", "foodtech_surplus"]
INDUSTRIES = ["Agriculture / AgriTech", "Finance / FinTech", "Food & Beverage"]
SCRIPTS = [run_m3_live, run_m3_retro_live, check_advisor_live]
NO_CALLS = {"llm": 0, "groq": 0, "searches": 0}
ONE_LLM_CALL = {"llm": 1, "groq": 0, "searches": 0}
FULL_RUN_LLM_CALLS = {
    "extraction": 1,
    "search": 0,
    "market_opportunity": 1,
    "competitor_analysis": 2,
    STAGE_SWOT: 1,
    STAGE_MVP: 1,
    STAGE_GTM: 1,
}
BUSY = "The AI service is busy right now. Please try again in a minute."


def script_name(module) -> str:
    return module.__name__.rsplit(".", 1)[-1]


def configured_keys() -> list[str]:
    settings = get_settings()
    return [value for value in (settings.llm_api_key, settings.tavily_api_key) if value]


def model() -> str:
    return get_settings().llm_model


def keeps_secrets(text: str, keys: list[str] | None = None) -> bool:
    return all(key not in text for key in (configured_keys() if keys is None else keys))


def seven_stage_result() -> PipelineResult:
    with m3_live_fakes.fake_clients(analysis=True, strategy=True):
        return run_pipeline(PIPELINE_SUBMISSION, STRATEGY_STAGES)


def analysis_result() -> PipelineResult:
    with pytest.MonkeyPatch.context() as patch:
        result, _ = full_result(patch)
    return result


def saved_run(folder: Path, result: PipelineResult, name: str = "agritech") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def every_file(folder: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(folder.iterdir()))


def spy_pipeline(monkeypatch: pytest.MonkeyPatch, module, *outcomes: object) -> list:
    calls: list = []

    def pipeline(submission, **kwargs):
        calls.append((submission, kwargs))
        outcome = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(module, "strategy_pipeline", pipeline)
    return calls


@pytest.fixture
def nothing_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        pytest.fail("a run or a question was attempted")

    monkeypatch.setattr(run_m3_live, "strategy_pipeline", fail)
    monkeypatch.setattr(run_m3_retro_live, "strategy_pipeline", fail)
    monkeypatch.setattr(advisor_agent, "answer", fail)


@pytest.mark.parametrize("script", SCRIPTS, ids=script_name)
def test_without_yes_or_fake_nothing_runs_and_no_file_is_written(script, nothing_runs, tmp_path: Path, capsys) -> None:
    out = tmp_path / "out"

    assert script.main(["--out", str(out)]) == 1

    assert not out.exists()
    printed = capsys.readouterr().out
    assert f"python scripts/{script_name(script)}.py --yes" in printed
    assert f"python scripts/{script_name(script)}.py --fake" in printed
    assert run_m3_live.MSG_NO_FILES in printed


@pytest.mark.parametrize("script", SCRIPTS, ids=script_name)
def test_yes_and_fake_cannot_be_combined(script, nothing_runs, tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        script.main(["--yes", "--fake", "--out", str(tmp_path / "out")])
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    ("script", "missing"),
    [
        (run_m3_live, "LLM_API_KEY"),
        (run_m3_live, "LLM_MODEL"),
        (run_m3_live, "TAVILY_API_KEY"),
        (run_m3_retro_live, "LLM_API_KEY"),
        (run_m3_retro_live, "LLM_MODEL"),
        (check_advisor_live, "LLM_API_KEY"),
        (check_advisor_live, "LLM_MODEL"),
    ],
)
def test_a_missing_key_is_named_and_nothing_is_written(
    script, missing: str, nothing_runs, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    keys, name = configured_keys(), model()
    monkeypatch.delenv(missing)
    out = tmp_path / "out"

    assert script.main(["--yes", "--out", str(out)]) == 1

    assert not out.exists()
    printed = capsys.readouterr().out
    assert f"Missing: {missing}" in printed and run_m3_live.MSG_NO_FILES in printed
    assert keeps_secrets(printed, keys) and name not in printed


def test_the_fake_run_writes_valid_files_for_the_three_ideas(tmp_path: Path, capsys) -> None:
    out = tmp_path / "out"

    assert run_m3_live.main(["--fake", "--out", str(out)]) == 0

    summary = read_json(out / run_m3_live.SUMMARY_NAME)
    assert (summary["fake"], summary["model"], summary["ideas_attempted"], summary["ideas_executed"]) == (True, "fake", 3, 3)
    assert [run["idea"] for run in summary["runs"]] == IDEAS
    assert [run["industry"] for run in summary["runs"]] == INDUSTRIES
    paths = [out / f"{name}.json" for name in IDEAS]
    for run, path in zip(summary["runs"], paths):
        result = PipelineResult.model_validate_json(path.read_text(encoding="utf-8"))
        assert result.status == run["status"] == "complete"
        assert set(run["seconds"]) == {*STRATEGY_STAGE_KEYS, "total"}
        assert run["seconds"] == {key: result.timings[key] for key in run["seconds"]}
        assert run["strategy_seconds"] == round(sum(result.timings[key] for key in STRATEGY_ONLY_KEYS), 3)
        assert {key: run["calls"][key]["llm"] for key in STRATEGY_STAGE_KEYS} == FULL_RUN_LLM_CALLS
        assert run["calls"]["total"] == {"llm": 7, "groq": 0, "searches": 0}
        assert run["warnings"] == result.warnings and run["errors"] == []
        assert run["contract_violations"] == []
        swot, mvp, gtm = run["counts"]["swot"], run["counts"]["mvp"], run["counts"]["gtm"]
        assert [swot[name] for name in ("strengths", "weaknesses", "opportunities", "threats", "risks")] == [
            len(result.swot.strengths), len(result.swot.weaknesses), len(result.swot.opportunities),
            len(result.swot.threats), len(result.swot.risks),
        ]
        assert swot["risks_by_category"] == result.swot.risk_category_coverage
        assert swot["coverage_gaps"] == result.swot.coverage_gaps
        assert mvp["in_scope"] == [feature.name for feature in result.mvp.features if feature.tier == "mvp"]
        assert mvp["deferred"] == [feature.name for feature in result.mvp.features if feature.tier == "later"]
        assert mvp["constraints_assumed"] == result.mvp.quality.constraints_assumed != []
        assert gtm["channels"] == [channel.name for channel in result.gtm.channels]
        assert gtm["start_here"] == result.gtm.channels[0].name
    assert check_m3_contracts.main([str(path) for path in paths]) == 0
    for name in IDEAS:
        text = (out / f"{name}.md").read_text(encoding="utf-8")
        assert text.startswith(f"# Milestone 3 run: {name}\n\n{run_m3_live.MSG_FAKE_RUN}\n")
        assert "## Seconds and calls per stage" in text and "| Total |" in text
        assert run_m3_live.MSG_NO_VIOLATIONS in text
        assert "- [ ] 4. The MVP list contains the founder's own features" in text
        assert "- [ ] 8. Timing:" in text and "- [ ] 7." not in text
        assert "## Startup idea validation report" in text and "### SWOT" in text
    printed = capsys.readouterr().out
    assert printed.count("Review checklist for ") == 3
    assert keeps_secrets(printed + every_file(out))
    assert model() not in printed


def test_a_fake_run_without_out_writes_to_a_new_temporary_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run_m3_live.tempfile, "tempdir", str(tmp_path))
    before = sorted(run_m3_live.OUTPUT_DIR.iterdir())

    assert run_m3_live.main(["--fake"]) == 0

    created = [path for path in tmp_path.iterdir() if path.name.startswith(run_m3_live.FAKE_DIR_PREFIX)]
    assert len(created) == 1
    assert sorted(path.name for path in created[0].iterdir()) == sorted(
        [*(f"{name}.json" for name in IDEAS), *(f"{name}.md" for name in IDEAS), run_m3_live.SUMMARY_NAME]
    )
    assert sorted(run_m3_live.OUTPUT_DIR.iterdir()) == before


def test_a_live_run_calls_the_seven_stages_as_the_run_manager_does(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    calls = spy_pipeline(monkeypatch, run_m3_live, seven_stage_result())
    out = tmp_path / "out"

    assert run_m3_live.main(["--yes", "--out", str(out)]) == 0

    assert [submission.industry for submission, _ in calls] == INDUSTRIES
    for _, kwargs in calls:
        assert (kwargs["idea"], kwargs["prior"], kwargs["constraints"]) == (None, None, None)
        assert kwargs["time_limit_s"] == run_time_limit_s()
        assert kwargs["strategy_time_limit_s"] == strategy_time_limit_s()
        assert kwargs["should_stop"]() is False
    summary = read_json(out / run_m3_live.SUMMARY_NAME)
    assert (summary["fake"], summary["model"], summary["ideas_executed"]) == (False, model(), 3)
    assert all(run["calls"]["total"] == NO_CALLS for run in summary["runs"])
    printed = capsys.readouterr().out
    assert run_m3_live.MSG_LIVE_RUN in printed
    assert model() not in printed and keeps_secrets(printed)
    assert keeps_secrets(every_file(out))


def test_a_partial_run_is_recorded_as_it_happened(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    error = StageError(stage=STAGE_GTM, code="llm_api_error", message=BUSY)
    partial = seven_stage_result().model_copy(update={"status": "partial", "gtm": None, "errors": [error]})
    spy_pipeline(monkeypatch, run_m3_live, partial)
    out = tmp_path / "out"

    assert run_m3_live.main(["--yes", "--out", str(out)]) == 0

    entry = read_json(out / run_m3_live.SUMMARY_NAME)["runs"][0]
    assert entry["status"] == "partial"
    assert entry["counts"]["gtm"] is None and entry["counts"]["mvp"] is not None
    assert entry["errors"] == [{"stage": STAGE_GTM, "code": "llm_api_error", "message": BUSY}]
    text = (out / "agritech.md").read_text(encoding="utf-8")
    assert "Status: partial" in text and "- [ ] 6. Channels are plausible" in text
    assert "Measured: start here" not in text


def test_an_unexpected_error_is_recorded_without_a_result_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spy_pipeline(monkeypatch, run_m3_live, RuntimeError("provider internals"))
    out = tmp_path / "out"

    assert run_m3_live.main(["--yes", "--out", str(out)]) == 1

    summary = read_json(out / run_m3_live.SUMMARY_NAME)
    assert summary["ideas_executed"] == 0
    assert [run["reason"] for run in summary["runs"]] == ["unexpected error (RuntimeError)"] * 3
    assert sorted(path.name for path in out.iterdir()) == [run_m3_live.SUMMARY_NAME]
    assert "provider internals" not in json.dumps(summary)


def test_the_meter_counts_each_search_request_in_its_stage_and_restores_the_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_client.requests, "post", make_sequence(tavily_ok()))
    original = web_search_agent.search
    meter = run_m3_live.Meter()

    with run_m3_live.metered(meter):
        meter.on_event(StageEvent("search", EVENT_STARTED))
        web_search_agent.run_queries([("First", "first query"), ("Second", "second query")])
        meter.on_event(StageEvent("market_opportunity", EVENT_STARTED))
        web_search_agent.run_queries([("Third", "third query")])

    assert meter.of("search") == {"llm": 0, "groq": 0, "searches": 2}
    assert meter.of("market_opportunity") == {"llm": 0, "groq": 0, "searches": 1}
    assert meter.total() == {"llm": 0, "groq": 0, "searches": 3}
    assert web_search_agent.search is original


def test_printing_a_character_the_console_cannot_show_does_not_stop_a_run(monkeypatch: pytest.MonkeyPatch) -> None:
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\n")
    monkeypatch.setattr(sys, "stdout", console)

    run_m3_live.say("Budget \u20b9 5,000 for \u0915\u093f\u0938\u093e\u0928 field days")

    console.flush()
    assert console.buffer.getvalue() == b"Budget ? 5,000 for ????? field days\n"


def test_the_meter_counts_a_groq_takeover_in_the_stage_that_made_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    _, groq = use_capturing_providers(monkeypatch, gemini_rate_limit(), groq_content='{"ok": true}')
    original = swot_risk_agent.generate_json
    meter = run_m3_live.Meter()

    with run_m3_live.metered(meter):
        meter.on_event(StageEvent(STAGE_SWOT, EVENT_STARTED))
        reply = swot_risk_agent.generate_json("system", "user")

    assert reply == '{"ok": true}' and len(groq.bodies) == 1
    assert meter.of(STAGE_SWOT) == {"llm": 1, "groq": 1, "searches": 0}
    assert swot_risk_agent.generate_json is original


def test_the_fake_retro_run_adds_the_strategy_to_a_saved_run_without_a_search(tmp_path: Path, capsys) -> None:
    prior = analysis_result()
    saved = saved_run(tmp_path / "saved", prior)
    out = tmp_path / "out"
    out.mkdir()
    (out / run_m3_live.SUMMARY_NAME).write_text(
        json.dumps({"runs": [{"idea": "agritech", "executed": True, "strategy_seconds": 63.5}]}), encoding="utf-8"
    )

    assert run_m3_retro_live.main(["--fake", "--saved", str(saved), "--out", str(out)]) == 0

    result = PipelineResult.model_validate_json((out / "retro_agritech.json").read_text(encoding="utf-8"))
    assert result.status == "complete"
    assert None not in (result.swot, result.mvp, result.gtm)
    assert (result.idea, result.search, result.market, result.competitors) == (
        prior.idea, prior.search, prior.market, prior.competitors
    )
    summary = read_json(out / run_m3_retro_live.RETRO_SUMMARY_NAME)
    assert (summary["executed"], summary["fake"], summary["saved"], summary["idea"]) == (True, True, "agritech.json", "agritech")
    assert summary["stages_run"] == list(STRATEGY_ONLY_KEYS)
    assert {key: summary["calls"][key] for key in STRATEGY_ONLY_KEYS} == {key: ONE_LLM_CALL for key in STRATEGY_ONLY_KEYS}
    assert summary["calls"]["total"] == {"llm": 3, "groq": 0, "searches": 0}
    assert summary["full_run_strategy_seconds"] == 63.5
    assert summary["seconds"]["total"] == round(result.timings["total"] - prior.timings["total"], 3)
    assert summary["status"] == "complete" and summary["contract_violations"] == []
    assert check_m3_contracts.main([str(out / "retro_agritech.json")]) == 0
    text = (out / "retro_agritech.md").read_text(encoding="utf-8")
    assert run_m3_retro_live.MSG_NO_SEARCH.format(searches=0) in text
    assert run_m3_retro_live.MSG_FULL_RUN.format(seconds="63.5 s") in text
    assert "; the strategy part of the L-1 run of this idea took 63.5 s." in text
    printed = capsys.readouterr().out
    assert "Review checklist for the strategy on agritech.json" in printed
    assert keeps_secrets(printed + every_file(out))


def test_the_retro_job_runs_the_missing_stages_as_the_strategy_route_does(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TAVILY_API_KEY")
    full = seven_stage_result()
    prior = full.model_copy(update={"mvp": None, "gtm": None, "constraints": CONSTRAINTS})
    calls = spy_pipeline(monkeypatch, run_m3_retro_live, full)
    saved = saved_run(tmp_path / "saved", prior)
    out = tmp_path / "out"

    assert run_m3_retro_live.main(["--yes", "--saved", str(saved), "--out", str(out)]) == 0

    [(submission, kwargs)] = calls
    assert submission.industry == INDUSTRIES[0]
    assert kwargs["prior"] == prior and kwargs["rerun"] == (STAGE_MVP, STAGE_GTM)
    assert kwargs["constraints"] == CONSTRAINTS and kwargs["idea"] is None
    assert kwargs["time_limit_s"] == strategy_time_limit_s() and kwargs["strategy_time_limit_s"] is None
    summary = read_json(out / run_m3_retro_live.RETRO_SUMMARY_NAME)
    assert (summary["fake"], summary["model"], summary["stages_run"]) == (False, model(), [STAGE_MVP, STAGE_GTM])
    assert summary["full_run_strategy_seconds"] is None
    assert run_m3_retro_live.MSG_NO_FULL_RUN in (out / "retro_agritech.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({}, StrategyAlreadyCompleteError.default_message),
        ({"market": None, "competitors": None, "swot": None, "mvp": None, "gtm": None}, StrategyNotReadyError.default_message),
        ({"idea": None, "swot": None}, StrategyNotReadyError.default_message),
    ],
    ids=["strategy complete", "no analysis", "no idea"],
)
def test_a_saved_run_the_strategy_job_would_refuse_is_left_alone(
    change: dict, message: str, nothing_runs, tmp_path: Path, capsys
) -> None:
    saved = saved_run(tmp_path / "saved", seven_stage_result().model_copy(update=change))
    out = tmp_path / "out"

    assert run_m3_retro_live.main(["--fake", "--saved", str(saved), "--out", str(out)]) == 1

    assert not out.exists()
    assert message in capsys.readouterr().out


@pytest.mark.parametrize("script", [run_m3_retro_live, check_advisor_live], ids=script_name)
@pytest.mark.parametrize(
    "content", [None, "{ not json", '{"status": "complete", "timings": "none"}'], ids=["absent", "not json", "not a result"]
)
def test_an_unreadable_saved_run_is_reported_and_nothing_is_written(
    script, content: str | None, nothing_runs, tmp_path: Path, capsys
) -> None:
    saved = tmp_path / "saved" / "agritech.json"
    if content is not None:
        saved.parent.mkdir()
        saved.write_text(content, encoding="utf-8")
    out = tmp_path / "out"

    assert script.main(["--fake", "--saved", str(saved), "--out", str(out)]) == 1

    assert not out.exists()
    printed = capsys.readouterr().out
    assert "agritech.json could not be read" in printed and run_m3_live.MSG_NO_FILES in printed


def test_a_saved_run_without_an_idea_file_is_refused(nothing_runs, tmp_path: Path, capsys) -> None:
    saved = saved_run(tmp_path / "saved", analysis_result(), name="unknown_idea")

    assert run_m3_retro_live.main(["--fake", "--saved", str(saved), "--out", str(tmp_path / "out")]) == 1

    assert not (tmp_path / "out").exists()
    assert "data/test_ideas/unknown_idea.json" in capsys.readouterr().out


def test_the_fake_advisor_check_asks_the_eight_fixed_questions(tmp_path: Path, capsys) -> None:
    saved = saved_run(tmp_path / "saved", seven_stage_result())
    out = tmp_path / "out"

    assert check_advisor_live.main(["--fake", "--saved", str(saved), "--out", str(out)]) == 0

    data = read_json(out / "advisor_agritech.json")
    answers = data["questions"]
    assert [entry["question"] for entry in answers] == [question for _, question, _, _ in check_advisor_live.QUESTIONS]
    assert [entry["status"] for entry in answers] == ["ok"] * 5 + ["out_of_scope", "out_of_scope", "no_evidence"]
    assert [entry["calls"] for entry in answers] == [ONE_LLM_CALL] * 7 + [NO_CALLS]
    assert all(entry["error"] is None for entry in answers)
    assert [entry["cited_sections"] for entry in answers[:5]] == [["market"], ["competitors"], ["risks"], ["mvp"], ["gtm"]]
    assert [entry["asked_on"] for entry in answers] == (
        [check_advisor_live.ON_SAVED] * 7 + [check_advisor_live.ON_WITHOUT_STRATEGY]
    )
    assert answers[5]["paragraphs"][0]["text"] == MSG_OUT_OF_SCOPE
    assert answers[7]["paragraphs"][0]["text"] == MSG_MISSING_STRATEGY.format(names="MVP feature plan")
    assert (data["fake"], data["model"], data["saved"]) == (True, "fake", "agritech.json")
    assert data["calls"] == {"llm": 7, "groq": 0, "searches": 0}
    text = (out / "advisor_agritech.md").read_text(encoding="utf-8")
    assert text.startswith(f"# Advisor question set: agritech\n\n{run_m3_live.MSG_FAKE_RUN}\n")
    assert text.count("- Question: ") == 8 and "- [ ] 7. Advisor answers cite results" in text
    printed = capsys.readouterr().out
    assert "Review checklist for the Advisor on agritech.json" in printed
    assert keeps_secrets(printed + every_file(out))


def test_a_failed_question_is_recorded_and_the_others_are_still_asked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    answer = m3_live_fakes.advisor_reply

    def busy_on_competitors(system: str, user: str) -> str:
        if "closest to my idea" in user:
            raise LLMAPIError(BUSY)
        return answer(system, user)

    monkeypatch.setattr(m3_live_fakes, "advisor_reply", busy_on_competitors)
    saved = saved_run(tmp_path / "saved", seven_stage_result())
    out = tmp_path / "out"

    assert check_advisor_live.main(["--fake", "--saved", str(saved), "--out", str(out)]) == 1

    answers = read_json(out / "advisor_agritech.json")["questions"]
    assert answers[1]["error"] == {"code": "llm_api_error", "message": BUSY} and answers[1]["calls"] == ONE_LLM_CALL
    assert [entry["status"] for index, entry in enumerate(answers) if index != 1] == ["ok"] * 4 + [
        "out_of_scope", "out_of_scope", "no_evidence"
    ]
    assert f"2. competitor         ERROR llm_api_error: {BUSY}" in capsys.readouterr().out


def test_the_advisor_check_needs_a_finished_result(nothing_runs, tmp_path: Path, capsys) -> None:
    saved = saved_run(tmp_path / "saved", seven_stage_result().model_copy(update={"status": "failed"}))
    out = tmp_path / "out"

    assert check_advisor_live.main(["--fake", "--saved", str(saved), "--out", str(out)]) == 1

    assert not out.exists()
    assert ChatUnavailableError.default_message in capsys.readouterr().out


def test_the_advisor_check_uses_the_l1_agritech_result_by_default(nothing_runs, capsys) -> None:
    assert check_advisor_live.SAVED_RUN == run_m3_live.OUTPUT_DIR / "agritech.json"
    assert run_m3_retro_live.SAVED_RUN == ROOT / "docs" / "test_runs_m2" / "agritech.json"
    if not check_advisor_live.SAVED_RUN.exists():
        assert check_advisor_live.main(["--fake"]) == 1
        assert "Run scripts/run_m3_live.py first" in capsys.readouterr().out


def test_the_readme_explains_every_file_and_every_fixed_question() -> None:
    text = README.read_text(encoding="utf-8")
    names = [
        *(f"{name}.json" for name in IDEAS),
        *(f"{name}.md" for name in IDEAS),
        run_m3_live.SUMMARY_NAME,
        f"{run_m3_retro_live.RETRO_PREFIX}agritech.json",
        f"{run_m3_retro_live.RETRO_PREFIX}agritech.md",
        run_m3_retro_live.RETRO_SUMMARY_NAME,
        f"{check_advisor_live.ADVISOR_PREFIX}agritech.json",
        f"{check_advisor_live.ADVISOR_PREFIX}agritech.md",
    ]
    assert [name for name in names if f"`{name}`" not in text] == []
    assert [name for name in SCRIPTS if f"python scripts/{script_name(name)}.py --yes" not in text] == []
    assert [question for _, question, _, _ in check_advisor_live.QUESTIONS if f'"{question}"' not in text] == []
    if not (README.parent / run_m3_live.SUMMARY_NAME).exists():
        assert "**Status: not executed.**" in text

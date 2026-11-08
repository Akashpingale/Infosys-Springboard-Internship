"""The Task 4 live runner and report refresher (KIRO_PROMPT_M2.md Sections 10.3 and 10.4).

The runner is never executed against a real API here. Every test either stops it before it would
call anything, or replaces the pipeline with a fake, so no credit can be spent. The point of
these tests is the safety behaviour the specification asks for: `--yes` before any call, missing
keys named but never shown, no misleading file left behind, and a summary that records what
actually happened.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import make_m2_report  # noqa: E402
import run_live_m2  # noqa: E402

from models.schemas import PipelineResult, StageError  # noqa: E402
from tests.domain_fakes import DOMAINS  # noqa: E402

SECRETS = ("test-llm-key", "test-tavily-key")


@pytest.fixture
def output_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point both scripts at a temporary directory, so the real docs are never touched."""
    directory = tmp_path / "test_runs_m2"
    monkeypatch.setattr(run_live_m2, "OUTPUT_DIR", directory)
    monkeypatch.setattr(run_live_m2, "SUMMARY_FILE", directory / "run_summary.json")
    monkeypatch.setattr(make_m2_report, "SUMMARY_FILE", directory / "run_summary.json")
    return directory


def complete_result() -> PipelineResult:
    """A result shaped like a finished run, built from the fakes rather than a live call."""
    domain = DOMAINS[1]
    return PipelineResult(
        status="complete",
        idea=domain.idea,
        search=domain.search,
        warnings=["Competitor analysis: the targeted search 'x' found no results"],
        errors=[],
        timings={"extraction": 1.0, "search": 2.0, "market_opportunity": 3.0,
                 "competitor_analysis": 4.0, "capture": 0.0, "total": 10.0},
    )


# --- the --yes guard (Section 10.3) -----------------------------------------------------------


def test_without_yes_nothing_runs_and_no_file_is_written(output_dir: Path, capsys) -> None:
    exit_code = run_live_m2.main([])

    assert exit_code == 1
    assert not output_dir.exists(), "no directory is created before a run is confirmed"
    printed = capsys.readouterr().out
    assert "--yes" in printed and run_live_m2.MSG_NO_FILES in printed


def test_the_yes_flag_is_the_only_way_in(monkeypatch: pytest.MonkeyPatch, output_dir: Path) -> None:
    """Without --yes the key check is never even reached, so nothing can call out."""
    called: list[str] = []
    monkeypatch.setattr(run_live_m2, "missing_keys", lambda: called.append("checked") or [])
    monkeypatch.setattr(run_live_m2, "run_one", lambda name: pytest.fail("a run was attempted"))

    assert run_live_m2.main([]) == 1
    assert called == []


def test_an_unknown_flag_is_rejected(output_dir: Path) -> None:
    with pytest.raises(SystemExit):
        run_live_m2.main(["--go"])
    assert not output_dir.exists()


# --- missing keys (Section 10.3) --------------------------------------------------------------


@pytest.mark.parametrize(
    ("missing", "expected"),
    [
        ("LLM_API_KEY", "LLM_API_KEY"),
        ("LLM_MODEL", "LLM_MODEL"),
        ("TAVILY_API_KEY", "TAVILY_API_KEY"),
    ],
)
def test_a_missing_key_is_named_and_nothing_is_written(
    monkeypatch: pytest.MonkeyPatch, output_dir: Path, capsys, missing: str, expected: str
) -> None:
    monkeypatch.delenv(missing)
    monkeypatch.setattr(run_live_m2, "run_one", lambda name: pytest.fail("a run was attempted"))

    exit_code = run_live_m2.main(["--yes"])

    assert exit_code == 1
    assert not output_dir.exists(), run_live_m2.MSG_NO_FILES
    printed = capsys.readouterr().out
    assert expected in printed
    assert all(secret not in printed for secret in SECRETS), "a key value must never be printed"


def test_every_missing_key_is_listed_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_API_KEY", "LLM_MODEL", "TAVILY_API_KEY"):
        monkeypatch.delenv(name)
    assert run_live_m2.missing_keys() == ["LLM_API_KEY", "LLM_MODEL", "TAVILY_API_KEY"]


def test_configured_keys_report_nothing_missing() -> None:
    assert run_live_m2.missing_keys() == []


# --- what a run writes (Section 10.3) ---------------------------------------------------------


def fake_pipeline(monkeypatch: pytest.MonkeyPatch, *results: object):
    """Replace the pipeline itself, so the runner's own logic is what gets tested."""
    calls: list[tuple] = []

    def pipeline(submission, stages=None):
        calls.append((submission, stages))
        outcome = results[min(len(calls), len(results)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        for stage in stages or []:
            if getattr(stage, "name", "") == "capture":
                stage.context = None
        return outcome

    monkeypatch.setattr(run_live_m2, "run_pipeline", pipeline)
    return calls


def test_a_run_writes_json_markdown_and_a_summary(
    monkeypatch: pytest.MonkeyPatch, output_dir: Path
) -> None:
    calls = fake_pipeline(monkeypatch, complete_result())

    assert run_live_m2.main(["--yes"]) == 0

    assert len(calls) == len(run_live_m2.TASK_4_IDEAS) == 3
    for file_name in run_live_m2.TASK_4_IDEAS:
        name = Path(file_name).stem
        assert (output_dir / f"{name}.json").exists()
        assert (output_dir / f"{name}.md").exists()

    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["ideas_attempted"] == 3 and summary["ideas_executed"] == 3
    assert [entry["idea"] for entry in summary["runs"]] == ["agritech", "fintech_cashflow", "foodtech_surplus"]
    assert all(entry["executed"] for entry in summary["runs"])


def test_only_the_three_task_4_ideas_are_run(monkeypatch: pytest.MonkeyPatch, output_dir: Path) -> None:
    calls = fake_pipeline(monkeypatch, complete_result())
    run_live_m2.main(["--yes"])

    industries = {submission.industry for submission, _ in calls}
    assert industries == {"Agriculture / AgriTech", "Finance / FinTech", "Food & Beverage"}
    assert not (output_dir / "healthtech.json").exists(), "the other samples are left alone"


def test_the_runner_uses_the_integrated_stage_list(monkeypatch: pytest.MonkeyPatch, output_dir: Path) -> None:
    calls = fake_pipeline(monkeypatch, complete_result())
    run_live_m2.main(["--yes"])

    _, stages = calls[0]
    names = [stage.name for stage in stages]
    assert names[:4] == ["extraction", "search", "market_opportunity", "competitor_analysis"]
    assert names[-1] == "capture", "the capture stage is appended, not substituted"


def test_the_summary_records_a_partial_run_honestly(
    monkeypatch: pytest.MonkeyPatch, output_dir: Path
) -> None:
    partial = complete_result().model_copy(update={
        "status": "partial",
        "market": None,
        "competitors": None,
        "errors": [StageError(stage="market_opportunity", code="llm_api_error", message="The AI service is busy.")],
    })
    fake_pipeline(monkeypatch, partial)

    assert run_live_m2.main(["--yes"]) == 0
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    entry = summary["runs"][0]

    assert entry["status"] == "partial"
    assert entry["counts"]["segments"] is None, "a stage that produced nothing is null, not zero"
    assert entry["counts"]["competitors"] is None
    assert entry["integrity_violations"] == {
        "market_opportunity": ["not run"], "competitor_analysis": ["not run"]
    }
    assert entry["errors"][0]["stage"] == "market_opportunity"


def test_an_unexpected_error_is_recorded_without_a_result_file(
    monkeypatch: pytest.MonkeyPatch, output_dir: Path
) -> None:
    fake_pipeline(monkeypatch, RuntimeError("provider internals"))

    exit_code = run_live_m2.main(["--yes"])

    assert exit_code == 1, "a run that produced nothing is not reported as success"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["ideas_executed"] == 0
    assert all(entry["executed"] is False for entry in summary["runs"])
    assert "RuntimeError" in summary["runs"][0]["reason"]
    assert not (output_dir / "agritech.json").exists(), "no result file for a run that failed"
    assert "provider internals" not in json.dumps(summary)


def test_a_markdown_report_states_what_was_not_produced(output_dir: Path) -> None:
    partial = complete_result().model_copy(update={"status": "partial", "market": None, "competitors": None})
    text = run_live_m2.idea_markdown(
        "fintech_cashflow", DOMAINS[1].submission, partial,
        {"market_opportunity": ["not run"], "competitor_analysis": ["not run"]},
    )

    assert "Status: partial" in text
    assert text.count("Not produced in this run.") == 2
    assert "market_opportunity: not run" in text
    assert all(secret not in text for secret in SECRETS)


def test_counts_come_from_the_result_only() -> None:
    assert run_live_m2.counts_for(complete_result())["segments"] is None
    assert run_live_m2.counts_for(complete_result())["search_results"] == DOMAINS[1].search.total_results


# --- the report refresher (Section 10.4) -------------------------------------------------------


@pytest.fixture
def report_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "09_milestone2_test_report.md"
    path.write_text(
        "# Report\n\nAutomated results stay here.\n\n"
        f"{make_m2_report.START_MARKER}\nplaceholder\n{make_m2_report.END_MARKER}\n\n"
        "## Human review checklist\n\n- [ ] untouched\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(make_m2_report, "REPORT_FILE", path)
    return path


def test_without_a_summary_every_idea_is_not_executed(report_file: Path, output_dir: Path) -> None:
    assert make_m2_report.main() == 0
    text = report_file.read_text(encoding="utf-8")

    assert text.count("**Not executed**") == 3
    assert "run_summary.json` does not exist yet" in text
    assert "Automated results stay here." in text, "the automated section is left alone"
    assert "- [ ] untouched" in text, "the checklist is left alone"
    assert "placeholder" not in text


def test_a_real_summary_fills_the_live_table(report_file: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_summary.json").write_text(json.dumps({
        "generated": "2026-10-27 18:00",
        "model": "some-model",
        "ideas_attempted": 3,
        "ideas_executed": 2,
        "runs": [
            {"idea": "agritech", "file": "agritech.json", "executed": True, "industry": "Agriculture / AgriTech",
             "status": "complete", "timings": {"total": 212.5}, "counts": {"competitors": 5, "segments": 2,
             "market_sources": 7, "competitor_sources": 6}, "warnings": ["Market opportunity: a note"],
             "integrity_violations": {"market_opportunity": [], "competitor_analysis": []}},
            {"idea": "fintech_cashflow", "file": "fintech_cashflow.json", "executed": True,
             "industry": "Finance / FinTech", "status": "partial", "timings": {"total": 150.0},
             "counts": {"competitors": None, "segments": 3, "market_sources": 4, "competitor_sources": None},
             "warnings": [], "integrity_violations": {"market_opportunity": [], "competitor_analysis": ["not run"]}},
            {"idea": "foodtech_surplus", "file": "foodtech_surplus.json", "executed": False,
             "reason": "unexpected error (TimeoutError)"},
        ],
    }), encoding="utf-8")

    assert make_m2_report.main() == 0
    text = report_file.read_text(encoding="utf-8")

    assert "2 of 3 ideas executed" in text
    assert "| `agritech` | Agriculture / AgriTech | complete | 212.5s |" in text
    assert "competitor_analysis: not run" in text
    assert "unexpected error (TimeoutError)" in text
    assert text.count("**Not executed**") == 1, "only the idea that did not run"
    assert "Market opportunity: a note" in text


def test_an_empty_summary_is_reported_as_nothing_executed(report_file: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_summary.json").write_text(json.dumps({"runs": []}), encoding="utf-8")

    assert make_m2_report.main() == 0
    text = report_file.read_text(encoding="utf-8")
    assert "holds no run" in text and text.count("**Not executed**") == 3


def test_an_unreadable_summary_never_invents_results(report_file: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_summary.json").write_text("{ not json", encoding="utf-8")

    assert make_m2_report.main() == 0
    text = report_file.read_text(encoding="utf-8")
    assert "could not be read" in text and text.count("**Not executed**") == 3


def test_a_report_without_markers_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output_dir: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text("# Report\n\nno markers here\n", encoding="utf-8")
    monkeypatch.setattr(make_m2_report, "REPORT_FILE", path)

    with pytest.raises(SystemExit):
        make_m2_report.main()
    assert path.read_text(encoding="utf-8") == "# Report\n\nno markers here\n", "left untouched"


def test_a_missing_report_is_reported_not_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "absent.md"
    monkeypatch.setattr(make_m2_report, "REPORT_FILE", path)

    assert make_m2_report.main() == 1
    assert not path.exists()


def test_the_checked_in_report_agrees_with_the_live_summary() -> None:
    """The checked-in report must say exactly what the artefacts say, in whatever state the
    project is in.

    With no `run_summary.json` every idea reads "Not executed". With one, an idea the summary
    records as executed shows the status and time that run recorded, an idea it records as
    failed reads "Not executed" with its reason, and an idea it never attempted is named as
    not attempted rather than given a result. So the report can neither invent a live result
    nor hide one.
    """
    report = ROOT_DIR / "docs" / "09_milestone2_test_report.md"
    summary_file = ROOT_DIR / "docs" / "test_runs_m2" / "run_summary.json"
    text = report.read_text(encoding="utf-8")

    assert make_m2_report.START_MARKER in text and make_m2_report.END_MARKER in text
    live = text.split(make_m2_report.START_MARKER, 1)[1].split(make_m2_report.END_MARKER, 1)[0]
    for name in make_m2_report.TASK_4_IDEAS:
        assert f"`{name}`" in live, f"{name} is missing from the live section"

    if not summary_file.exists():
        assert live.count("**Not executed**") == len(make_m2_report.TASK_4_IDEAS)
        assert make_m2_report.NOT_EXECUTED_REASON in live
        return

    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    runs = summary.get("runs") or []
    assert runs, "a summary that exists must hold at least one run"
    assert f"{summary['ideas_executed']} of {summary['ideas_attempted']} ideas executed" in live

    rows = {line.split("|")[1].strip().strip("`"): line for line in live.splitlines() if line.startswith("| `")}
    unexecuted = 0
    for entry in runs:
        name = entry["idea"]
        if not entry.get("executed"):
            unexecuted += 1
            assert "**Not executed**" in rows[name], f"{name} did not run, so it must say so"
            assert entry["reason"] in rows[name], f"{name}: the reason must be shown"
            continue
        row = rows[name]
        assert f"| {entry['status']} |" in row, f"{name}: the row must show the status the run recorded"
        assert f"| {entry['timings']['total']:.1f}s |" in row, f"{name}: the row must show its real time"
        assert "Not executed" not in row, f"{name} ran, so it must not be marked unexecuted"

    assert live.count("**Not executed**") == unexecuted, "no idea is marked unexecuted wrongly"
    attempted = {entry["idea"] for entry in runs}
    for name in make_m2_report.TASK_4_IDEAS:
        if name not in attempted:
            assert f"Not attempted in that run: " in live and f"`{name}`" in live

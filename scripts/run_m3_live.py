import argparse
import json
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agents import (  # noqa: E402
    advisor_agent,
    competitor_analysis_agent,
    extraction_agent,
    gtm_agent,
    market_opportunity_agent,
    mvp_agent,
    swot_risk_agent,
    web_search_agent,
)
from agents.mvp_agent import TIER_LATER, TIER_MVP  # noqa: E402
from agents.strategy_checks import configured_secrets  # noqa: E402
from agents.swot_risk_agent import QUADRANTS  # noqa: E402
from config import get_settings, setup_logging  # noqa: E402
from frontend.analysis_views import report_markdown  # noqa: E402
from models.schemas import IdeaSubmission, PipelineResult  # noqa: E402
from orchestrator import EVENT_STARTED, TOTAL_KEY, StageEvent  # noqa: E402
from scripts.check_m3_contracts import check_result  # noqa: E402
from utils import groq_client  # noqa: E402
from utils.run_manager import (  # noqa: E402
    STRATEGY_ONLY_KEYS,
    STRATEGY_STAGE_KEYS,
    TITLES,
    run_time_limit_s,
    strategy_pipeline,
    strategy_time_limit_s,
)
from utils.run_store import REDACTED  # noqa: E402

IDEAS_DIR = ROOT_DIR / "data" / "test_ideas"
OUTPUT_DIR = ROOT_DIR / "docs" / "test_runs_m3"
SUMMARY_NAME = "run_summary.json"
IDEAS = ("agritech.json", "fintech_cashflow.json", "foodtech_surplus.json")
FULL_RUN_KEYS = ("LLM_API_KEY", "LLM_MODEL", "TAVILY_API_KEY")
LLM_KEYS = ("LLM_API_KEY", "LLM_MODEL")
FAKE_DIR_PREFIX = "m3_fake_"
FAKE_MODEL = "fake"
STAGE_ESTIMATE_S = (15, 35)
STRATEGY_ESTIMATE_S = (45, 105)

CALL_KINDS = ("llm", "groq", "searches")
LLM_MODULES = (
    extraction_agent,
    market_opportunity_agent,
    competitor_analysis_agent,
    swot_risk_agent,
    mvp_agent,
    gtm_agent,
    advisor_agent,
)
SEAMS = (
    *((module, "generate_json", "llm") for module in LLM_MODULES),
    (groq_client, "generate_json", "groq"),
    (web_search_agent, "search", "searches"),
)

MSG_NEEDS_YES = (
    "This script makes real API calls and spends credits. Nothing has been run.\n"
    "Re-run it with --yes once you are ready:\n"
    "    python scripts/{script} --yes\n"
    "or try it offline with the fake clients of the test suite:\n"
    "    python scripts/{script} --fake"
)
MSG_NEEDS_KEYS = "This script needs real keys in the project root .env."
MSG_MISSING_KEYS = "Missing: {names}"
MSG_HOW_TO_FIX = "Copy .env.example to .env and fill in your own values, then run this again."
MSG_NO_FILES = "No result or summary file was written."
MSG_FAKE_RUN = (
    "Fake run: the fake clients of the test suite answer every call, so no provider is called and nothing here is "
    "evidence."
)
MSG_LIVE_RUN = "Live run: the real providers are called and credits are spent."
MSG_NO_VIOLATIONS = "No strategy rule is broken (the rules of scripts/check_m3_contracts.py)."
MSG_NOT_MEASURED = "not measured"
CHECKLIST_HEADING = "Review checklist for {title} (record the outcome in docs/12; nothing here is ticked for you):"
CHECKLIST = {
    1: "Every SWOT item and risk is understandable without outside knowledge and relates to the idea.",
    2: "No competitor, organisation, price or statistic appears that is not in the market or competitor results.",
    3: "Risks cover the categories; gaps are stated.",
    4: "The MVP list contains the founder's own features; deferred reasons make sense; assumptions are visible.",
    5: "The positioning sentence reads naturally and the differentiator label fits.",
    6: "Channels are plausible for the segment and region; the first experiment is concrete.",
    7: "Advisor answers cite results; the out-of-scope and injection questions are refused cleanly.",
    8: "Timing: record the total seconds and the strategy seconds and compare them with the estimate in plan Section 5.4.",
}
STRATEGY_ITEMS = (1, 2, 3, 4, 5, 6, 8)


class Meter:
    def __init__(self, stage: str | None = None) -> None:
        self.stage = stage
        self.calls: dict[str | None, dict[str, int]] = {}

    def on_event(self, event: StageEvent) -> None:
        if event.kind == EVENT_STARTED:
            self.stage = event.stage

    def counted(self, kind: str, function: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: Any, **kwargs: Any) -> Any:
            self.calls.setdefault(self.stage, dict.fromkeys(CALL_KINDS, 0))[kind] += 1
            return function(*args, **kwargs)

        return call

    def of(self, stage: str | None) -> dict[str, int]:
        return dict(self.calls.get(stage, dict.fromkeys(CALL_KINDS, 0)))

    def total(self) -> dict[str, int]:
        return {kind: sum(entry[kind] for entry in self.calls.values()) for kind in CALL_KINDS}


@contextmanager
def metered(meter: Meter) -> Iterator[Meter]:
    originals = [(module, name, getattr(module, name)) for module, name, _ in SEAMS]
    try:
        for module, name, kind in SEAMS:
            setattr(module, name, meter.counted(kind, getattr(module, name)))
        yield meter
    finally:
        for module, name, original in originals:
            setattr(module, name, original)


@contextmanager
def clients(fake: bool, **parts: bool) -> Iterator[None]:
    if not fake:
        yield
        return
    from tests.m3_live_fakes import fake_clients

    with fake_clients(**parts):
        yield


def never() -> bool:
    return False


def redact(text: str) -> str:
    for secret in configured_secrets():
        text = text.replace(secret, REDACTED)
    return text


def say(text: str = "") -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(redact(text).encode(encoding, errors="replace").decode(encoding))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(text), encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    write(path, json.dumps(data, indent=2))


def shown(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return path.name


def parser(description: str) -> argparse.ArgumentParser:
    found = argparse.ArgumentParser(description=description)
    mode = found.add_mutually_exclusive_group()
    mode.add_argument(
        "--yes", action="store_true",
        help="confirm that real API calls may be made and credits spent; without it nothing runs",
    )
    mode.add_argument(
        "--fake", action="store_true",
        help="use the fake clients of the test suite: no provider is called, no key is needed, no credit is spent",
    )
    found.add_argument(
        "--out", type=Path,
        help="folder for the files (default: docs/test_runs_m3, or a new temporary folder with --fake)",
    )
    return found


def missing_keys(names: Sequence[str]) -> list[str]:
    settings = get_settings()
    configured = {
        "LLM_API_KEY": settings.llm_api_key,
        "LLM_MODEL": settings.llm_model,
        "TAVILY_API_KEY": settings.tavily_api_key,
    }
    return [name for name in names if not configured[name]]


def ready(args: argparse.Namespace, script: str, keys: Sequence[str]) -> bool:
    if args.fake:
        return True
    if not args.yes:
        say(MSG_NEEDS_YES.format(script=script))
        say(MSG_NO_FILES)
        return False
    missing = missing_keys(keys)
    if missing:
        say(MSG_NEEDS_KEYS)
        say(MSG_MISSING_KEYS.format(names=", ".join(missing)))
        say(MSG_HOW_TO_FIX)
        say(MSG_NO_FILES)
        return False
    return True


def output_dir(args: argparse.Namespace) -> Path:
    if args.out is not None:
        return args.out
    return Path(tempfile.mkdtemp(prefix=FAKE_DIR_PREFIX)) if args.fake else OUTPUT_DIR


def model_name(fake: bool) -> str | None:
    return FAKE_MODEL if fake else get_settings().llm_model


def generated_at() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read_submission(path: Path) -> IdeaSubmission:
    return IdeaSubmission(**json.loads(path.read_text(encoding="utf-8")))


def seconds_text(value: float | None) -> str:
    return MSG_NOT_MEASURED if value is None else f"{value:.1f} s"


def strategy_seconds(result: PipelineResult) -> float | None:
    found = [result.timings[key] for key in STRATEGY_ONLY_KEYS if key in result.timings]
    return round(sum(found), 3) if found else None


def strategy_counts(result: PipelineResult) -> dict[str, Any]:
    swot, mvp, gtm = result.swot, result.mvp, result.gtm
    start = next((channel for channel in gtm.channels if channel.start_here), None) if gtm is not None else None
    return {
        "swot": None if swot is None else {
            **{name: len(getattr(swot, name)) for name in QUADRANTS},
            "risks": len(swot.risks),
            "risks_by_category": dict(swot.risk_category_coverage),
            "coverage_gaps": list(swot.coverage_gaps),
        },
        "mvp": None if mvp is None else {
            "in_scope": [feature.name for feature in mvp.features if feature.tier == TIER_MVP],
            "deferred": [feature.name for feature in mvp.features if feature.tier == TIER_LATER],
            "capacity_person_months": mvp.capacity_person_months,
            "planned_person_months": mvp.planned_person_months,
            "over_capacity": mvp.over_capacity,
            "constraints_assumed": list(mvp.quality.constraints_assumed),
        },
        "gtm": None if gtm is None else {
            "target_segment": gtm.positioning.target_segment,
            "differentiator_status": gtm.positioning.differentiator_status,
            "channels": [channel.name for channel in gtm.channels],
            "start_here": start.name if start is not None else None,
            "first_experiment": start.first_experiment if start is not None else None,
            "launch_phases": len(gtm.launch_phases),
        },
    }


def run_entry(result: PipelineResult, meter: Meter, keys: Sequence[str]) -> dict[str, Any]:
    return {
        "status": result.status,
        "seconds": {key: result.timings.get(key) for key in (*keys, TOTAL_KEY)},
        "strategy_seconds": strategy_seconds(result),
        "calls": {**{key: meter.of(key) for key in keys}, TOTAL_KEY: meter.total()},
        "warnings": list(result.warnings),
        "errors": [{"stage": item.stage, "code": item.code, "message": item.message} for item in result.errors],
        "counts": strategy_counts(result),
        "contract_violations": [violation.line() for violation in check_result(result)],
    }


def timing_hint(entry: Mapping[str, Any]) -> str:
    seconds = entry["seconds"]
    parts = ", ".join(f"{TITLES[key]} {seconds[key]:.1f} s" for key in STRATEGY_ONLY_KEYS if seconds.get(key) is not None)
    measured = f"total {seconds_text(seconds.get(TOTAL_KEY))}, strategy {seconds_text(entry['strategy_seconds'])}"
    estimate = (
        f"the plan estimated {STAGE_ESTIMATE_S[0]} to {STAGE_ESTIMATE_S[1]} s per strategy stage and "
        f"{STRATEGY_ESTIMATE_S[0]} to {STRATEGY_ESTIMATE_S[1]} s in all"
    )
    return f"{measured}{f' ({parts})' if parts else ''}; {estimate}"


def strategy_hints(entry: Mapping[str, Any]) -> dict[int, str]:
    counts = entry["counts"]
    found = {8: timing_hint(entry)}
    if counts["swot"] is not None:
        risks = ", ".join(f"{category} {count}" for category, count in counts["swot"]["risks_by_category"].items())
        found[3] = f"risks by category: {risks or 'none'}; gaps: {', '.join(counts['swot']['coverage_gaps']) or 'none'}"
    if counts["mvp"] is not None:
        mvp = counts["mvp"]
        found[4] = (
            f"in scope: {'; '.join(mvp['in_scope']) or 'none'}; deferred: {'; '.join(mvp['deferred']) or 'none'}; "
            f"assumed: {', '.join(mvp['constraints_assumed']) or 'nothing'}"
        )
    if counts["gtm"] is not None:
        found[5] = f"differentiator: {counts['gtm']['differentiator_status']}"
        found[6] = f"start here: {counts['gtm']['start_here'] or 'none'}"
    return found


def checklist(items: Sequence[int], hints: Mapping[int, str]) -> list[str]:
    return [f"[ ] {number}. {CHECKLIST[number]}" + (f" Measured: {hints[number]}." if number in hints else "") for number in items]


def print_checklist(title: str, lines: Sequence[str]) -> None:
    say(CHECKLIST_HEADING.format(title=title))
    for line in lines:
        say(f"  {line}")
    say()


def demoted(text: str) -> str:
    return "\n".join(f"#{line}" if line.startswith("#") else line for line in text.splitlines())


def stage_table(entry: Mapping[str, Any], keys: Sequence[str]) -> list[str]:
    rows = ["| Stage | Seconds | LLM calls | Groq calls | Searches |", "|---|---:|---:|---:|---:|"]
    for key in (*keys, TOTAL_KEY):
        calls = entry["calls"][key]
        label = "Total" if key == TOTAL_KEY else TITLES.get(key, key)
        rows.append(
            f"| {label} | {seconds_text(entry['seconds'].get(key))} | {calls['llm']} | {calls['groq']} | {calls['searches']} |"
        )
    return rows


def run_markdown(
    title: str,
    entry: Mapping[str, Any],
    result: PipelineResult,
    keys: Sequence[str],
    review: Sequence[str],
    *,
    fake: bool,
    generated: str,
    submission: IdeaSubmission | None = None,
    notes: Sequence[str] = (),
) -> str:
    lines = [f"# {title}", "", MSG_FAKE_RUN if fake else MSG_LIVE_RUN, "", f"Generated: {generated}", f"Status: {result.status}"]
    lines += [*notes, ""]
    if submission is not None:
        lines += [
            "## Submitted idea",
            "",
            f"- Industry: {submission.industry}",
            f"- Target customers: {submission.target_customers}",
            f"- Description: {submission.idea_description}",
            "",
        ]
    lines += ["## Seconds and calls per stage", "", *stage_table(entry, keys), ""]
    lines += ["## Strategy rule check", ""]
    lines += [f"- {line}" for line in entry["contract_violations"]] or [MSG_NO_VIOLATIONS]
    lines += ["", "## Review checklist", "", *(f"- {line}" for line in review), ""]
    lines += [demoted(report_markdown(result, full=True)), ""]
    return "\n".join(lines)


def run_line(name: str, entry: Mapping[str, Any]) -> str:
    total = entry["calls"][TOTAL_KEY]
    return (
        f"{name:<18} {entry['status']:<9} total={seconds_text(entry['seconds'][TOTAL_KEY])} "
        f"strategy={seconds_text(entry['strategy_seconds'])} llm={total['llm']} groq={total['groq']} "
        f"searches={total['searches']} warnings={len(entry['warnings'])} errors={len(entry['errors'])} "
        f"violations={len(entry['contract_violations'])}"
    )


def run_one(file_name: str, fake: bool, out: Path, generated: str) -> dict[str, Any]:
    name = Path(file_name).stem
    path = IDEAS_DIR / file_name
    try:
        submission = read_submission(path)
    except Exception as exc:
        say(f"{name:<18} SKIPPED: {path.name} could not be read as an idea ({type(exc).__name__})")
        return {"idea": name, "file": file_name, "executed": False,
                "reason": f"the idea file could not be read ({type(exc).__name__})"}
    meter = Meter()
    try:
        with clients(fake, analysis=True, strategy=True), metered(meter):
            result = strategy_pipeline(
                submission, idea=None, on_event=meter.on_event, should_stop=never,
                time_limit_s=run_time_limit_s(), strategy_time_limit_s=strategy_time_limit_s(),
                constraints=None, prior=None,
            )
    except Exception as exc:
        say(f"{name:<18} FAILED: unexpected error ({type(exc).__name__})")
        return {"idea": name, "file": file_name, "executed": False, "reason": f"unexpected error ({type(exc).__name__})"}
    entry = {"idea": name, "file": file_name, "executed": True, "industry": submission.industry,
             **run_entry(result, meter, STRATEGY_STAGE_KEYS)}
    review = checklist(STRATEGY_ITEMS, strategy_hints(entry))
    write(out / f"{name}.json", result.model_dump_json(indent=2))
    write(out / f"{name}.md", run_markdown(
        f"Milestone 3 run: {name}", entry, result, STRATEGY_STAGE_KEYS, review,
        fake=fake, generated=generated, submission=submission,
    ))
    say(run_line(name, entry))
    print_checklist(name, review)
    return entry


def main(argv: list[str] | None = None) -> int:
    args = parser(
        "Run the three Milestone 2 ideas through all seven stages, strategy included, and save the evidence (plan L-1)."
    ).parse_args(argv)
    if not ready(args, "run_m3_live.py", FULL_RUN_KEYS):
        return 1
    setup_logging()
    out = output_dir(args)
    generated = generated_at()
    say(MSG_FAKE_RUN if args.fake else MSG_LIVE_RUN)
    say(f"Running {len(IDEAS)} ideas through the seven stages.\n")
    entries = [run_one(file_name, args.fake, out, generated) for file_name in IDEAS]
    executed = [entry for entry in entries if entry["executed"]]
    write_json(out / SUMMARY_NAME, {
        "generated": generated,
        "fake": args.fake,
        "model": model_name(args.fake),
        "ideas_attempted": len(entries),
        "ideas_executed": len(executed),
        "runs": entries,
    })
    say(f"Saved {len(executed)} of {len(entries)} runs to {out}")
    say(f"Summary: {out / SUMMARY_NAME}")
    return 0 if len(executed) == len(entries) else 1


if __name__ == "__main__":
    raise SystemExit(main())

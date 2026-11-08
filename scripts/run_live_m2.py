"""Live validation of the integrated Milestone 2 pipeline (KIRO_PROMPT_M2.md Section 10.3).

Runs the three Task 4 sample ideas through the four-stage pipeline with **real** API calls, saves
the evidence, checks every result with the integrity checkers, and writes a run summary.

    python scripts/run_live_m2.py --yes

Nothing happens without `--yes`: the flag is the confirmation that real credits may be spent.
Without real keys in the project root `.env` the script says which variables are missing and
writes no files at all. Keys are never printed.

One run costs roughly 4 LLM calls and up to 11 web searches per idea, so about 12 LLM calls and
33 searches in total, and can take several minutes per idea.

Outputs, all under docs/test_runs_m2/:
    <idea>.json          the full PipelineResult
    <idea>.md            a readable report
    run_summary.json     status, timings, counts and integrity violations per idea

A failed or partial run is recorded as it happened. Nothing is invented, and a stage that did not
produce a result is written as null with its error.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agents.base import AgentContext  # noqa: E402
from agents.competitor_analysis_agent import competitor_evidence  # noqa: E402
from agents.integrity import check_competitor_integrity, check_market_integrity  # noqa: E402
from agents.market_size import market_evidence  # noqa: E402
from agents.web_search_agent import render_markdown  # noqa: E402
from config import get_settings, setup_logging  # noqa: E402
from models.schemas import IdeaSubmission, PipelineResult  # noqa: E402
from orchestrator import FULL_STAGES, run_pipeline  # noqa: E402

IDEAS_DIR = ROOT_DIR / "data" / "test_ideas"
OUTPUT_DIR = ROOT_DIR / "docs" / "test_runs_m2"
SUMMARY_FILE = OUTPUT_DIR / "run_summary.json"

# Section 10.1: the three Task 4 domains, and only those.
TASK_4_IDEAS = ("agritech.json", "fintech_cashflow.json", "foodtech_surplus.json")

MSG_NEEDS_YES = (
    "This script makes real API calls and spends credits. Nothing has been run.\n"
    "Re-run it with --yes once you are ready:\n"
    "    python scripts/run_live_m2.py --yes"
)
MSG_MISSING_KEYS = "Missing: {names}"
MSG_HOW_TO_FIX = "Copy .env.example to .env and fill in your own values, then run this again."
MSG_NO_FILES = "No result or summary file was written."


class CaptureStage:
    """Keeps the shared context so the evidence each agent saw can be rebuilt for the integrity
    checkers. `PipelineResult` does not carry the targeted searches, and the pipeline takes a
    stage list, so this needs no change to any agent or to the orchestrator."""

    name = "capture"

    def __init__(self) -> None:
        self.context: AgentContext | None = None

    def run(self, context: AgentContext) -> AgentContext:
        self.context = context
        return context


def missing_keys() -> list[str]:
    """The names of the settings that are not configured. Never their values."""
    settings = get_settings()
    missing = []
    if not settings.llm_api_key:
        missing.append("LLM_API_KEY")
    if not settings.llm_model:
        missing.append("LLM_MODEL")
    if not settings.tavily_api_key:
        missing.append("TAVILY_API_KEY")
    return missing


def violations_for(result: PipelineResult, context: AgentContext | None) -> dict[str, list[str]]:
    """Integrity violations per analysis, from the evidence rebuilt out of the context.

    A stage that produced nothing is reported as not run rather than as clean.
    """
    found: dict[str, list[str]] = {}
    if context is None:
        return {"market_opportunity": ["not run"], "competitor_analysis": ["not run"]}

    if result.market is None:
        found["market_opportunity"] = ["not run"]
    else:
        evidence = market_evidence(context.search, context.market_search, context.idea)
        found["market_opportunity"] = check_market_integrity(result.market, evidence)

    if result.competitors is None:
        found["competitor_analysis"] = ["not run"]
    else:
        evidence = competitor_evidence(
            context.search, context.competitor_search, context.competitor_candidates
        )
        found["competitor_analysis"] = check_competitor_integrity(result.competitors, evidence)
    return found


def counts_for(result: PipelineResult) -> dict[str, int | None]:
    """Section 10.3 counts. None means the stage produced no result, not zero."""
    market, competitors = result.market, result.competitors
    return {
        "search_results": result.search.total_results if result.search else None,
        "queries_failed": result.search.queries_failed if result.search else None,
        "segments": len(market.segments) if market else None,
        "market_sources": len(market.sources) if market else None,
        "broader_market_figures": len(market.broader_markets) if market else None,
        "competitors": len(competitors.competitors) if competitors else None,
        "comparison_features": len(competitors.comparison.features) if competitors else None,
        "market_gaps": len(competitors.market_gaps) if competitors else None,
        "competitor_sources": len(competitors.sources) if competitors else None,
        "targeted_competitor_queries": len(competitors.queries_used) if competitors else None,
    }


def idea_markdown(name: str, submission: IdeaSubmission, result: PipelineResult, violations: dict) -> str:
    lines = [
        f"# Live Milestone 2 run: {name}",
        "",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
        f"Status: {result.status}",
        f"Timings (seconds): {result.timings}",
        "",
        "## Submitted idea",
        "",
        f"- Industry: {submission.industry}",
        f"- Target customers: {submission.target_customers}",
        f"- Description: {submission.idea_description}",
        "",
    ]
    if result.warnings:
        lines += ["## Warnings", ""] + [f"- {text}" for text in result.warnings] + [""]
    if result.errors:
        lines += ["## Errors", ""]
        lines += [f"- {item.stage}: {item.message} ({item.code})" for item in result.errors] + [""]

    lines += ["## Integrity check", ""]
    for stage, problems in violations.items():
        if problems == ["not run"]:
            lines.append(f"- {stage}: not run")
        elif problems:
            lines.append(f"- {stage}: {len(problems)} violation(s)")
            lines += [f"  - {problem}" for problem in problems]
        else:
            lines.append(f"- {stage}: no violations")
    lines.append("")

    if result.idea is not None:
        idea = result.idea
        lines += [
            "## Structured idea",
            "",
            f"**{idea.idea_title}**",
            "",
            f"- Industry: {idea.industry}",
            f"- Problem: {idea.problem}",
            f"- Solution: {idea.solution}",
            "- Target customers: " + "; ".join(idea.target_customers),
            "- Key features: " + "; ".join(idea.key_features),
            "",
        ]
    if result.market is not None:
        lines += ["## Market opportunity", "", "```json",
                  result.market.model_dump_json(indent=2), "```", ""]
    else:
        lines += ["## Market opportunity", "", "Not produced in this run.", ""]
    if result.competitors is not None:
        lines += ["## Competitors", "", "```json",
                  result.competitors.model_dump_json(indent=2), "```", ""]
    else:
        lines += ["## Competitors", "", "Not produced in this run.", ""]
    if result.search is not None:
        lines += [render_markdown(result.search)]
    return "\n".join(lines)


def run_one(file_name: str) -> dict:
    """One idea through the integrated pipeline. Returns its summary entry."""
    name = Path(file_name).stem
    path = IDEAS_DIR / file_name
    try:
        submission = IdeaSubmission(**json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:
        print(f"{name:<20} SKIPPED: {path.name} could not be read as an idea ({type(exc).__name__})")
        return {"idea": name, "file": file_name, "executed": False,
                "reason": f"the idea file could not be read ({type(exc).__name__})"}

    capture = CaptureStage()
    try:
        result = run_pipeline(submission, [*FULL_STAGES, capture])
    except Exception as exc:
        print(f"{name:<20} FAILED: unexpected error ({type(exc).__name__})")
        return {"idea": name, "file": file_name, "executed": False,
                "reason": f"unexpected error ({type(exc).__name__})"}

    violations = violations_for(result, capture.context)
    timings = {stage: round(value, 3) for stage, value in result.timings.items() if stage != capture.name}
    print(
        f"{name:<20} {result.status:<9} "
        f"total={timings.get('total', 0):.1f}s "
        f"warnings={len(result.warnings)} errors={len(result.errors)} "
        f"violations={sum(len(v) for v in violations.values() if v != ['not run'])}"
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{name}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    (OUTPUT_DIR / f"{name}.md").write_text(
        idea_markdown(name, submission, result, violations), encoding="utf-8"
    )
    return {
        "idea": name,
        "file": file_name,
        "executed": True,
        "industry": submission.industry,
        "status": result.status,
        "timings": timings,
        "counts": counts_for(result),
        "warnings": list(result.warnings),
        "errors": [{"stage": item.stage, "code": item.code, "message": item.message} for item in result.errors],
        "integrity_violations": violations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the three Task 4 ideas through the integrated pipeline with real API calls."
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="confirm that real API calls may be made and credits spent; without it nothing runs",
    )
    args = parser.parse_args(argv)

    if not args.yes:
        print(MSG_NEEDS_YES)
        print(MSG_NO_FILES)
        return 1

    missing = missing_keys()
    if missing:
        print("This script needs real keys in the project root .env.")
        print(MSG_MISSING_KEYS.format(names=", ".join(missing)))
        print(MSG_HOW_TO_FIX)
        print(MSG_NO_FILES)
        return 1

    setup_logging()
    settings = get_settings()
    print(f"Model: {settings.llm_model} | web search configured: yes")
    print(f"Running {len(TASK_4_IDEAS)} ideas through the integrated pipeline. This spends credits.\n")

    entries = [run_one(file_name) for file_name in TASK_4_IDEAS]
    executed = [entry for entry in entries if entry["executed"]]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(
        json.dumps(
            {
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "model": settings.llm_model,
                "ideas_attempted": len(entries),
                "ideas_executed": len(executed),
                "runs": entries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved {len(executed)} of {len(entries)} runs to {OUTPUT_DIR}")
    print(f"Summary: {SUMMARY_FILE}")
    return 0 if len(executed) == len(entries) else 1


if __name__ == "__main__":
    raise SystemExit(main())

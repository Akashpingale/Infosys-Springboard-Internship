"""Run every test idea through the real pipeline and save the evidence.

Needs real keys in the project root .env. Run from the project root:

    python scripts/run_live_ideas.py

Writes docs/test_runs/<idea>.json and docs/test_runs/<idea>.md for each idea.
Keys are never printed.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agents.web_search_agent import render_markdown  # noqa: E402
from config import get_settings, setup_logging  # noqa: E402
from models.schemas import IdeaSubmission, PipelineResult  # noqa: E402
from orchestrator import run_pipeline  # noqa: E402

IDEAS_DIR = ROOT_DIR / "data" / "test_ideas"
OUTPUT_DIR = ROOT_DIR / "docs" / "test_runs"


def check_keys() -> bool:
    settings = get_settings()
    missing = []
    if not settings.llm_api_key or not settings.llm_model:
        missing.append("LLM_API_KEY and LLM_MODEL")
    if not settings.tavily_api_key:
        missing.append("TAVILY_API_KEY")
    if missing:
        print("This script makes real API calls and needs real keys in the project root .env.")
        print("Missing: " + "; ".join(missing))
        print("Copy .env.example to .env and fill in your own values, then run this again.")
        return False
    print(f"Model: {settings.llm_model} | web search configured: yes")
    return True


def idea_markdown(name: str, submission: IdeaSubmission, result: PipelineResult) -> str:
    lines = [
        f"# Live run: {name}",
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
    if result.search is not None:
        lines += [render_markdown(result.search)]
    return "\n".join(lines)


def run_one(path: Path) -> PipelineResult | None:
    name = path.stem
    try:
        submission = IdeaSubmission(**json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:
        print(f"{name:<12} SKIPPED: the file could not be read as an idea ({type(exc).__name__})")
        return None

    try:
        result = run_pipeline(submission)
    except Exception as exc:
        print(f"{name:<12} FAILED: unexpected error ({type(exc).__name__})")
        return None

    results_found = result.search.total_results if result.search else 0
    queries_failed = result.search.queries_failed if result.search else 0
    print(
        f"{name:<12} {result.status:<9} "
        f"results={results_found:<3} queries_failed={queries_failed} "
        f"extraction={result.timings.get('extraction', 0):.1f}s "
        f"search={result.timings.get('search', 0):.1f}s "
        f"total={result.timings.get('total', 0):.1f}s"
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{name}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    (OUTPUT_DIR / f"{name}.md").write_text(
        idea_markdown(name, submission, result), encoding="utf-8"
    )
    return result


def main() -> int:
    setup_logging()
    if not check_keys():
        return 1

    paths = sorted(IDEAS_DIR.glob("*.json"))
    if not paths:
        print(f"No idea files found in {IDEAS_DIR}")
        return 1

    print(f"Running {len(paths)} ideas through the real pipeline. This takes a while.\n")
    results = [run_one(path) for path in paths]
    completed = [r for r in results if r is not None]

    print(f"\nSaved {len(completed)} runs to {OUTPUT_DIR}")
    by_status: dict[str, int] = {}
    for result in completed:
        by_status[result.status] = by_status.get(result.status, 0) + 1
    print("Outcomes: " + (", ".join(f"{k}={v}" for k, v in sorted(by_status.items())) or "none"))
    return 0 if len(completed) == len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())

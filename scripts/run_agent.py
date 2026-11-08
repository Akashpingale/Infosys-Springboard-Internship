"""Run one Milestone 2 agent on a test idea, for development. Makes real API calls.

Run from the project root:

    python scripts/run_agent.py market --idea data/test_ideas/agritech.json
    python scripts/run_agent.py competitor --idea data/test_ideas/agritech.json
    python scripts/run_agent.py competitor --idea data/test_ideas/agritech.json --with-market

Runs idea extraction and web search, then the chosen agent (which runs its own targeted
searches), and prints what the agent saw for auditing (the extracted idea, every search query
and the numbered evidence snippets), then the JSON result, its warnings and any integrity
violations. `--with-market` runs the market agent first and gives the competitor agent its
compact market context. Keys and other settings are never printed.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.base import AgentContext  # noqa: E402
from agents.competitor_analysis_agent import CompetitorAnalysisAgent, competitor_evidence  # noqa: E402
from agents.competitor_checks import DROPPED_CANDIDATE  # noqa: E402
from agents.evidence import build_evidence  # noqa: E402
from agents.extraction_agent import extract_idea  # noqa: E402
from agents.integrity import check_competitor_integrity, check_market_integrity  # noqa: E402
from agents.market_opportunity_agent import MarketOpportunityAgent  # noqa: E402
from agents.market_size import market_evidence  # noqa: E402
from agents.web_search_agent import run_web_search  # noqa: E402
from config import get_settings, setup_logging  # noqa: E402
from models.schemas import EvidenceItem, ExtractedIdea, IdeaSubmission, SearchBundle  # noqa: E402
from utils.errors import AppError  # noqa: E402

AGENTS = ("market", "competitor")
NO_TARGETED_SEARCH = "- none: not run, or every targeted search failed (see the warnings)"
MARKET_EVIDENCE_TITLE = "Evidence used by the market agent:"
COMPETITOR_EVIDENCE_TITLE = "Evidence used by the competitor agent:"


def keys_present() -> bool:
    settings = get_settings()
    missing = []
    if not settings.llm_api_key or not settings.llm_model:
        missing.append("LLM_API_KEY and LLM_MODEL")
    if not settings.tavily_api_key:
        missing.append("TAVILY_API_KEY")
    if missing:
        print("This script makes real API calls and needs real keys in the project root .env.")
        print("Missing: " + "; ".join(missing))
        return False
    return True


def load_submission(path: Path) -> IdeaSubmission | None:
    try:
        return IdeaSubmission(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        print(f"Could not read {path} as an idea ({type(exc).__name__}).")
        return None


def print_idea(idea: ExtractedIdea) -> None:
    print("Idea:")
    print(f"- Title: {idea.idea_title}")
    print(f"- Problem: {idea.problem}")
    print(f"- Solution: {idea.solution}")
    print(f"- Industry: {idea.industry}")
    print(f"- Target customers: {'; '.join(idea.target_customers)}")
    print(f"- Key features: {'; '.join(idea.key_features)}")


def print_searches(title: str, bundle: SearchBundle | None) -> None:
    print(title)
    if bundle is None:
        print(NO_TARGETED_SEARCH)
        return
    for section in bundle.sections:
        outcome = section.error if section.error and not section.results else f"{len(section.results)} results"
        print(f"- {section.label}: {section.query} ({outcome})")


def print_evidence(evidence: list[EvidenceItem], title: str = MARKET_EVIDENCE_TITLE) -> None:
    print(title)
    for item in evidence:
        print(f"[{item.id}] {item.title}")
        print(f"    URL: {item.url or 'none (search summary, not a source)'}")
        print(f"    Section: {item.section_label}")
        print(f"    Text: {item.snippet}")


def print_audit(context: AgentContext) -> None:
    """What the agent saw, so every sourced claim can be checked against its snippet by hand."""
    if context.idea is not None:
        print_idea(context.idea)
        print()
    if context.search is None:
        return
    print_searches("Standard searches:", context.search)
    print_searches("Targeted market-size searches:", context.market_search)
    print()
    print_evidence(market_evidence(context.search, context.market_search, context.idea))
    print()


def print_candidates(context: AgentContext) -> None:
    """Phase A: the candidates kept, with the pages that name them, and those dropped and why."""
    standard = {item.id.upper(): item.url for item in build_evidence(context.search)} if context.search else {}
    print("Phase A candidates kept:")
    for candidate in context.competitor_candidates:
        pages = ", ".join(standard[sid.upper()] for sid in candidate.source_ids if sid.upper() in standard)
        print(f"- {candidate.name} ({candidate.type}, {candidate.basis}): {pages or 'named in the submission'}")
    if not context.competitor_candidates:
        print("- none")
    dropped = [warning.split(DROPPED_CANDIDATE, 1)[1].strip() for warning in context.warnings if DROPPED_CANDIDATE in warning]
    print("Phase A candidates dropped:")
    print("\n".join(f"- {reason}" for reason in dropped) or "- none")


def print_competitor_audit(context: AgentContext, market_note: str) -> None:
    if context.idea is not None:
        print_idea(context.idea)
        print()
    print(market_note)
    print()
    if context.search is None:
        return
    print_searches("Standard searches:", context.search)
    print()
    print_candidates(context)
    print()
    print_searches("Targeted competitor searches:", context.competitor_search)
    print()
    evidence = competitor_evidence(context.search, context.competitor_search, context.competitor_candidates)
    print_evidence(evidence, COMPETITOR_EVIDENCE_TITLE)
    print()


def add_market_context(context: AgentContext) -> str:
    """--with-market: run the market agent first. If it fails, the competitor agent runs without
    market context, as Section 9.1 plans for the integrated pipeline."""
    try:
        MarketOpportunityAgent().run(context)
    except AppError as exc:
        context.market = None
        return f"Market context: none; the market agent stopped ({exc.user_message})"
    return f"Market context: from the market agent ({context.market.industry_overview.market_category})"


def print_result(result_json: str, warnings: list[str], violations: list[str]) -> int:
    print("Result:")
    print(result_json)
    print("\nWarnings:")
    print("\n".join(f"- {warning}" for warning in warnings) or "- none")
    if violations:
        print("\nIntegrity check: violations found")
        print("\n".join(f"- {problem}" for problem in violations))
        return 1
    print("\nIntegrity check: no violations")
    return 0


def run_market(context: AgentContext) -> int:
    try:
        MarketOpportunityAgent().run(context)
    except AppError as exc:
        print_audit(context)
        print(f"Stopped: {exc.user_message} ({exc.code})")
        return 1
    print_audit(context)
    evidence = market_evidence(context.search, context.market_search, context.idea)
    return print_result(
        context.market.model_dump_json(indent=2), context.warnings, check_market_integrity(context.market, evidence)
    )


def run_competitor(context: AgentContext, with_market: bool) -> int:
    market_note = add_market_context(context) if with_market else "Market context: none (not requested)"
    try:
        CompetitorAnalysisAgent().run(context)
    except AppError as exc:
        print_competitor_audit(context, market_note)
        print(f"Stopped: {exc.user_message} ({exc.code})")
        return 1
    print_competitor_audit(context, market_note)
    evidence = competitor_evidence(context.search, context.competitor_search, context.competitor_candidates)
    return print_result(
        context.competitors.model_dump_json(indent=2),
        context.warnings,
        check_competitor_integrity(context.competitors, evidence),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one Milestone 2 agent on a test idea.")
    parser.add_argument("agent", choices=AGENTS)
    parser.add_argument("--idea", required=True, type=Path, help="path to a test idea JSON file")
    parser.add_argument(
        "--with-market",
        action="store_true",
        help="competitor only: run the market agent first and use its compact market context",
    )
    args = parser.parse_args(argv)

    if not keys_present():
        return 1
    submission = load_submission(args.idea)
    if submission is None:
        return 1

    context = AgentContext(submission=submission)
    try:
        context.idea = extract_idea(submission)
        context.search = run_web_search(context.idea)
    except AppError as exc:
        if args.agent == "market":
            print_audit(context)
        else:
            print_competitor_audit(context, "Market context: none")
        print(f"Stopped: {exc.user_message} ({exc.code})")
        return 1
    if args.agent == "market":
        return run_market(context)
    return run_competitor(context, args.with_market)


if __name__ == "__main__":
    setup_logging()
    # Search text can hold characters the console cannot show; print "?" rather than crash
    # after the API calls have been paid for.
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())

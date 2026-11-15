import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pytest

from agents import advisor_agent
from orchestrator import STRATEGY_ONLY_STAGES, run_pipeline
from tests.m3_fakes import full_result
from tests.pipeline_fakes import PIPELINE_SUBMISSION
from tests.test_m3_no_search import Replies


def main() -> None:
    mp = pytest.MonkeyPatch()
    try:
        prior, _ = full_result(mp)
        Replies(mp)
        result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=prior)
        print(result.status, len(result.executive_summary), len(result.verify_next), len(result.notices))
        facts, headline = advisor_agent.context_facts(result)
        print(len(facts), len(headline))
        for section in [[], ["market"], ["risks"], ["mvp", "gtm"], ["evidence"]]:
            ctx = advisor_agent.build_context(result, section)
            print(section, len(ctx.text), len(ctx.digest.facts), ctx.expanded, ctx.missing)
        ctx = advisor_agent.build_context(result, ["market"])
        print(ctx.text[:6000])
        print(advisor_agent.suggestions(result))
        base = advisor_agent.build_context(prior, ["mvp"])
        print(base.answerable, base.missing, advisor_agent.suggestions(prior))
    finally:
        mp.undo()


main()

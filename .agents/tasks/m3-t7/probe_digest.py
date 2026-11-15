import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pytest

from agents import mvp_agent, swot_risk_agent
from agents.mvp_agent import recommend_mvp
from agents.strategy_context import build_digest
from agents.swot_risk_agent import analyse_swot
from tests.fakes import make_sequence
from tests.m3_fakes import full_result
from tests.test_m3_mvp_agent import draft as mvp_draft
from tests.test_m3_swot_agent import draft as swot_draft

with pytest.MonkeyPatch.context() as mp:
    for name, value in {"TAVILY_API_KEY": "t", "LLM_API_KEY": "l", "LLM_MODEL": "m"}.items():
        mp.setenv(name, value)
    mp.delenv("GROQ_API_KEY", raising=False)
    base, _ = full_result(mp)
    mp.setattr(swot_risk_agent, "generate_json", make_sequence(json.dumps(swot_draft())))
    swot = analyse_swot(base.idea, None, base.market, base.competitors)
    mp.setattr(mvp_agent, "generate_json", make_sequence(json.dumps(mvp_draft())))
    mvp = recommend_mvp(base.idea, None, base.market, base.competitors, swot)
    digest = build_digest(base.idea, None, base.market, base.competitors, swot=swot, mvp=mvp)
    print(digest.text)
    print("TITLE", base.idea.idea_title)
    print("CUSTOMERS", base.idea.target_customers)
    print("SEGMENTS", [segment.name for segment in base.market.segments])
    print("PRIORITY", base.market.priority_segment)
    print("MVP IDS", [(f.id, f.name, f.tier) for f in mvp.features])
    print("RISK IDS", [(r.id, r.title) for r in swot.risks])

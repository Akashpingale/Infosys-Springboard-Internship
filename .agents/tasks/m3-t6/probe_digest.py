import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

os.environ["TAVILY_API_KEY"] = "test-tavily-key"
os.environ["LLM_API_KEY"] = "test-llm-key"
os.environ["LLM_MODEL"] = "test-model"
os.environ.pop("GROQ_API_KEY", None)

import pytest

from agents import swot_risk_agent
from agents.strategy_context import build_digest
from tests.fakes import make_sequence
from tests.m3_fakes import full_result
from tests.test_m3_swot_agent import draft

mp = pytest.MonkeyPatch()
result, _ = full_result(mp)
mp.setattr(swot_risk_agent, "generate_json", make_sequence(json.dumps(draft())))
swot = swot_risk_agent.analyse_swot(result.idea, None, result.market, result.competitors)
print("key_features", result.idea.key_features)
digest = build_digest(result.idea, result.constraints, result.market, result.competitors, swot=swot)
for fact in digest.facts:
    print(fact.ref, fact.kind, fact.basis, fact.sources, fact.text[:110])
print(len(digest.text), digest.max_chars)
for risk in swot.risks:
    print(risk.id, risk.title, risk.category)
mp.undo()

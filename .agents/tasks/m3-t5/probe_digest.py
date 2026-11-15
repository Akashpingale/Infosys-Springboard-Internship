import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pytest

from agents.strategy_context import build_digest
from tests.m3_fakes import full_result


class MP:
    def __init__(self):
        self.m = pytest.MonkeyPatch()

    def setattr(self, *a, **k):
        self.m.setattr(*a, **k)

    def setenv(self, *a, **k):
        self.m.setenv(*a, **k)


import os
os.environ["TAVILY_API_KEY"] = "test-tavily-key"
os.environ["LLM_API_KEY"] = "test-llm-key"
os.environ["LLM_MODEL"] = "test-model"
os.environ.pop("GROQ_API_KEY", None)
mp = pytest.MonkeyPatch()
result, _ = full_result(mp)
digest = build_digest(result.idea, result.constraints, result.market, result.competitors)
for fact in digest.facts:
    print(fact.ref, fact.kind, fact.basis, fact.sources, fact.text[:90])
print(len(digest.text))
mp.undo()

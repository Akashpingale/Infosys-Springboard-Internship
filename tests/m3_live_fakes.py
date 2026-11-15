import json
import re
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from agents import advisor_agent, gtm_agent, mvp_agent, swot_risk_agent
from agents.advisor_agent import QUESTION_CLOSE, QUESTION_OPEN, route_question, section_of
from tests.fakes import make_sequence
from tests.pipeline_fakes import use_full_pipeline
from tests.test_m3_gtm_agent import draft as gtm_draft
from tests.test_m3_mvp_agent import draft as mvp_draft
from tests.test_m3_swot_agent import draft as swot_draft
from utils import llm_client, search_client

MSG_BLOCKED = "A fake run never calls a provider."
FAKE_ANSWER = "This answer comes from the fake Advisor and rests on one finding in your results."
FAKE_FOLLOW_UP = "What should I check first?"
_FACT_REF = re.compile(r"^\[([A-Z]+\.\d+)\]", re.MULTILINE)


def blocked(*args, **kwargs):
    raise RuntimeError(MSG_BLOCKED)


def strategy_replies() -> dict:
    return {swot_risk_agent: swot_draft(), mvp_agent: mvp_draft(), gtm_agent: gtm_draft()}


def advisor_reply(system: str, user: str) -> str:
    question = user.split(QUESTION_OPEN, 1)[-1].split(QUESTION_CLOSE, 1)[0]
    sections = route_question(question)
    if not sections:
        return json.dumps({"in_scope": False, "paragraphs": [], "follow_ups": [], "needs_more_evidence": False})
    refs = _FACT_REF.findall(user)
    chosen = next((ref for ref in refs if section_of(ref) in sections), refs[0] if refs else None)
    paragraph = {"text": FAKE_ANSWER, "basis": "ai_interpretation", "refs": [chosen] if chosen else []}
    return json.dumps({"in_scope": True, "paragraphs": [paragraph], "follow_ups": [FAKE_FOLLOW_UP], "needs_more_evidence": False})


@contextmanager
def fake_clients(*, analysis: bool = False, strategy: bool = False, advisor: bool = False) -> Iterator[None]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(llm_client.genai, "Client", blocked)
        monkeypatch.setattr(search_client.requests, "post", blocked)
        if analysis:
            use_full_pipeline(monkeypatch)
        if strategy:
            for module, draft in strategy_replies().items():
                monkeypatch.setattr(module, "generate_json", make_sequence(json.dumps(draft)))
        if advisor:
            monkeypatch.setattr(advisor_agent, "generate_json", lambda system, user: advisor_reply(system, user))
        yield

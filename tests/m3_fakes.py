import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

import orchestrator
from agents.base import AgentContext
from models.schemas import (
    GtmResult,
    MvpResult,
    PipelineResult,
    Positioning,
    StrategyConstraints,
    SwotItem,
    SwotRiskResult,
)
from orchestrator import FULL_STAGES, STAGE_GTM, STAGE_MVP, STAGE_SWOT, STRATEGY_ONLY_STAGES, run_pipeline
from tests.fakes import FakeHTTPResponse
from tests.pipeline_fakes import PIPELINE_SUBMISSION, PipelineFakes, use_full_pipeline
from utils import deadline, groq_client, llm_client

SWOT = SwotRiskResult(
    summary="Synthetic SWOT for the plumbing tests.",
    strengths=[SwotItem(id="S1", text="Synthetic strength.", basis="ai_interpretation", based_on=["IDEA.1"])],
)
MVP = MvpResult(
    summary="Synthetic MVP for the plumbing tests.",
    capacity_person_months=6.0,
    planned_person_months=4.0,
    constraints_used=StrategyConstraints(team_size=2, months_to_mvp=3),
)
GTM = GtmResult(
    summary="Synthetic go-to-market plan for the plumbing tests.",
    positioning=Positioning(
        target_segment="Smallholder farmers",
        for_whom="Smallholder farmers",
        problem="Late disease diagnosis",
        category="Crop diagnosis app",
        key_benefit="Early warnings",
        alternative="Extension officers",
        differentiator="Local language advice",
        statement="For smallholder farmers who spot diseases late, a crop diagnosis app gives early warnings.",
        differentiator_status="hypothesis",
        basis="ai_interpretation",
    ),
)
CONSTRAINTS = StrategyConstraints(team_size=2, months_to_mvp=4, budget_level="bootstrapped")
STRATEGY_KEYS = (STAGE_SWOT, STAGE_MVP, STAGE_GTM)
FIELDS = {STAGE_SWOT: "swot", STAGE_MVP: "mvp", STAGE_GTM: "gtm"}
VALUES = {STAGE_SWOT: SWOT, STAGE_MVP: MVP, STAGE_GTM: GTM}
SYSTEM = "Synthetic system prompt."
USER = "Synthetic user prompt."
GROQ_TEST_KEY = "test-" + "groq-" + "placeholder-value"


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def use_clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(deadline, "clock", clock)
    return clock


@dataclass
class FakeStrategyAgent:
    name: str
    value: Any = None
    error: Exception | None = None
    before: Callable[[], None] | None = None
    seen: list[dict[str, Any]] = field(default_factory=list)

    def run(self, context: AgentContext) -> AgentContext:
        self.seen.append({
            "idea": context.idea,
            "market": context.market,
            "competitors": context.competitors,
            "swot": context.swot,
            "mvp": context.mvp,
            "gtm": context.gtm,
            "constraints": context.constraints,
            "time_left": deadline.time_left(),
        })
        if self.before is not None:
            self.before()
        if self.error is not None:
            raise self.error
        setattr(context, FIELDS[self.name], VALUES[self.name] if self.value is None else self.value)
        return context

    @property
    def calls(self) -> int:
        return len(self.seen)


def use_fake_strategy(monkeypatch: pytest.MonkeyPatch, **agents: FakeStrategyAgent) -> dict[str, FakeStrategyAgent]:
    fakes = {key: agents.get(FIELDS[key]) or FakeStrategyAgent(key) for key in STRATEGY_KEYS}
    for stage in STRATEGY_ONLY_STAGES:
        monkeypatch.setattr(stage, "agent", fakes[stage.name])
    return fakes


def gate_agent(name: str, gate: threading.Event, reached: threading.Event) -> FakeStrategyAgent:
    def hold() -> None:
        reached.set()
        gate.wait(10)

    return FakeStrategyAgent(name, before=hold)


def full_result(monkeypatch: pytest.MonkeyPatch, **options: Any) -> tuple[PipelineResult, PipelineFakes]:
    fakes = use_full_pipeline(monkeypatch, **options)
    return run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES), fakes


def outside_calls(fakes: PipelineFakes) -> int:
    return len(fakes.extraction_llm.calls) + len(fakes.search.calls) + fakes.analysis_calls()


class GeminiCapture:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.configs: list[Any] = []

    def __call__(self, **kwargs: Any) -> "GeminiCapture":
        return self

    @property
    def models(self) -> "GeminiCapture":
        return self

    def generate_content(self, **kwargs: Any) -> Any:
        self.configs.append(kwargs["config"])
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return SimpleNamespace(text=self.outcome)

    def close(self) -> None:
        pass


class GroqCapture:
    def __init__(self, content: str) -> None:
        self.content = content
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, url: str, headers: Any = None, json: Any = None, timeout: Any = None, **kw: Any) -> Any:
        self.bodies.append(json)
        return FakeHTTPResponse(200, {"choices": [{"index": 0, "message": {"content": self.content}, "finish_reason": "stop"}]})


def use_capturing_providers(
    monkeypatch: pytest.MonkeyPatch, gemini_outcome: Any, groq_content: str = "{}"
) -> tuple[GeminiCapture, GroqCapture]:
    gemini = GeminiCapture(gemini_outcome)
    groq = GroqCapture(groq_content)
    monkeypatch.setenv("GROQ_API_KEY", GROQ_TEST_KEY)
    monkeypatch.setattr(llm_client.genai, "Client", gemini)
    monkeypatch.setattr(groq_client.requests, "post", groq)
    monkeypatch.setattr(llm_client, "time", SimpleNamespace(sleep=lambda seconds: None))
    return gemini, groq


def gemini_rate_limit() -> Exception:
    return llm_client.genai_errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )


def calling_llm(name: str, replies: list[str]) -> FakeStrategyAgent:
    def call() -> None:
        replies.append(llm_client.generate_json(SYSTEM, USER))

    return FakeStrategyAgent(name, before=call)


def strategy_stage_labels() -> dict[str, str]:
    return {stage.name: stage.label for stage in orchestrator.STRATEGY_ONLY_STAGES}

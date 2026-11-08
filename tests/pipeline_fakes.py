"""Fakes for the Task 3 pipeline tests: one agritech idea through all four stages.

The LLM and the searches are replaced at the same seams the Milestone 1, Task 1 and Task 2 tests
use, so the real stages, agents, guards and integrity checks all run and nothing touches the
network. The standard search is the Task 2 bundle; PIPELINE_MARKET_REPLY cites its evidence:
S1 market report, S2 Plantix, S4 CropSense and S5 farmer survey.
"""

import copy
import json
from dataclasses import dataclass
from typing import Any, Callable

import pytest

import orchestrator
from agents import competitor_analysis_agent as competitor_agent
from agents import extraction_agent
from agents import market_opportunity_agent as market_agent
from agents import market_size
from models.schemas import ExtractedIdea, SearchBundle
from tests.fakes import LLM_REPLY_OK, VALID_EXTRACTION, make_sequence
from tests.m2_fakes import (
    COMPETITOR_SEARCH,
    COMPETITOR_SUBMISSION,
    COMPETITOR_TARGETED,
    NO_MARKET_SIZE_RESULTS,
    analysis_draft,
    as_reply,
    candidate_draft,
)

PIPELINE_SUBMISSION = COMPETITOR_SUBMISSION
PIPELINE_SEARCH = COMPETITOR_SEARCH
IDEA = ExtractedIdea(**VALID_EXTRACTION)

PIPELINE_MARKET_REPLY = {
    "industry_overview": {
        "summary": "AI crop disease detection is a growing part of AgriTech.",
        "market_category": "AI crop disease detection",
        "developments": [
            {
                "text": "A new startup launched drone-based disease scouting for farming cooperatives.",
                "basis": "sourced",
                "source_ids": ["S4"],
            }
        ],
    },
    "market_demand": {
        "summary": "Small farmers lose crops when diseases are spotted late.",
        "demand_evidence": [
            {
                "text": "Most small farmers say they lose crops because diseases are spotted late.",
                "basis": "sourced",
                "source_ids": ["S5"],
            }
        ],
        "customer_problems": [
            {"text": "Diseases are spotted too late to save the crop.", "basis": "sourced", "source_ids": ["S5"]}
        ],
        "interest_signals": [
            {
                "text": "Photo-based diagnosis apps already reach farmers in their own languages.",
                "basis": "ai_interpretation",
                "source_ids": ["S2"],
            }
        ],
    },
    "market_size": {
        "tam": {
            "value": "USD 1.8 billion",
            "status": "sourced",
            "source_ids": ["S1"],
            "note": "AI crop disease detection market, 2025",
            "scope": "idea_market",
        },
        "sam": {"value": None, "status": "unavailable", "source_ids": [], "note": "No figure for India was found"},
        "som": {"value": None, "status": "unavailable", "source_ids": [], "note": None},
    },
    "broader_markets": [],
    "trends": [
        {"trend": "Drone-based disease scouting", "category": "technology", "basis": "sourced", "source_ids": ["S4"]}
    ],
    "segments": [
        {
            "name": "Smallholder farmers",
            "description": "Farmers on small plots who lose crops to late diagnosis.",
            "segmentation_basis": "business_type",
            "needs": ["Early disease warnings"],
            "pain_points": [{"text": "Crops lost to late diagnosis", "basis": "sourced", "source_ids": ["S5"]}],
            "source_ids": ["S5"],
        },
        {
            "name": "Farming cooperatives",
            "description": "Groups that advise many member farmers.",
            "segmentation_basis": "business_type",
            "needs": ["Scouting across many fields"],
            "pain_points": [{"text": "Few experts per member", "basis": "assumption", "source_ids": []}],
            "source_ids": ["S4"],
        },
    ],
    "priority_segment": {
        "segment_name": "Smallholder farmers",
        "rationale": "They feel the crop losses most directly.",
        "risks": ["Free diagnosis apps already serve them"],
    },
    "opportunities": [
        {"text": "Treatment advice in local languages", "basis": "ai_interpretation", "source_ids": ["S2"]}
    ],
    "limitations": [
        {"text": "A free photo diagnosis app is already available", "basis": "sourced", "source_ids": ["S2"]}
    ],
    "data_quality": {"evidence_level": "limited", "notes": ["No market figure for India was found."]},
}

# Text that appears only in the full market result, never in the compact market context.
MARKET_ONLY_TEXT = ("Free diagnosis apps already serve them", "Treatment advice in local languages")

# The compact market context line the Phase C prompt carries when the market stage succeeded.
MARKET_CONTEXT_LINE = (
    "Market context: category: AI crop disease detection; segments: Smallholder farmers, Farming "
    "cooperatives; priority segment: Smallholder farmers (They feel the crop losses most directly.); "
    "trends: Drone-based disease scouting"
)
NO_MARKET_CONTEXT_LINE = "Market context: none"


def market_reply(draft: dict | None = None) -> str:
    return json.dumps(PIPELINE_MARKET_REPLY if draft is None else draft)


def market_draft() -> dict:
    return copy.deepcopy(PIPELINE_MARKET_REPLY)


def competitor_replies() -> tuple[str, str]:
    """Phase A then Phase C, as in the Task 2 tests."""
    return as_reply(candidate_draft()), as_reply(analysis_draft())


def evidence_urls(*bundles: SearchBundle | None) -> set[str]:
    return {
        result.url
        for bundle in (PIPELINE_SEARCH, COMPETITOR_TARGETED, *bundles)
        if bundle is not None
        for section in bundle.sections
        for result in section.results
    }


@dataclass
class PipelineFakes:
    """The fakes behind one run, so tests can check what each stage called."""

    extraction_llm: Callable[..., Any]
    search: Callable[..., Any]
    market_search: Callable[..., Any]
    market_llm: Callable[..., Any]
    competitor_search: Callable[..., Any]
    competitor_llm: Callable[..., Any]

    def phase_c_prompt(self) -> str:
        """The user prompt of the competitor agent's analysis call (the last LLM call)."""
        return self.competitor_llm.calls[-1][0][1]

    def analysis_calls(self) -> int:
        return sum(
            len(fake.calls)
            for fake in (self.market_search, self.market_llm, self.competitor_search, self.competitor_llm)
        )


def use_full_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    extraction: tuple = (LLM_REPLY_OK,),
    search: tuple = (PIPELINE_SEARCH,),
    market_search: tuple = (NO_MARKET_SIZE_RESULTS,),
    market_llm: tuple | None = None,
    competitor_search: tuple = (COMPETITOR_TARGETED,),
    competitor_llm: tuple | None = None,
) -> PipelineFakes:
    """Replace every outside call of the four stages. Exceptions are raised, values returned."""
    fakes = PipelineFakes(
        extraction_llm=make_sequence(*extraction),
        search=make_sequence(*search),
        market_search=make_sequence(*market_search),
        market_llm=make_sequence(*(market_llm or (market_reply(),))),
        competitor_search=make_sequence(*competitor_search),
        competitor_llm=make_sequence(*(competitor_llm or competitor_replies())),
    )
    monkeypatch.setattr(extraction_agent, "generate_json", fakes.extraction_llm)
    monkeypatch.setattr(orchestrator, "run_web_search", fakes.search)
    monkeypatch.setattr(market_size, "run_queries", fakes.market_search)
    monkeypatch.setattr(market_agent, "generate_json", fakes.market_llm)
    monkeypatch.setattr(competitor_agent, "run_queries", fakes.competitor_search)
    monkeypatch.setattr(competitor_agent, "generate_json", fakes.competitor_llm)
    return fakes

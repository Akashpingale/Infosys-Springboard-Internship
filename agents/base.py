"""The contract every agent follows. Future agents implement this and nothing more."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from models.schemas import (
    CompetitorAnalysisResult,
    CompetitorCandidate,
    ExtractedIdea,
    IdeaSubmission,
    MarketOpportunityResult,
    SearchBundle,
)


@dataclass
class AgentContext:
    """Carried from one agent to the next: the input, what has been produced so far,
    and anything the user should be told about a degraded result."""

    submission: IdeaSubmission
    idea: ExtractedIdea | None = None
    search: SearchBundle | None = None
    warnings: list[str] = field(default_factory=list)
    market: MarketOpportunityResult | None = None
    # The market agent's own targeted market-size searches, kept so the evidence can be audited.
    market_search: SearchBundle | None = None
    # Competitor Analysis Agent (Task 2): its result, the Phase A candidates it kept and its
    # targeted searches, so the merged evidence can be rebuilt and audited.
    competitors: CompetitorAnalysisResult | None = None
    competitor_candidates: list[CompetitorCandidate] = field(default_factory=list)
    competitor_search: SearchBundle | None = None


@runtime_checkable
class Agent(Protocol):
    """An agent reads the context, adds its own output, and returns the context."""

    name: str

    def run(self, context: AgentContext) -> AgentContext: ...

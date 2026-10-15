"""The contract every agent follows. Future agents implement this and nothing more."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from models.schemas import ExtractedIdea, IdeaSubmission, SearchBundle


@dataclass
class AgentContext:
    """Carried from one agent to the next: the input, what has been produced so far,
    and anything the user should be told about a degraded result."""

    submission: IdeaSubmission
    idea: ExtractedIdea | None = None
    search: SearchBundle | None = None
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class Agent(Protocol):
    """An agent reads the context, adds its own output, and returns the context."""

    name: str

    def run(self, context: AgentContext) -> AgentContext: ...

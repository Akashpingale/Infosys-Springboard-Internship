import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from config import get_settings
from models.schemas import NonEmptyStr, StrategySourceKey
from models.strategy_drafts import ADVISOR_BASES

CHAT_ROLES = ("user", "assistant")
CHAT_STATUSES = ("ok", "out_of_scope", "no_evidence")
ADVISOR_SECTIONS = ("market", "competitors", "swot", "risks", "mvp", "gtm", "evidence", "general")
CHAT_PARAGRAPH_MAX = 600
CHAT_PARAGRAPHS_MAX = 5
CHAT_FOLLOW_UP_MAX = 120
CHAT_FOLLOW_UPS_MAX = 3
CHAT_SUGGESTIONS_MAX = 4

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


class ChatParagraph(BaseModel):
    text: NonEmptyStr = Field(max_length=CHAT_PARAGRAPH_MAX)
    basis: Literal[ADVISOR_BASES]
    sections: list[Literal[ADVISOR_SECTIONS]] = Field(default_factory=list)
    sources: list[StrategySourceKey] = Field(default_factory=list)


class ChatMessage(BaseModel):
    id: NonEmptyStr
    role: Literal[CHAT_ROLES]
    created_at: str
    text: str | None = None
    paragraphs: list[ChatParagraph] = Field(default_factory=list, max_length=CHAT_PARAGRAPHS_MAX)
    follow_ups: list[Annotated[NonEmptyStr, Field(max_length=CHAT_FOLLOW_UP_MAX)]] = Field(default_factory=list, max_length=CHAT_FOLLOW_UPS_MAX)
    status: Literal[CHAT_STATUSES] = "ok"
    used_sections: list[Literal[ADVISOR_SECTIONS]] = Field(default_factory=list)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str

    @field_validator("message", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return _CONTROL_CHARACTERS.sub("", value).strip()

    @model_validator(mode="after")
    def _within_limits(self) -> "ChatRequest":
        limit = get_settings().chat_max_message_chars
        if not self.message or len(self.message) > limit:
            raise ValueError(f"Write a question of up to {limit} characters.")
        return self


class ChatLimits(BaseModel):
    max_message_chars: int
    max_user_turns: int


class ChatThread(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list, max_length=CHAT_SUGGESTIONS_MAX)
    available_sections: list[Literal[ADVISOR_SECTIONS]] = Field(default_factory=list)
    remaining_turns: int = Field(ge=0)
    limits: ChatLimits


class ChatReply(BaseModel):
    message: ChatMessage
    remaining_turns: int = Field(ge=0)

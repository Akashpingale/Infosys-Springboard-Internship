"""Shared data models and validation limits. Backend, UI and tests import from here."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

IDEA_MIN = 30
IDEA_MAX = 2000
IDEA_MIN_WORDS = 3
INDUSTRY_MIN = 2
INDUSTRY_MAX = 60
CUSTOMERS_MIN = 3
CUSTOMERS_MAX = 300
DETAILS_MAX = 1500

IDEA_TITLE_MAX = 80
TARGET_CUSTOMERS_RANGE = (1, 5)
KEY_FEATURES_RANGE = (3, 6)
SNIPPET_MAX = 300

INDUSTRIES = [
    "Agriculture / AgriTech",
    "Healthcare / HealthTech",
    "Education / EdTech",
    "Finance / FinTech",
    "E-commerce / Retail",
    "Food & Beverage",
    "Travel & Hospitality",
    "Logistics & Supply Chain",
    "Real Estate / PropTech",
    "Energy & Climate",
    "Entertainment & Media",
    "SaaS / B2B Software",
    "Other",
]

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class IdeaSubmission(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    idea_description: str = Field(min_length=IDEA_MIN, max_length=IDEA_MAX)
    industry: str = Field(min_length=INDUSTRY_MIN, max_length=INDUSTRY_MAX)
    target_customers: str = Field(min_length=CUSTOMERS_MIN, max_length=CUSTOMERS_MAX)
    relevant_details: str | None = Field(default=None, max_length=DETAILS_MAX)

    @field_validator("idea_description")
    @classmethod
    def _needs_enough_words(cls, value: str) -> str:
        if len(value.split()) < IDEA_MIN_WORDS:
            raise ValueError(f"Please describe your idea in at least {IDEA_MIN_WORDS} words.")
        return value

    @field_validator("relevant_details")
    @classmethod
    def _blank_details_to_none(cls, value: str | None) -> str | None:
        return value or None


class ExtractedIdea(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    idea_title: NonEmptyStr = Field(max_length=IDEA_TITLE_MAX)
    problem: NonEmptyStr
    solution: NonEmptyStr
    target_customers: list[NonEmptyStr] = Field(
        min_length=TARGET_CUSTOMERS_RANGE[0], max_length=TARGET_CUSTOMERS_RANGE[1]
    )
    industry: NonEmptyStr
    key_features: list[NonEmptyStr] = Field(
        min_length=KEY_FEATURES_RANGE[0], max_length=KEY_FEATURES_RANGE[1]
    )


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = Field(max_length=SNIPPET_MAX)
    score: float | None = Field(default=None, ge=0, le=1)


class SearchSection(BaseModel):
    label: str
    query: str
    answer: str | None = None
    results: list[SearchResult] = Field(default_factory=list)
    error: str | None = None


class SearchBundle(BaseModel):
    sections: list[SearchSection] = Field(default_factory=list)
    total_results: int = Field(default=0, ge=0)
    queries_failed: int = Field(default=0, ge=0)


class StageError(BaseModel):
    stage: str
    code: str
    message: str


class PipelineResult(BaseModel):
    status: Literal["complete", "partial", "failed"]
    idea: ExtractedIdea | None = None
    search: SearchBundle | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[StageError] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)

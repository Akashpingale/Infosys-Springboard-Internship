from typing import Literal

from pydantic import BaseModel, Field

from models.schemas import (
    CHANNEL_KINDS,
    CHANNEL_ROLES,
    COST_LEVELS,
    EFFORT_SIZES,
    FEATURE_ORIGINS,
    LAUNCH_PHASE_NAMES,
    RISK_CATEGORIES,
    RISK_CONFIDENCES_DRAFT,
    RISK_LEVELS,
    SPEEDS,
    STRATEGY_BASES,
)

ADVISOR_BASES = ("sourced", "ai_interpretation", "assumption")

StrategyDraftBasis = Literal[STRATEGY_BASES]


class SwotItemDraft(BaseModel):
    text: str
    why_it_matters: str = ""
    basis: StrategyDraftBasis
    based_on: list[str] = Field(default_factory=list)


class RiskDraft(BaseModel):
    category: Literal[RISK_CATEGORIES]
    title: str
    description: str
    likelihood: Literal[RISK_LEVELS]
    impact: Literal[RISK_LEVELS]
    mitigation: str
    early_warning_signal: str
    confidence: Literal[RISK_CONFIDENCES_DRAFT] = "low"
    basis: StrategyDraftBasis
    based_on: list[str] = Field(default_factory=list)


class SwotRiskDraft(BaseModel):
    strengths: list[SwotItemDraft] = Field(default_factory=list)
    weaknesses: list[SwotItemDraft] = Field(default_factory=list)
    opportunities: list[SwotItemDraft] = Field(default_factory=list)
    threats: list[SwotItemDraft] = Field(default_factory=list)
    risks: list[RiskDraft] = Field(default_factory=list)
    summary: str = ""
    limitations: list[str] = Field(default_factory=list)


class MvpFeatureDraft(BaseModel):
    name: str
    description: str = ""
    user_problem: str = ""
    origin: Literal[FEATURE_ORIGINS]
    essential: bool = False
    customer_need: int
    differentiation: int
    feasibility: int
    effort: Literal[EFFORT_SIZES]
    rationale: str = ""
    mitigates: list[str] = Field(default_factory=list)
    basis: StrategyDraftBasis
    based_on: list[str] = Field(default_factory=list)


class MvpMetricDraft(BaseModel):
    name: str
    how_to_measure: str
    suggested_target: str | None = None
    basis: StrategyDraftBasis


class MvpDraft(BaseModel):
    features: list[MvpFeatureDraft] = Field(default_factory=list)
    success_metrics: list[MvpMetricDraft] = Field(default_factory=list)
    summary: str = ""
    limitations: list[str] = Field(default_factory=list)


class PositioningDraft(BaseModel):
    target_segment: str
    for_whom: str
    problem: str
    category: str
    key_benefit: str
    alternative: str
    differentiator: str
    basis: StrategyDraftBasis
    based_on: list[str] = Field(default_factory=list)


class ChannelDraft(BaseModel):
    name: str
    kind: Literal[CHANNEL_KINDS]
    role: Literal[CHANNEL_ROLES]
    fit_rationale: str = ""
    audience_fit: int
    cost_level: Literal[COST_LEVELS]
    speed_to_first_result: Literal[SPEEDS]
    first_experiment: str
    success_signal: str
    uses_features: list[str] = Field(default_factory=list)
    addresses_risks: list[str] = Field(default_factory=list)
    basis: StrategyDraftBasis
    based_on: list[str] = Field(default_factory=list)


class EarlyCustomerDraft(BaseModel):
    tactic: str
    where_to_find_them: str
    offer: str
    how_to_measure: str
    basis: StrategyDraftBasis
    based_on: list[str] = Field(default_factory=list)


class LaunchPhaseDraft(BaseModel):
    name: Literal[LAUNCH_PHASE_NAMES]
    goal: str
    actions: list[str] = Field(default_factory=list)


class KeyMessageDraft(BaseModel):
    audience: str
    message: str
    proof_needed: str = ""


class GtmDraft(BaseModel):
    positioning: PositioningDraft
    channels: list[ChannelDraft] = Field(default_factory=list)
    early_customers: list[EarlyCustomerDraft] = Field(default_factory=list)
    launch_phases: list[LaunchPhaseDraft] = Field(default_factory=list)
    key_messages: list[KeyMessageDraft] = Field(default_factory=list)
    summary: str = ""
    limitations: list[str] = Field(default_factory=list)


class AdvisorParagraphDraft(BaseModel):
    text: str
    basis: Literal[ADVISOR_BASES]
    refs: list[str] = Field(default_factory=list)


class AdvisorDraft(BaseModel):
    in_scope: bool
    paragraphs: list[AdvisorParagraphDraft] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    needs_more_evidence: bool = False


STRATEGY_DRAFT_MODELS = (SwotRiskDraft, MvpDraft, GtmDraft, AdvisorDraft)

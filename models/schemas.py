"""Shared data models and validation limits. Backend, UI and tests import from here."""

import re
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

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

QUANT_STATUSES = ("sourced", "estimate_needs_verification", "unavailable")

# Market Opportunity result (KIRO_PROMPT_M2.md Section 7.1). The model, the prompt and the
# tests all read these, so an allowed value is defined once.
TREND_CATEGORIES = ("technology", "consumer", "industry", "business")
SEGMENTATION_BASES = ("demographic", "business_type", "location", "needs", "behavior")
EVIDENCE_LEVELS = ("strong", "limited", "insufficient")
SEGMENTS_RANGE = (2, 5)
# Which market a TAM, SAM or SOM figure measures: this idea's own market, or a wider one.
MARKET_SCOPES = ("idea_market", "broader_market")

# Competitor Analysis result (KIRO_PROMPT_M2.md Section 8.1).
COMPETITOR_TYPES = ("direct", "indirect", "emerging")
COMPETITOR_BASES = ("sourced", "user_provided")
INFO_COMPLETENESS = ("complete", "partial", "minimal")
CELL_STATUSES = ("evidence_found", "no_evidence_found", "unclear")
GAP_CONFIDENCES = ("low", "medium")
GAP_CONFIDENCES_DRAFT = ("low", "medium", "high")  # the LLM may say high; code caps it at medium
CANDIDATES_MAX = 8
COMPARISON_FEATURES_MAX = 8
COMPETITOR_NAME_MAX = 80

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


SEARCH_TERMS_RANGE = (3, 5)
SEARCH_TERM_MAX = 40


class SearchTermsIdea(ExtractedIdea):
    search_terms: list[str] = Field(default_factory=list)


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


class Basis(str, Enum):
    """How a claim is grounded. Subclasses str so it serialises as the bare string."""

    sourced = "sourced"
    assumption = "assumption"
    ai_interpretation = "ai_interpretation"
    user_provided = "user_provided"

    def __str__(self) -> str:
        """Print the value, not `Basis.sourced`, in str() and f-strings on every Python."""
        return self.value


class SourceRef(BaseModel):
    id: NonEmptyStr
    title: str
    url: str


class LabeledItem(BaseModel):
    text: NonEmptyStr
    basis: Basis
    source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sourced_needs_a_source(self) -> "LabeledItem":
        if self.basis is Basis.sourced and not any(sid.strip() for sid in self.source_ids):
            raise ValueError("A sourced item needs at least one source id.")
        return self


class QuantEstimate(BaseModel):
    value: str | None = None
    status: Literal["sourced", "estimate_needs_verification", "unavailable"]
    source_ids: list[str] = Field(default_factory=list)
    note: str | None = None


class EvidenceItem(BaseModel):
    id: NonEmptyStr
    title: str
    url: str = ""
    snippet: str = Field(max_length=SNIPPET_MAX)
    section_label: str


class IndustryOverview(BaseModel):
    summary: NonEmptyStr
    market_category: NonEmptyStr
    developments: list[LabeledItem] = Field(default_factory=list)


class MarketDemand(BaseModel):
    summary: NonEmptyStr
    demand_evidence: list[LabeledItem] = Field(default_factory=list)
    customer_problems: list[LabeledItem] = Field(default_factory=list)
    interest_signals: list[LabeledItem] = Field(default_factory=list)


class MarketFigure(QuantEstimate):
    """A Task 1 market-size figure. `scope` says which market it measures: `idea_market` for
    this idea's own product, customers and region, `broader_market` for a wider or different
    market such as a whole industry. Only Task 1 uses it; QuantEstimate stays unchanged."""

    scope: Literal[MARKET_SCOPES] | None = None


class MarketSize(BaseModel):
    """TAM, SAM and SOM for this idea's own market only (figures with scope `idea_market`)."""

    tam: MarketFigure
    sam: MarketFigure
    som: MarketFigure


class Trend(BaseModel):
    trend: NonEmptyStr
    category: Literal[TREND_CATEGORIES]
    basis: Basis
    source_ids: list[str] = Field(default_factory=list)


class Segment(BaseModel):
    name: NonEmptyStr
    description: NonEmptyStr
    segmentation_basis: Literal[SEGMENTATION_BASES]
    needs: list[NonEmptyStr] = Field(default_factory=list)
    pain_points: list[LabeledItem] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class PrioritySegment(BaseModel):
    segment_name: NonEmptyStr
    rationale: NonEmptyStr
    risks: list[NonEmptyStr] = Field(default_factory=list)


class DataQuality(BaseModel):
    evidence_level: Literal[EVIDENCE_LEVELS]
    notes: list[NonEmptyStr] = Field(default_factory=list)


class MarketOpportunityDraft(BaseModel):
    """What the LLM returns. Code adds `sources` and `caveats` afterwards (Section 7.2), so
    any such keys in the reply are ignored."""

    industry_overview: IndustryOverview
    market_demand: MarketDemand
    market_size: MarketSize
    # Figures for a broader or different market, kept as context and never shown as this
    # idea's TAM, SAM or SOM.
    broader_markets: list[MarketFigure] = Field(default_factory=list)
    trends: list[Trend] = Field(default_factory=list)
    segments: list[Segment] = Field(min_length=SEGMENTS_RANGE[0], max_length=SEGMENTS_RANGE[1])
    priority_segment: PrioritySegment | None = None
    opportunities: list[LabeledItem] = Field(default_factory=list)
    limitations: list[LabeledItem] = Field(default_factory=list)
    data_quality: DataQuality


class MarketOpportunityResult(MarketOpportunityDraft):
    """Section 7.1: the checked market analysis that the agent writes to the shared context."""

    sources: list[SourceRef] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


# --- Competitor Analysis (KIRO_PROMPT_M2.md Section 8.1) ------------------------------
# Draft models are what the LLM returns; code checks them and builds the result models.

class CompetitorCandidate(BaseModel):
    """Phase A: a competitor or alternative named in the evidence, or named by the founder."""

    name: NonEmptyStr = Field(max_length=COMPETITOR_NAME_MAX)
    type: Literal[COMPETITOR_TYPES]
    source_ids: list[str] = Field(default_factory=list)
    basis: Literal[COMPETITOR_BASES] = "sourced"


class CandidateList(BaseModel):
    candidates: list[CompetitorCandidate] = Field(default_factory=list)


def _unavailable_price() -> QuantEstimate:
    return QuantEstimate(status="unavailable")


class CompetitorDraft(BaseModel):
    """A competitor as the LLM describes it. `type` and `relevance_note` may be missing here:
    code drops such entries as irrelevant (Section 8.3) instead of retrying the call."""

    name: NonEmptyStr = Field(max_length=COMPETITOR_NAME_MAX)
    type: Literal[COMPETITOR_TYPES] | None = None
    relevance_note: str = ""
    website: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    offering: str | None = None
    target_segment: str | None = None
    key_features: list[NonEmptyStr] = Field(default_factory=list)
    value_proposition: str | None = None
    pricing_model: QuantEstimate = Field(default_factory=_unavailable_price)
    strengths: list[LabeledItem] = Field(default_factory=list)
    weaknesses: list[LabeledItem] = Field(default_factory=list)
    positioning: str | None = None
    differentiation_vs_startup: str | None = None
    basis: Literal[COMPETITOR_BASES] = "sourced"


class Competitor(CompetitorDraft):
    """Section 8.1 `Competitor`. `info_completeness` is computed in code."""

    type: Literal[COMPETITOR_TYPES]
    relevance_note: NonEmptyStr
    info_completeness: Literal[INFO_COMPLETENESS]


class ComparisonCell(BaseModel):
    feature: NonEmptyStr
    status: Literal[CELL_STATUSES]
    source_ids: list[str] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    competitor: NonEmptyStr
    cells: list[ComparisonCell] = Field(default_factory=list)


class ComparisonDraft(BaseModel):
    features: list[NonEmptyStr] = Field(default_factory=list)
    rows: list[ComparisonRow] = Field(default_factory=list)


class FeatureCoverage(BaseModel):
    feature: NonEmptyStr
    competitors_with_evidence: int = Field(ge=0)


class Comparison(ComparisonDraft):
    """The feature matrix. `feature_coverage` is counted from the rows in code."""

    feature_coverage: list[FeatureCoverage] = Field(default_factory=list)


class MarketGapDraft(BaseModel):
    description: NonEmptyStr
    related_features: list[NonEmptyStr] = Field(default_factory=list)
    basis: Basis
    source_ids: list[str] = Field(default_factory=list)
    confidence: Literal[GAP_CONFIDENCES_DRAFT] = "low"


class MarketGap(MarketGapDraft):
    """A gap hypothesis: confidence is never above medium and the caveat is always set."""

    confidence: Literal[GAP_CONFIDENCES]
    caveat: NonEmptyStr


class CompetitorAnalysisDraft(BaseModel):
    """What the Phase C LLM call returns. Code adds `feature_coverage`, gap caveats,
    `queries_used`, `sources` and `caveats`, so any such keys in the reply are ignored."""

    competitors: list[CompetitorDraft] = Field(default_factory=list)
    comparison: ComparisonDraft = Field(default_factory=ComparisonDraft)
    market_gaps: list[MarketGapDraft] = Field(default_factory=list)
    differentiation_opportunities: list[LabeledItem] = Field(default_factory=list)
    data_quality: DataQuality


class MarketContext(BaseModel):
    """Section 9.1.4: the compact market context the competitor stage may use. Never the full
    market result."""

    market_category: str
    segment_names: list[str] = Field(default_factory=list)
    priority_segment: str | None = None
    priority_rationale: str | None = None
    trend_titles: list[str] = Field(default_factory=list)


class CompetitorAnalysisResult(BaseModel):
    """Section 8.1: the checked competitor analysis that the agent writes to the context."""

    competitors: list[Competitor] = Field(min_length=1)
    comparison: Comparison
    market_gaps: list[MarketGap] = Field(default_factory=list)
    differentiation_opportunities: list[LabeledItem] = Field(default_factory=list)
    queries_used: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    data_quality: DataQuality
    caveats: list[str] = Field(default_factory=list)


class StageError(BaseModel):
    stage: str
    code: str
    message: str


# --- UI upgrade (KIRO_UI_UPGRADE_SPEC.md Sections 8.5, 10.3 and 10.4) --------------------------
# Built in code from the structured results (agents/notices.py, agents/derived.py), never by the LLM.

NOTICE_SEVERITIES = ("info", "warning", "error")
EVIDENCE_STRENGTH_LABELS = ("strong", "moderate", "limited")
EVIDENCE_COMPONENTS = ("sourced_share", "source_breadth", "evidence_level")
ANALYSES = ("market", "competitors")


class Notice(BaseModel):
    """A quality note in plain words. `message` never holds a field path or an evidence id;
    `detail` keeps the technical text it came from, for developers."""

    stage: str | None = None
    code: str
    severity: Literal[NOTICE_SEVERITIES]
    message: str
    detail: str | None = None


class EvidenceComponent(BaseModel):
    key: Literal[EVIDENCE_COMPONENTS]
    label: str
    weight: float
    value: float = Field(ge=0, le=1)
    detail: str


class EvidenceStrength(BaseModel):
    """How well the findings are backed by sources (Section 8.5). Not a prediction of success."""

    label: Literal[EVIDENCE_STRENGTH_LABELS]
    score: float = Field(ge=0, le=1)
    components: list[EvidenceComponent]
    caption: str


class SummaryLine(BaseModel):
    """One executive-summary line. `source_ids` refer to the sources of `analysis` (the market
    and competitor analyses number their evidence separately). `basis` is None for a statement
    that code counted or composed, such as the number of competitors found."""

    topic: str
    text: str
    basis: Basis | None = None
    source_ids: list[str] = Field(default_factory=list)
    analysis: Literal[ANALYSES] | None = None


class VerifyItem(BaseModel):
    """One "what to verify next" item, built from an unavailable, estimated or low-confidence part."""

    topic: str
    text: str
    source_ids: list[str] = Field(default_factory=list)
    analysis: Literal[ANALYSES] | None = None


class PipelineResult(BaseModel):
    status: Literal["complete", "partial", "failed"]
    idea: ExtractedIdea | None = None
    search: SearchBundle | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[StageError] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)
    # Milestone 2, Task 3 (Section 9.1.2): the analysis stages' checked results. Optional, so
    # Milestone 1 clients and tests keep working. None when the stage did not run, was skipped
    # or failed; never a placeholder.
    market: MarketOpportunityResult | None = None
    competitors: CompetitorAnalysisResult | None = None
    # The analysis stages' own evidence inputs, named as the agent context names them. They are
    # returned so a client can rebuild the evidence the agents worked from (market_evidence and
    # competitor_evidence) and re-run the integrity checks on `market` and `competitors` without
    # any hidden state. Empty or None for a Milestone 1 run, and for a stage that was skipped.
    market_search: SearchBundle | None = None
    competitor_candidates: list[CompetitorCandidate] = Field(default_factory=list)
    competitor_search: SearchBundle | None = None
    # UI upgrade (Sections 10.3 and 10.4): plain quality notes and fields derived in code from the
    # results above. Optional, so earlier clients, saved results and tests keep working; `warnings`
    # and `errors` are unchanged.
    notices: list[Notice] = Field(default_factory=list)
    evidence_strength: EvidenceStrength | None = None
    executive_summary: list[SummaryLine] = Field(default_factory=list)
    verify_next: list[VerifyItem] = Field(default_factory=list)
    # Milestone 3 (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 6.5): the strategy stages'
    # results and the founder's resource constraints. Optional, so every saved result still validates.
    swot: "SwotRiskResult | None" = None
    mvp: "MvpResult | None" = None
    gtm: "GtmResult | None" = None
    constraints: "StrategyConstraints | None" = None
    usage: "Usage | None" = None
    versions: "Versions | None" = None


class StageUsage(BaseModel):
    llm_calls: int = Field(default=0, ge=0)
    search_calls: int = Field(default=0, ge=0)
    seconds: float = Field(default=0.0, ge=0)


class Usage(BaseModel):
    llm_calls: int = Field(default=0, ge=0)
    search_calls: int = Field(default=0, ge=0)
    by_stage: dict[str, StageUsage] = Field(default_factory=dict)


class Versions(BaseModel):
    query_profile: str
    prompt_profile: str
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    app_version: str


# --- Milestone 3 (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 6): strategy results ----------
# Built in code from the LLM drafts (models/strategy_drafts.py). Strategy items are judgments, so
# their basis is never `sourced`; their sources are inherited from the findings they cite.

STRATEGY_BASES = ("ai_interpretation", "assumption", "user_provided")
STRATEGY_INPUTS = ("idea", "market", "competitors", "swot", "mvp")
CONSTRAINT_FIELDS = ("team_size", "months_to_mvp", "budget_level", "technical_skill", "launch_region")
BUDGET_LEVELS = ("bootstrapped", "small", "funded")
TECHNICAL_SKILLS = ("non_technical", "some", "strong")
TEAM_SIZE_RANGE = (1, 10)
MONTHS_TO_MVP_RANGE = (1, 12)
LAUNCH_REGION_MAX = 60

RISK_CATEGORIES = ("business", "market", "technical", "financial", "operational")
RISK_LEVELS = ("low", "medium", "high")
RISK_CONFIDENCES = ("low", "medium")
RISK_CONFIDENCES_DRAFT = ("low", "medium", "high")
SWOT_QUADRANT_MAX = 5
RISKS_MAX = 10

FEATURE_ORIGINS = ("founder_listed", "gap_opportunity", "suggested")
EFFORT_SIZES = ("S", "M", "L")
FEATURE_TIERS = ("mvp", "later")
RATING_RANGE = (1, 5)
FEATURES_MAX = 12
METRICS_MAX = 5

CHANNEL_KINDS = ("digital", "community", "partnership", "offline", "direct_sales", "product_led")
CHANNEL_ROLES = ("acquisition", "distribution", "both")
COST_LEVELS = ("low", "medium", "high")
SPEEDS = ("days", "weeks", "months")
DIFFERENTIATOR_STATUSES = ("hypothesis", "supported")
LAUNCH_PHASE_NAMES = ("Before launch", "Launch", "First 90 days")
CHANNELS_MAX = 6
EARLY_CUSTOMERS_MAX = 5
LAUNCH_ACTIONS_MAX = 4
KEY_MESSAGES_MAX = 4

STRATEGY_SUMMARY_MAX = 400
SWOT_TEXT_MAX = 280
WHY_IT_MATTERS_MAX = 200
RISK_TITLE_MAX = 100
RISK_TEXT_MAX = 300
EARLY_WARNING_MAX = 200
FEATURE_NAME_MAX = 80
FEATURE_DESCRIPTION_MAX = 240
USER_PROBLEM_MAX = 200
RATIONALE_MAX = 300
METRIC_NAME_MAX = 80
METRIC_TEXT_MAX = 200
POSITIONING_PART_MAX = 160
CHANNEL_NAME_MAX = 60
CHANNEL_EXPERIMENT_MAX = 250
CHANNEL_SIGNAL_MAX = 200
TACTIC_TEXT_MAX = 220
PHASE_TEXT_MAX = 200
MESSAGE_TEXT_MAX = 200
PROOF_NEEDED_MAX = 160

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f]")

StrategyBasis = Literal[STRATEGY_BASES]


class StrategySourceKey(BaseModel):
    analysis: Literal[ANALYSES]
    id: NonEmptyStr


class StrategyConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_size: int | None = Field(default=None, ge=TEAM_SIZE_RANGE[0], le=TEAM_SIZE_RANGE[1])
    months_to_mvp: int | None = Field(default=None, ge=MONTHS_TO_MVP_RANGE[0], le=MONTHS_TO_MVP_RANGE[1])
    budget_level: Literal[BUDGET_LEVELS] | None = None
    technical_skill: Literal[TECHNICAL_SKILLS] | None = None
    launch_region: str | None = Field(default=None, max_length=LAUNCH_REGION_MAX)

    @field_validator("launch_region", mode="before")
    @classmethod
    def _printable_region(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = " ".join(_CONTROL_CHARACTERS.sub(" ", value).split())
        return cleaned or None


class StrategyQuality(BaseModel):
    inputs_used: list[Literal[STRATEGY_INPUTS]] = Field(default_factory=list)
    inputs_missing: list[Literal[STRATEGY_INPUTS]] = Field(default_factory=list)
    constraints_provided: list[Literal[CONSTRAINT_FIELDS]] = Field(default_factory=list)
    constraints_assumed: list[Literal[CONSTRAINT_FIELDS]] = Field(default_factory=list)
    basis_counts: dict[StrategyBasis, int] = Field(default_factory=dict)
    grounded_share: float = Field(default=0.0, ge=0, le=1)
    warnings_count: int = Field(default=0, ge=0)


class SwotItem(BaseModel):
    id: NonEmptyStr
    text: NonEmptyStr = Field(max_length=SWOT_TEXT_MAX)
    why_it_matters: str = Field(default="", max_length=WHY_IT_MATTERS_MAX)
    basis: StrategyBasis
    based_on: list[str] = Field(default_factory=list)
    sources: list[StrategySourceKey] = Field(default_factory=list)


class RiskItem(BaseModel):
    id: NonEmptyStr
    category: Literal[RISK_CATEGORIES]
    title: NonEmptyStr = Field(max_length=RISK_TITLE_MAX)
    description: NonEmptyStr = Field(max_length=RISK_TEXT_MAX)
    likelihood: Literal[RISK_LEVELS]
    impact: Literal[RISK_LEVELS]
    severity: Literal[RISK_LEVELS]
    mitigation: NonEmptyStr = Field(max_length=RISK_TEXT_MAX)
    early_warning_signal: NonEmptyStr = Field(max_length=EARLY_WARNING_MAX)
    confidence: Literal[RISK_CONFIDENCES]
    basis: StrategyBasis
    based_on: list[str] = Field(default_factory=list)
    sources: list[StrategySourceKey] = Field(default_factory=list)


class SwotRiskResult(BaseModel):
    summary: str = Field(default="", max_length=STRATEGY_SUMMARY_MAX)
    strengths: list[SwotItem] = Field(default_factory=list, max_length=SWOT_QUADRANT_MAX)
    weaknesses: list[SwotItem] = Field(default_factory=list, max_length=SWOT_QUADRANT_MAX)
    opportunities: list[SwotItem] = Field(default_factory=list, max_length=SWOT_QUADRANT_MAX)
    threats: list[SwotItem] = Field(default_factory=list, max_length=SWOT_QUADRANT_MAX)
    risks: list[RiskItem] = Field(default_factory=list, max_length=RISKS_MAX)
    risk_category_coverage: dict[Literal[RISK_CATEGORIES], int] = Field(default_factory=dict)
    coverage_gaps: list[Literal[RISK_CATEGORIES]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    quality: StrategyQuality = Field(default_factory=StrategyQuality)
    warnings: list[str] = Field(default_factory=list)


class MvpFeature(BaseModel):
    id: NonEmptyStr
    name: NonEmptyStr = Field(max_length=FEATURE_NAME_MAX)
    description: str = Field(default="", max_length=FEATURE_DESCRIPTION_MAX)
    user_problem: str = Field(default="", max_length=USER_PROBLEM_MAX)
    origin: Literal[FEATURE_ORIGINS]
    essential: bool = False
    customer_need: int = Field(ge=RATING_RANGE[0], le=RATING_RANGE[1])
    differentiation: int = Field(ge=RATING_RANGE[0], le=RATING_RANGE[1])
    feasibility: int = Field(ge=RATING_RANGE[0], le=RATING_RANGE[1])
    effort: Literal[EFFORT_SIZES]
    score: float = Field(ge=RATING_RANGE[0], le=RATING_RANGE[1])
    tier: Literal[FEATURE_TIERS]
    rank: int = Field(ge=1)
    rationale: str = Field(default="", max_length=RATIONALE_MAX)
    mitigates_risk_ids: list[str] = Field(default_factory=list)
    basis: StrategyBasis
    based_on: list[str] = Field(default_factory=list)
    sources: list[StrategySourceKey] = Field(default_factory=list)


class MvpMetric(BaseModel):
    name: NonEmptyStr = Field(max_length=METRIC_NAME_MAX)
    how_to_measure: NonEmptyStr = Field(max_length=METRIC_TEXT_MAX)
    suggested_target: str | None = Field(default=None, max_length=METRIC_TEXT_MAX)
    basis: StrategyBasis


class MvpResult(BaseModel):
    summary: str = Field(default="", max_length=STRATEGY_SUMMARY_MAX)
    features: list[MvpFeature] = Field(default_factory=list, max_length=FEATURES_MAX)
    capacity_person_months: float = Field(ge=0)
    planned_person_months: float = Field(ge=0)
    over_capacity: bool = False
    constraints_used: StrategyConstraints
    deferred_reasons: dict[str, str] = Field(default_factory=dict)
    success_metrics: list[MvpMetric] = Field(default_factory=list, max_length=METRICS_MAX)
    limitations: list[str] = Field(default_factory=list)
    quality: StrategyQuality = Field(default_factory=StrategyQuality)
    warnings: list[str] = Field(default_factory=list)


class Positioning(BaseModel):
    target_segment: NonEmptyStr = Field(max_length=POSITIONING_PART_MAX)
    for_whom: NonEmptyStr = Field(max_length=POSITIONING_PART_MAX)
    problem: NonEmptyStr = Field(max_length=POSITIONING_PART_MAX)
    category: NonEmptyStr = Field(max_length=POSITIONING_PART_MAX)
    key_benefit: NonEmptyStr = Field(max_length=POSITIONING_PART_MAX)
    alternative: NonEmptyStr = Field(max_length=POSITIONING_PART_MAX)
    differentiator: NonEmptyStr = Field(max_length=POSITIONING_PART_MAX)
    statement: NonEmptyStr
    differentiator_status: Literal[DIFFERENTIATOR_STATUSES]
    basis: StrategyBasis
    based_on: list[str] = Field(default_factory=list)
    sources: list[StrategySourceKey] = Field(default_factory=list)


class Channel(BaseModel):
    id: NonEmptyStr
    name: NonEmptyStr = Field(max_length=CHANNEL_NAME_MAX)
    kind: Literal[CHANNEL_KINDS]
    role: Literal[CHANNEL_ROLES]
    fit_rationale: str = Field(default="", max_length=RATIONALE_MAX)
    audience_fit: int = Field(ge=RATING_RANGE[0], le=RATING_RANGE[1])
    cost_level: Literal[COST_LEVELS]
    speed_to_first_result: Literal[SPEEDS]
    first_experiment: NonEmptyStr = Field(max_length=CHANNEL_EXPERIMENT_MAX)
    success_signal: NonEmptyStr = Field(max_length=CHANNEL_SIGNAL_MAX)
    priority: int = Field(ge=1)
    start_here: bool = False
    budget_conflict: bool = False
    uses_feature_ids: list[str] = Field(default_factory=list)
    addresses_risk_ids: list[str] = Field(default_factory=list)
    basis: StrategyBasis
    based_on: list[str] = Field(default_factory=list)
    sources: list[StrategySourceKey] = Field(default_factory=list)


class EarlyCustomerTactic(BaseModel):
    tactic: NonEmptyStr = Field(max_length=TACTIC_TEXT_MAX)
    where_to_find_them: NonEmptyStr = Field(max_length=TACTIC_TEXT_MAX)
    offer: NonEmptyStr = Field(max_length=TACTIC_TEXT_MAX)
    how_to_measure: NonEmptyStr = Field(max_length=TACTIC_TEXT_MAX)
    basis: StrategyBasis
    based_on: list[str] = Field(default_factory=list)
    sources: list[StrategySourceKey] = Field(default_factory=list)


class LaunchPhase(BaseModel):
    name: Literal[LAUNCH_PHASE_NAMES]
    goal: NonEmptyStr = Field(max_length=PHASE_TEXT_MAX)
    actions: list[Annotated[NonEmptyStr, Field(max_length=PHASE_TEXT_MAX)]] = Field(
        default_factory=list, max_length=LAUNCH_ACTIONS_MAX
    )


class KeyMessage(BaseModel):
    audience: NonEmptyStr = Field(max_length=MESSAGE_TEXT_MAX)
    message: NonEmptyStr = Field(max_length=MESSAGE_TEXT_MAX)
    proof_needed: str = Field(default="", max_length=PROOF_NEEDED_MAX)


class GtmResult(BaseModel):
    summary: str = Field(default="", max_length=STRATEGY_SUMMARY_MAX)
    positioning: Positioning
    channels: list[Channel] = Field(default_factory=list, max_length=CHANNELS_MAX)
    early_customers: list[EarlyCustomerTactic] = Field(default_factory=list, max_length=EARLY_CUSTOMERS_MAX)
    launch_phases: list[LaunchPhase] = Field(default_factory=list, max_length=len(LAUNCH_PHASE_NAMES))
    key_messages: list[KeyMessage] = Field(default_factory=list, max_length=KEY_MESSAGES_MAX)
    limitations: list[str] = Field(default_factory=list)
    quality: StrategyQuality = Field(default_factory=StrategyQuality)
    warnings: list[str] = Field(default_factory=list)


PipelineResult.model_rebuild()

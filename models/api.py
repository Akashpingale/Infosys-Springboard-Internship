"""Request and response models for the UI upgrade routes (KIRO_UI_UPGRADE_SPEC.md Section 10.1).

Kept apart from models/schemas.py, which holds the pipeline's own data. Nothing here changes the
Milestone 1 and 2 routes.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.report import NARRATIVE_STATUSES
from models.schemas import ExtractedIdea, IdeaSubmission, PipelineResult, StrategyConstraints

RUN_STATES = ("queued", "running", "done", "failed", "cancelled")
STRATEGY_MODES = ("missing", "all")
ACTIVE_STATES = ("queued", "running")
STAGE_STATUSES = ("waiting", "running", "done", "skipped", "failed", "cancelled")
RESULT_STATUSES = ("complete", "partial", "failed")
TITLE_MAX = 120


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """The one error shape every route returns (app.py)."""

    error: ErrorDetail


# --- GET /api/meta ------------------------------------------------------------------------------


class TextLimit(BaseModel):
    min_chars: int | None = None
    max_chars: int
    min_words: int | None = None


class CountLimit(BaseModel):
    min_items: int
    max_items: int


class ExtractedIdeaLimits(BaseModel):
    """What the review step may edit, with the limits ExtractedIdea enforces."""

    title_max_chars: int
    target_customers: CountLimit
    key_features: CountLimit


class FormLimits(BaseModel):
    idea_description: TextLimit
    industry: TextLimit
    target_customers: TextLimit
    relevant_details: TextLimit
    extracted_idea: ExtractedIdeaLimits


class ExampleIdea(BaseModel):
    key: str
    label: str
    submission: IdeaSubmission


class StageInfo(BaseModel):
    key: str
    label: str


class ProviderStatus(BaseModel):
    """Whether a provider is configured. Configured is not the same as tested: no call is made."""

    name: str
    configured: bool
    model: str | None = None


class Providers(BaseModel):
    llm: ProviderStatus
    fallback_llm: ProviderStatus
    search: ProviderStatus


class RunLimits(BaseModel):
    time_limit_s: float
    max_concurrent_runs: int
    competitor_max_extra_queries: int
    competitor_results_per_query: int
    evidence_max_items: int


class NumberLimit(BaseModel):
    min_value: int
    max_value: int


class ConstraintLimits(BaseModel):
    """The limits StrategyConstraints enforces and the choices it accepts (Section 12.3)."""

    team_size: NumberLimit
    months_to_mvp: NumberLimit
    launch_region: TextLimit
    budget_levels: list[str]
    technical_skills: list[str]


class StrategyInfo(BaseModel):
    """Milestone 3 (Section 12.1). `available` is true when every strategy stage has its agent;
    `time_limit_s` is the extra time a run with strategy gets, and the whole limit of a strategy job
    on a saved run."""

    available: bool
    time_limit_s: float
    constraints: ConstraintLimits


class ChatLimits(BaseModel):
    max_message_chars: int
    max_user_turns: int


class ReportInfo(BaseModel):
    available: bool
    pdf_available: bool
    time_limit_s: float


class ProfileInfo(BaseModel):
    query_profile: str
    prompt_profile: str
    app_version: str


class MetaResponse(BaseModel):
    app_name: str
    version: str
    limits: FormLimits
    industries: list[str]
    examples: list[ExampleIdea]
    stages: list[StageInfo]
    run_limits: RunLimits
    providers: Providers
    # Milestone 3 (Section 12.1). Always sent; optional in the schema so existing clients and their
    # typed fixtures stay valid.
    strategy: StrategyInfo | None = None
    chat: ChatLimits | None = None
    report: ReportInfo | None = None
    profiles: ProfileInfo | None = None


# --- /api/runs ------------------------------------------------------------------------------------


class RunRequest(BaseModel):
    """Start a run. `idea_override` is the extracted idea after the founder's review; with it the
    extraction stage is not run again."""

    model_config = ConfigDict(extra="forbid")

    submission: IdeaSubmission
    idea_override: ExtractedIdea | None = None
    # Milestone 3 (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 12.1): the three strategy stages
    # after the four, with the founder's resource constraints. Without them a run is as before.
    include_strategy: bool = False
    constraints: StrategyConstraints | None = None


class StrategyRequest(BaseModel):
    """Generate strategy for a saved run (Section 12.2). `missing` runs only the absent stages."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal[STRATEGY_MODES] = "missing"
    constraints: StrategyConstraints | None = None


class RunStarted(BaseModel):
    run_id: str
    state: Literal[RUN_STATES]


class RunStage(BaseModel):
    key: str
    label: str
    status: Literal[STAGE_STATUSES]
    started_at: str | None = None
    duration_s: float | None = None
    # Seconds so far for a running stage, the duration for a finished one, computed by the server.
    elapsed_s: float | None = None
    message: str | None = None


class RunReportStatus(BaseModel):
    exists: bool = False
    generated_at: str | None = None
    stale: bool = False
    narrative_status: Literal[NARRATIVE_STATUSES] | None = None


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force: bool = False
    narrative: bool = True


class RunDetail(BaseModel):
    """A run's state. `result` is the final result once the run has ended; while it runs, it holds
    what the finished stages produced so far (a partial snapshot), or null before any stage ends."""

    id: str
    title: str
    industry: str
    state: Literal[RUN_STATES]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_s: float | None = None
    elapsed_s: float | None = None
    cancel_requested: bool = False
    message: str | None = None
    stages: list[RunStage]
    submission: IdeaSubmission
    idea_override: ExtractedIdea | None = None
    result: PipelineResult | None = None
    # Milestone 3 (Section 12.1): the founder's resource constraints, if any were given.
    constraints: StrategyConstraints | None = None
    report: RunReportStatus | None = None


class RunSummary(BaseModel):
    """One row of the history list. `status` is the result's status when there is a result.
    `has_strategy` (Milestone 3) says whether the run asked for the strategy stages or was given them
    later; it is always sent, and optional in the schema only so existing clients stay valid."""

    id: str
    title: str
    industry: str
    state: Literal[RUN_STATES]
    status: Literal[RESULT_STATUSES] | None = None
    created_at: str
    duration_s: float | None = None
    has_strategy: bool | None = None


class RunList(BaseModel):
    runs: list[RunSummary]


class RunRename(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=TITLE_MAX)

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from models.schemas import STRATEGY_BASES

REPORT_SCHEMA_VERSION = 1
REPORT_BASES = ("sourced", "ai_interpretation", "assumption", "user_provided")
NARRATIVE_STATUSES = ("ok", "failed", "skipped")
CALLOUT_KINDS = ("note", "caveat", "warning")
COLUMN_ALIGNMENTS = ("left", "right")
REPORT_ANALYSES = ("market", "competitors")
RUN_STATUSES = ("complete", "partial", "failed")

ReportBasis = Literal[REPORT_BASES]


class ReportItem(BaseModel):
    text: str
    basis: ReportBasis | None = None
    cites: list[int] = Field(default_factory=list)
    keys: list[str] = Field(default_factory=list, exclude=True)


class ParagraphBlock(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: str
    basis: ReportBasis | None = None
    cites: list[int] = Field(default_factory=list)
    narrative: bool = False
    keys: list[str] = Field(default_factory=list, exclude=True)


class BulletsBlock(BaseModel):
    type: Literal["bullets"] = "bullets"
    items: list[ReportItem] = Field(default_factory=list)
    narrative: bool = False


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    caption: str
    columns: list[str]
    rows: list[list[str]] = Field(default_factory=list)
    col_align: list[Literal[COLUMN_ALIGNMENTS]] = Field(default_factory=list)
    row_cites: list[list[int]] = Field(default_factory=list)
    row_keys: list[list[str]] = Field(default_factory=list, exclude=True)

    @model_validator(mode="after")
    def _shape(self) -> "TableBlock":
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("Every table row needs one cell per column.")
        if self.col_align and len(self.col_align) != len(self.columns):
            raise ValueError("A table needs one alignment per column.")
        if self.row_cites and len(self.row_cites) != len(self.rows):
            raise ValueError("A table needs one citation list per row.")
        return self


class CalloutBlock(BaseModel):
    type: Literal["callout"] = "callout"
    kind: Literal[CALLOUT_KINDS]
    text: str


class FactPair(BaseModel):
    label: str
    value: str


class FactsBlock(BaseModel):
    type: Literal["facts"] = "facts"
    pairs: list[FactPair] = Field(default_factory=list)


class SubheadingBlock(BaseModel):
    type: Literal["subheading"] = "subheading"
    text: str


ReportBlock = Annotated[
    ParagraphBlock | BulletsBlock | TableBlock | CalloutBlock | FactsBlock | SubheadingBlock,
    Field(discriminator="type"),
]


class ReportSection(BaseModel):
    id: str
    title: str
    blocks: list[ReportBlock] = Field(default_factory=list)


class MissingSection(BaseModel):
    id: str
    reason: str


class ConsistencyCheck(BaseModel):
    id: str
    description: str
    passed: bool
    detail: str = ""


class ConsistencyReport(BaseModel):
    checks: list[ConsistencyCheck] = Field(default_factory=list)
    passed_count: int = Field(default=0, ge=0)
    total_count: int = Field(default=0, ge=0)


class ReportMeta(BaseModel):
    run_id: str
    generated_at: str
    source_fingerprint: str = ""
    run_status: Literal[RUN_STATUSES]
    idea_title: str
    industry: str
    sections_included: list[str] = Field(default_factory=list)
    sections_missing: list[MissingSection] = Field(default_factory=list)
    narrative_status: Literal[NARRATIVE_STATUSES] = "skipped"
    prompt_version: str | None = None
    app_version: str
    consistency: ConsistencyReport = Field(default_factory=ConsistencyReport)


class BibEntry(BaseModel):
    number: int = Field(ge=1)
    title: str
    url: str | None = None
    domain: str = ""
    analyses: list[Literal[REPORT_ANALYSES]] = Field(default_factory=list)
    cited_in: list[str] = Field(default_factory=list)
    has_page: bool = True

    @model_validator(mode="after")
    def _web_links_only(self) -> "BibEntry":
        if self.url is not None and not self.url.lower().startswith(("http://", "https://")):
            raise ValueError("A source link must be an http or https address.")
        return self


class ReportDocument(BaseModel):
    schema_version: int = REPORT_SCHEMA_VERSION
    title: str
    subtitle: str
    meta: ReportMeta
    sections: list[ReportSection] = Field(default_factory=list)
    bibliography: list[BibEntry] = Field(default_factory=list)
    appendix_sections: list[ReportSection] = Field(default_factory=list)


class NarrativeStatementDraft(BaseModel):
    text: str
    basis: Literal[STRATEGY_BASES]
    based_on: list[str] = Field(default_factory=list)


class NextStepDraft(BaseModel):
    action: str
    why: str = ""
    based_on: list[str] = Field(default_factory=list)


class ReportNarrativeDraft(BaseModel):
    overview: list[NarrativeStatementDraft] = Field(default_factory=list)
    key_insights: list[NarrativeStatementDraft] = Field(default_factory=list)
    next_steps: list[NextStepDraft] = Field(default_factory=list)
    closing_caveat: str = ""


class ReportVersionError(ValueError):
    pass


MSG_NEWER_REPORT = (
    "This report was made by a newer version of the app and cannot be read here. Generate the report again."
)
MSG_UNREADABLE_REPORT = "The stored report could not be read. Generate the report again."


def report_json(document: ReportDocument) -> str:
    return document.model_dump_json(indent=2)


def read_report(data: object) -> ReportDocument:
    if not isinstance(data, dict):
        raise ReportVersionError(MSG_UNREADABLE_REPORT)
    version = data.get("schema_version", REPORT_SCHEMA_VERSION)
    if not isinstance(version, int) or isinstance(version, bool):
        raise ReportVersionError(MSG_UNREADABLE_REPORT)
    if version > REPORT_SCHEMA_VERSION:
        raise ReportVersionError(MSG_NEWER_REPORT)
    try:
        return ReportDocument.model_validate(data)
    except ValueError:
        raise ReportVersionError(MSG_UNREADABLE_REPORT) from None

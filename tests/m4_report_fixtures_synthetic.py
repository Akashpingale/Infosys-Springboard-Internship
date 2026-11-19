import json
from pathlib import Path

from agents.derived import with_derived_fields
from agents.report_bibliography import number_citations
from agents.report_checks import with_consistency
from agents.report_sections import build_document
from models.report import ReportDocument
from models.schemas import PipelineResult, StageError

ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC_PATH = ROOT / "web" / "src" / "test" / "strategyFixture.synthetic.json"
GENERATED_AT = "2026-11-16T10:00:00+00:00"
RUN_ID = "synthetic-run"
APP_VERSION = "0.1.0"
BUSY = "The AI service is busy right now. Please try again in a minute."
SEARCH_FAILED = "Web search could not be completed. Please try again."


def synthetic_complete() -> PipelineResult:
    return PipelineResult.model_validate(json.loads(SYNTHETIC_PATH.read_text(encoding="utf-8")))


def synthetic_partial() -> PipelineResult:
    complete = synthetic_complete()
    return with_derived_fields(complete.model_copy(update={
        "status": "partial",
        "market": None,
        "market_search": None,
        "gtm": None,
        "errors": [
            StageError(stage="market_opportunity", code="llm_api_error", message=BUSY),
            StageError(stage="go_to_market", code="llm_api_error", message=BUSY),
        ],
    }))


def synthetic_no_strategy() -> PipelineResult:
    complete = synthetic_complete()
    warnings = [warning for warning in complete.warnings if not warning.startswith("Planning go-to-market")]
    return with_derived_fields(complete.model_copy(update={
        "swot": None, "mvp": None, "gtm": None, "constraints": None, "warnings": warnings,
    }))


def synthetic_minimal() -> PipelineResult:
    complete = synthetic_complete()
    return with_derived_fields(PipelineResult(
        status="partial",
        idea=complete.idea,
        errors=[StageError(stage="search", code="search_api_error", message=SEARCH_FAILED)],
        warnings=[
            "Market and competitor research is not available, so only the structured idea is shown.",
            "Market opportunity: skipped because the web search did not complete.",
            "Competitor analysis: skipped because the web search did not complete.",
        ],
        timings={"extraction": 1.2, "search": 0.4, "total": 1.6},
    ))


SYNTHETIC_RESULTS = {
    "complete": synthetic_complete,
    "partial": synthetic_partial,
    "no_strategy": synthetic_no_strategy,
    "minimal": synthetic_minimal,
}


def draft(result: PipelineResult) -> ReportDocument:
    return build_document(result, run_id=RUN_ID, generated_at=GENERATED_AT, app_version=APP_VERSION)


def full_document(result: PipelineResult) -> ReportDocument:
    return with_consistency(number_citations(draft(result), result), result)

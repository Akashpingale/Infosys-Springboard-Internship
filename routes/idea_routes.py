from fastapi import APIRouter, Query

from agents.extraction_agent import extract_idea
from agents.web_search_agent import run_web_search
from models.schemas import ExtractedIdea, IdeaSubmission, PipelineResult, SearchBundle
from orchestrator import FULL_STAGES, analysis_time_limit_s, run_pipeline

router = APIRouter(prefix="/api", tags=["ideas"])

ANALYSIS_PARAM_HELP = (
    "Also run the Market Opportunity and Competitor Analysis stages (Milestone 2). "
    "Without it, only extraction and web search run, as in Milestone 1."
)


@router.post("/ideas/extract", response_model=ExtractedIdea)
def extract(submission: IdeaSubmission) -> ExtractedIdea:
    """Structure a founder's idea into problem, solution, customers, industry and features."""
    return extract_idea(submission)


@router.post("/search", response_model=SearchBundle)
def web_search(idea: ExtractedIdea) -> SearchBundle:
    """Fetch live market and competitor information for an extracted idea."""
    return run_web_search(idea)


@router.post("/validate", response_model=PipelineResult)
def validate(
    submission: IdeaSubmission,
    include_analysis: bool = Query(default=False, description=ANALYSIS_PARAM_HELP),
) -> PipelineResult:
    """Run the whole pipeline: structure the idea, research it and, with include_analysis,
    analyse its market and competitors. The UI always asks for the analysis, and that run is
    time-limited so it answers before the UI stops waiting (orchestrator.TIME_LIMIT_SHARE)."""
    if include_analysis:
        return run_pipeline(submission, FULL_STAGES, time_limit_s=analysis_time_limit_s())
    return run_pipeline(submission)

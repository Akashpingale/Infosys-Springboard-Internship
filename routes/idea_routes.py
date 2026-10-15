from fastapi import APIRouter

from agents.extraction_agent import extract_idea
from agents.web_search_agent import run_web_search
from models.schemas import ExtractedIdea, IdeaSubmission, PipelineResult, SearchBundle
from orchestrator import run_pipeline

router = APIRouter(prefix="/api", tags=["ideas"])


@router.post("/ideas/extract", response_model=ExtractedIdea)
def extract(submission: IdeaSubmission) -> ExtractedIdea:
    """Structure a founder's idea into problem, solution, customers, industry and features."""
    return extract_idea(submission)


@router.post("/search", response_model=SearchBundle)
def web_search(idea: ExtractedIdea) -> SearchBundle:
    """Fetch live market and competitor information for an extracted idea."""
    return run_web_search(idea)


@router.post("/validate", response_model=PipelineResult)
def validate(submission: IdeaSubmission) -> PipelineResult:
    """Run the whole pipeline: structure the idea, then research it. Used by the UI."""
    return run_pipeline(submission)

"""GET /api/meta (KIRO_UI_UPGRADE_SPEC.md Sections 10.1 and 8.1).

One place the new front end reads the form limits, the industry list, the example ideas, the stage
labels and the run limits from, so no number or label is repeated in the interface. It also reports
which providers are configured, never a key and never a key's length.

Configured is not the same as working: no provider is called here, so a `true` only means a key and
a model name are set.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter

from agents.notices import STAGE_TITLES
from config import ROOT_DIR, get_settings
from models.api import (
    CountLimit,
    ErrorResponse,
    ExampleIdea,
    ExtractedIdeaLimits,
    FormLimits,
    MetaResponse,
    ProviderStatus,
    Providers,
    RunLimits,
    StageInfo,
    TextLimit,
)
from models.schemas import (
    CUSTOMERS_MAX,
    CUSTOMERS_MIN,
    DETAILS_MAX,
    IDEA_MAX,
    IDEA_MIN,
    IDEA_MIN_WORDS,
    IDEA_TITLE_MAX,
    INDUSTRIES,
    INDUSTRY_MAX,
    INDUSTRY_MIN,
    KEY_FEATURES_RANGE,
    TARGET_CUSTOMERS_RANGE,
    IdeaSubmission,
)
from orchestrator import FULL_STAGES
from utils import groq_client
from utils.run_manager import MAX_CONCURRENT_RUNS, run_time_limit_s

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["meta"])

APP_NAME = "AI Startup Idea Validator"
APP_VERSION = "0.1.0"
IDEAS_DIR = ROOT_DIR / "data" / "test_ideas"
# Section 4.16: one example per Task 4 domain, read from the files the live runs use.
EXAMPLES = (("agritech", "Agritech"), ("fintech_cashflow", "Fintech"), ("foodtech_surplus", "Foodtech"))


def form_limits() -> FormLimits:
    """The limits models/schemas.py enforces, so the form never repeats a number."""
    return FormLimits(
        idea_description=TextLimit(min_chars=IDEA_MIN, max_chars=IDEA_MAX, min_words=IDEA_MIN_WORDS),
        industry=TextLimit(min_chars=INDUSTRY_MIN, max_chars=INDUSTRY_MAX),
        target_customers=TextLimit(min_chars=CUSTOMERS_MIN, max_chars=CUSTOMERS_MAX),
        relevant_details=TextLimit(max_chars=DETAILS_MAX),
        extracted_idea=ExtractedIdeaLimits(
            title_max_chars=IDEA_TITLE_MAX,
            target_customers=CountLimit(min_items=TARGET_CUSTOMERS_RANGE[0], max_items=TARGET_CUSTOMERS_RANGE[1]),
            key_features=CountLimit(min_items=KEY_FEATURES_RANGE[0], max_items=KEY_FEATURES_RANGE[1]),
        ),
    )


def example_ideas(directory: Path = IDEAS_DIR) -> list[ExampleIdea]:
    """The example submissions. A missing or unreadable file is left out rather than invented."""
    examples = []
    for key, label in EXAMPLES:
        path = directory / f"{key}.json"
        try:
            submission = IdeaSubmission(**json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("example idea %s was left out (%s)", key, type(exc).__name__)
            continue
        examples.append(ExampleIdea(key=key, label=label, submission=submission))
    return examples


def providers() -> Providers:
    settings = get_settings()
    return Providers(
        llm=ProviderStatus(name="Gemini", configured=bool(settings.llm_api_key and settings.llm_model),
                           model=settings.llm_model),
        fallback_llm=ProviderStatus(name="Groq", configured=bool(settings.groq_api_key), model=groq_client.MODEL),
        search=ProviderStatus(name="Tavily", configured=bool(settings.tavily_api_key)),
    )


@router.get("/meta", response_model=MetaResponse, responses={503: {"model": ErrorResponse}})
def meta() -> MetaResponse:
    """Everything the interface needs before a run: limits, industries, examples, stages and
    limits. Never a key."""
    settings = get_settings()
    return MetaResponse(
        app_name=APP_NAME,
        version=APP_VERSION,
        limits=form_limits(),
        industries=list(INDUSTRIES),
        examples=example_ideas(),
        stages=[StageInfo(key=stage.name, label=STAGE_TITLES.get(stage.name, stage.name)) for stage in FULL_STAGES],
        run_limits=RunLimits(
            time_limit_s=run_time_limit_s(),
            max_concurrent_runs=MAX_CONCURRENT_RUNS,
            competitor_max_extra_queries=settings.competitor_max_extra_queries,
            competitor_results_per_query=settings.competitor_results_per_query,
            evidence_max_items=settings.evidence_max_items,
        ),
        providers=providers(),
    )

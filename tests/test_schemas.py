import json

import pytest
from pydantic import ValidationError

from models.schemas import (
    DETAILS_MAX,
    IDEA_MAX,
    IDEA_MIN,
    INDUSTRIES,
    ExtractedIdea,
    IdeaSubmission,
    PipelineResult,
    SearchResult,
)
from tests.fakes import (
    LLM_REPLY_EMPTY_LIST,
    LLM_REPLY_EXTRA_KEY,
    LLM_REPLY_MISSING_FIELD,
    LLM_REPLY_OK,
    VALID_EXTRACTION,
)

VALID_SUBMISSION = {
    "idea_description": "An AI app that detects crop diseases from phone photos for small farmers.",
    "industry": "Agriculture / AgriTech",
    "target_customers": "Small farmers in India",
    "relevant_details": "Pilot in Maharashtra",
}


def submission(**overrides: object) -> dict:
    return {**VALID_SUBMISSION, **overrides}


def test_valid_submission_strips_whitespace() -> None:
    idea = IdeaSubmission(**submission(target_customers="  Small farmers  "))
    assert idea.target_customers == "Small farmers"


@pytest.mark.parametrize("field", ["idea_description", "industry", "target_customers"])
@pytest.mark.parametrize("value", ["", "   \n\t "])
def test_required_fields_reject_empty_and_whitespace(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        IdeaSubmission(**submission(**{field: value}))


@pytest.mark.parametrize("field", ["idea_description", "industry", "target_customers"])
def test_required_fields_reject_missing(field: str) -> None:
    data = submission()
    del data[field]
    with pytest.raises(ValidationError):
        IdeaSubmission(**data)


def test_description_length_boundaries() -> None:
    base = "word " * (IDEA_MAX // 5)
    assert IdeaSubmission(**submission(idea_description=("a b " + "c" * IDEA_MIN)[:IDEA_MIN]))
    assert IdeaSubmission(**submission(idea_description=base[:IDEA_MAX]))
    with pytest.raises(ValidationError):
        IdeaSubmission(**submission(idea_description=("a b " + "c" * IDEA_MIN)[: IDEA_MIN - 1]))
    with pytest.raises(ValidationError):
        IdeaSubmission(**submission(idea_description=base + "x" * (IDEA_MAX + 1 - len(base))))


def test_description_needs_three_words() -> None:
    with pytest.raises(ValidationError, match="at least 3 words"):
        IdeaSubmission(**submission(idea_description="Cropdiseasedetection appforfarmersinindia"))


def test_relevant_details_optional_and_limited() -> None:
    assert IdeaSubmission(**submission(relevant_details="   ")).relevant_details is None
    assert IdeaSubmission(**submission(relevant_details=None)).relevant_details is None
    with pytest.raises(ValidationError):
        IdeaSubmission(**submission(relevant_details="x" * (DETAILS_MAX + 1)))


def test_submission_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        IdeaSubmission(**submission(api_key="nope"))


def test_industries_list_ends_with_other() -> None:
    assert INDUSTRIES[-1] == "Other" and len(INDUSTRIES) == len(set(INDUSTRIES))


def test_extracted_idea_accepts_valid_json() -> None:
    idea = ExtractedIdea.model_validate_json(LLM_REPLY_OK)
    assert idea.key_features == VALID_EXTRACTION["key_features"]


@pytest.mark.parametrize("reply", [LLM_REPLY_MISSING_FIELD, LLM_REPLY_EMPTY_LIST, LLM_REPLY_EXTRA_KEY])
def test_extracted_idea_rejects_bad_shapes(reply: str) -> None:
    with pytest.raises(ValidationError):
        ExtractedIdea.model_validate_json(reply)


def test_extracted_idea_rejects_blank_items_and_long_title() -> None:
    with pytest.raises(ValidationError):
        ExtractedIdea(**{**VALID_EXTRACTION, "target_customers": ["  "]})
    with pytest.raises(ValidationError):
        ExtractedIdea(**{**VALID_EXTRACTION, "idea_title": "x" * 81})
    with pytest.raises(ValidationError):
        ExtractedIdea(**{**VALID_EXTRACTION, "key_features": ["a", "b", "c", "d", "e", "f", "g"]})


def test_search_result_limits() -> None:
    with pytest.raises(ValidationError):
        SearchResult(title="t", url="https://x.org", snippet="s" * 301)
    with pytest.raises(ValidationError):
        SearchResult(title="t", url="https://x.org", snippet="s", score=1.5)


def test_pipeline_result_round_trips_as_json() -> None:
    result = PipelineResult(status="partial", idea=ExtractedIdea(**VALID_EXTRACTION))
    assert PipelineResult.model_validate(json.loads(result.model_dump_json())) == result
    with pytest.raises(ValidationError):
        PipelineResult(status="done")

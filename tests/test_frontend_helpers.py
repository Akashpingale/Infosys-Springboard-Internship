"""Tests for the UI's pure helpers. The Streamlit layer itself is checked manually."""

import pytest
import requests

from frontend import api_client
from frontend.api_client import (
    INDUSTRY_OTHER_FIELD,
    OTHER_INDUSTRY,
    BackendError,
    FormValues,
    validate_idea,
    validate_submission,
)
from models.schemas import (
    CUSTOMERS_MAX,
    CUSTOMERS_MIN,
    DETAILS_MAX,
    IDEA_MAX,
    IDEA_MIN,
    IDEA_MIN_WORDS,
    INDUSTRIES,
    IdeaSubmission,
    PipelineResult,
)
from tests.fakes import VALID_EXTRACTION, FakeHTTPResponse, make_sequence

GOOD_DESCRIPTION = "An AI app that detects crop diseases from phone photos for small farmers."
GOOD_INDUSTRY = "Agriculture / AgriTech"
GOOD_CUSTOMERS = "Small farmers in India"

COMPLETE_RESULT = {
    "status": "complete",
    "idea": VALID_EXTRACTION,
    "search": {"sections": [], "total_results": 0, "queries_failed": 0},
    "warnings": [],
    "errors": [],
    "timings": {"extraction": 1.0, "search": 2.0, "total": 3.0},
}


def form(**overrides: str) -> FormValues:
    values = {
        "idea_description": GOOD_DESCRIPTION,
        "industry": GOOD_INDUSTRY,
        "target_customers": GOOD_CUSTOMERS,
    }
    values.update(overrides)
    return FormValues(**values)


def use_fake_post(monkeypatch: pytest.MonkeyPatch, *outcomes: object):
    fake = make_sequence(*outcomes)
    monkeypatch.setattr(api_client.requests, "post", fake)
    return fake


def submission() -> IdeaSubmission:
    built, errors = validate_submission(form())
    assert errors == {} and built is not None
    return built


# --- form validation ---------------------------------------------------------


def test_valid_form_builds_the_shared_model() -> None:
    built, errors = validate_submission(form(relevant_details="Pilot in Maharashtra"))
    assert errors == {}
    assert isinstance(built, IdeaSubmission)
    assert built.idea_description == GOOD_DESCRIPTION
    assert built.industry == GOOD_INDUSTRY
    assert built.relevant_details == "Pilot in Maharashtra"


def test_whitespace_is_stripped() -> None:
    built, errors = validate_submission(
        form(idea_description=f"  {GOOD_DESCRIPTION}  ", target_customers="  Farmers  ")
    )
    assert errors == {}
    assert built is not None
    assert built.idea_description == GOOD_DESCRIPTION and built.target_customers == "Farmers"


def test_blank_extra_details_becomes_none() -> None:
    built, _ = validate_submission(form(relevant_details="   "))
    assert built is not None and built.relevant_details is None


@pytest.mark.parametrize("field", ["idea_description", "target_customers"])
@pytest.mark.parametrize("value", ["", "    ", "\n\t "])
def test_required_fields_block_submission_when_blank(field: str, value: str) -> None:
    built, errors = validate_submission(form(**{field: value}))
    assert built is None
    assert errors[field] == f"Please enter your {api_client.FIELD_LABELS[field]}."


def test_description_too_short_names_the_shared_minimum() -> None:
    built, errors = validate_submission(form(idea_description="a b " + "c" * (IDEA_MIN - 5)))
    assert built is None
    assert str(IDEA_MIN) in errors["idea_description"]
    assert errors["idea_description"].startswith("Please use at least")


def test_description_too_long_names_the_shared_maximum() -> None:
    built, errors = validate_submission(form(idea_description="word " * (IDEA_MAX // 2)))
    assert built is None
    assert str(IDEA_MAX) in errors["idea_description"]


def test_description_needs_enough_words() -> None:
    built, errors = validate_submission(form(idea_description="Cropdisease" * 6))
    assert built is None
    assert errors["idea_description"] == (
        f"Please describe your idea in at least {IDEA_MIN_WORDS} words."
    )


def test_target_customers_length_limits() -> None:
    _, short_errors = validate_submission(form(target_customers="a" * (CUSTOMERS_MIN - 1)))
    _, long_errors = validate_submission(form(target_customers="a" * (CUSTOMERS_MAX + 1)))
    assert str(CUSTOMERS_MIN) in short_errors["target_customers"]
    assert str(CUSTOMERS_MAX) in long_errors["target_customers"]


def test_extra_details_too_long_is_rejected() -> None:
    built, errors = validate_submission(form(relevant_details="x" * (DETAILS_MAX + 1)))
    assert built is None
    assert str(DETAILS_MAX) in errors["relevant_details"]


def test_several_problems_are_reported_together() -> None:
    built, errors = validate_submission(
        form(idea_description="  ", target_customers="", relevant_details="x" * (DETAILS_MAX + 1))
    )
    assert built is None
    assert set(errors) == {"idea_description", "target_customers", "relevant_details"}


# --- the "Other" industry ----------------------------------------------------


def test_other_without_detail_is_rejected() -> None:
    built, errors = validate_submission(form(industry=OTHER_INDUSTRY))
    assert built is None
    assert errors[INDUSTRY_OTHER_FIELD] == api_client.MSG_OTHER_REQUIRED
    assert "industry" not in errors


def test_other_with_whitespace_only_is_rejected() -> None:
    built, errors = validate_submission(form(industry=OTHER_INDUSTRY, industry_other="   "))
    assert built is None and INDUSTRY_OTHER_FIELD in errors


def test_other_with_detail_is_sent_as_the_industry() -> None:
    built, errors = validate_submission(
        form(industry=OTHER_INDUSTRY, industry_other="  Sports and fitness  ")
    )
    assert errors == {}
    assert built is not None and built.industry == "Sports and fitness"


def test_other_detail_is_ignored_for_a_normal_industry() -> None:
    built, _ = validate_submission(form(industry=GOOD_INDUSTRY, industry_other="ignored"))
    assert built is not None and built.industry == GOOD_INDUSTRY


def test_every_shared_industry_is_accepted() -> None:
    for industry in INDUSTRIES:
        values = form(industry=industry, industry_other="Sports and fitness")
        built, errors = validate_submission(values)
        assert errors == {}, industry
        assert built is not None


def test_character_hints_come_from_the_shared_limits() -> None:
    hint = api_client.character_hint("idea_description")
    assert str(IDEA_MIN) in hint and str(IDEA_MAX) in hint and str(IDEA_MIN_WORDS) in hint
    assert str(DETAILS_MAX) in api_client.character_hint("relevant_details")


# --- talking to the backend --------------------------------------------------


def test_successful_call_returns_a_pipeline_result(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, FakeHTTPResponse(200, COMPLETE_RESULT))
    result = validate_idea(submission(), url="http://localhost:8000")

    assert isinstance(result, PipelineResult) and result.status == "complete"
    args, kwargs = fake.calls[0]
    assert args[0] == "http://localhost:8000/api/validate"
    assert kwargs["json"]["idea_description"] == GOOD_DESCRIPTION
    assert kwargs["timeout"] == api_client.REQUEST_TIMEOUT_S == 90


def test_the_backend_url_comes_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_URL", "http://127.0.0.1:9000/")
    fake = use_fake_post(monkeypatch, FakeHTTPResponse(200, COMPLETE_RESULT))
    validate_idea(submission())
    assert fake.calls[0][0][0] == "http://127.0.0.1:9000/api/validate"


def test_backend_not_running_tells_the_user_how_to_start_it(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fake_post(monkeypatch, requests.ConnectionError("refused"))
    with pytest.raises(BackendError) as info:
        validate_idea(submission())
    assert info.value.message == api_client.MSG_BACKEND_DOWN
    assert "python app.py" in info.value.message


def test_timeout_is_reported_plainly(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, requests.Timeout("too slow"))
    with pytest.raises(BackendError, match="took too long"):
        validate_idea(submission())


def test_422_shows_the_servers_field_message(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"error": {"code": "invalid_input", "message": "idea_description: too short"}}
    use_fake_post(monkeypatch, FakeHTTPResponse(422, body))
    with pytest.raises(BackendError) as info:
        validate_idea(submission())
    assert "idea_description: too short" in info.value.message


@pytest.mark.parametrize("status", [502, 503])
def test_502_and_503_show_the_message_from_the_error_json(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    body = {"error": {"code": "llm_api_error", "message": "The AI service is busy right now."}}
    use_fake_post(monkeypatch, FakeHTTPResponse(status, body))
    with pytest.raises(BackendError) as info:
        validate_idea(submission())
    assert info.value.message == "The AI service is busy right now."


def test_error_without_a_message_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, FakeHTTPResponse(500, {"detail": "boom"}))
    with pytest.raises(BackendError) as info:
        validate_idea(submission())
    assert info.value.message == api_client.MSG_UNEXPECTED


def test_non_json_reply_is_reported_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, FakeHTTPResponse(200, None, "<html>oops</html>"))
    with pytest.raises(BackendError) as info:
        validate_idea(submission())
    assert info.value.message == api_client.MSG_BAD_REPLY


def test_unexpected_json_shape_is_reported_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, FakeHTTPResponse(200, {"status": "not-a-real-status"}))
    with pytest.raises(BackendError) as info:
        validate_idea(submission())
    assert info.value.message == api_client.MSG_BAD_REPLY


def test_other_request_problems_use_the_generic_message(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, requests.TooManyRedirects("loop"))
    with pytest.raises(BackendError) as info:
        validate_idea(submission())
    assert info.value.message == api_client.MSG_UNEXPECTED


def test_no_message_ever_leaks_a_key_or_a_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes = [
        requests.ConnectionError("refused"),
        requests.Timeout("slow"),
        FakeHTTPResponse(500, {"error": {"code": "x", "message": "server said no"}}),
        FakeHTTPResponse(200, None, "<html/>"),
    ]
    for outcome in outcomes:
        use_fake_post(monkeypatch, outcome)
        with pytest.raises(BackendError) as info:
            validate_idea(submission())
        message = info.value.message
        assert "test-llm-key" not in message and "test-tavily-key" not in message
        assert "Traceback" not in message


def test_partial_and_failed_results_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    partial = {
        **COMPLETE_RESULT,
        "status": "partial",
        "search": None,
        "warnings": ["Market and competitor research is not available."],
        "errors": [{"stage": "search", "code": "search_api_error", "message": "Search failed."}],
    }
    failed = {
        "status": "failed",
        "idea": None,
        "search": None,
        "warnings": [],
        "errors": [{"stage": "extraction", "code": "llm_api_error", "message": "AI failed."}],
        "timings": {"extraction": 0.5, "total": 0.5},
    }
    for body, expected in ((partial, "partial"), (failed, "failed")):
        use_fake_post(monkeypatch, FakeHTTPResponse(200, body))
        assert validate_idea(submission()).status == expected

"""One test per row of the Section 12 error-handling matrix. Nothing touches the network."""

import pytest
import requests
from fastapi.testclient import TestClient

from agents import extraction_agent
from agents import web_search_agent
from frontend import api_client
from frontend.api_client import BackendError, FormValues, validate_idea, validate_submission
from models.schemas import DETAILS_MAX, IDEA_MAX, IDEA_MIN, PipelineResult
from tests.fakes import (
    LLM_REPLY_EMPTY,
    LLM_REPLY_EXTRA_KEY,
    LLM_REPLY_MISSING_FIELD,
    LLM_REPLY_NOT_JSON,
    LLM_REPLY_OK,
    TAVILY_CONNECTION_ERROR,
    TAVILY_OK_RESPONSE,
    TAVILY_TIMEOUT,
    FakeHTTPResponse,
    make_sequence,
    tavily_empty,
    tavily_not_json,
    tavily_status,
)
from utils import llm_client, search_client

URL = "/api/validate"
GOOD_DESCRIPTION = "An AI app that detects crop diseases from phone photos for small farmers."
BODY = {
    "idea_description": GOOD_DESCRIPTION,
    "industry": "Agriculture / AgriTech",
    "target_customers": "Small farmers in India",
    "relevant_details": "Pilot in Maharashtra",
}


def fake_llm(monkeypatch: pytest.MonkeyPatch, *replies: object):
    fake = make_sequence(*replies)
    monkeypatch.setattr(extraction_agent, "generate_json", fake)
    return fake


def fake_tavily(monkeypatch: pytest.MonkeyPatch, *outcomes: object):
    fake = make_sequence(*outcomes)
    monkeypatch.setattr(search_client.requests, "post", fake)
    return fake


def fake_ui_post(monkeypatch: pytest.MonkeyPatch, *outcomes: object):
    fake = make_sequence(*outcomes)
    monkeypatch.setattr(api_client.requests, "post", fake)
    return fake


def run(client: TestClient, body: dict | None = None) -> PipelineResult:
    response = client.post(URL, json=BODY if body is None else body)
    assert response.status_code == 200, response.text
    assert "Traceback" not in response.text
    assert "test-llm-key" not in response.text and "test-tavily-key" not in response.text
    return PipelineResult.model_validate(response.json())


def form(**overrides: str) -> FormValues:
    values = {
        "idea_description": GOOD_DESCRIPTION,
        "industry": "Agriculture / AgriTech",
        "target_customers": "Small farmers in India",
    }
    values.update(overrides)
    return FormValues(**values)


# --- row 1: empty or whitespace-only field, not run -------------------------


def test_row01_whitespace_only_field_is_caught_before_any_call(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    submission, errors = validate_submission(form(idea_description="   "))
    assert submission is None
    assert errors["idea_description"] == "Please enter your idea description."

    llm = fake_llm(monkeypatch, LLM_REPLY_OK)
    search = fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))
    response = client.post(URL, json={**BODY, "idea_description": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert llm.calls == [] and search.calls == []


# --- row 2: description too short or too long, not run ----------------------


def test_row02_description_too_short_or_too_long(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, short_errors = validate_submission(form(idea_description="a b " + "c" * (IDEA_MIN - 5)))
    _, long_errors = validate_submission(form(idea_description="word " * (IDEA_MAX // 2)))
    assert str(IDEA_MIN) in short_errors["idea_description"]
    assert str(IDEA_MAX) in long_errors["idea_description"]

    llm = fake_llm(monkeypatch, LLM_REPLY_OK)
    response = client.post(URL, json={**BODY, "idea_description": "too short"})
    assert response.status_code == 422 and llm.calls == []


def test_row02_extra_details_too_long() -> None:
    _, errors = validate_submission(form(relevant_details="x" * (DETAILS_MAX + 1)))
    assert str(DETAILS_MAX) in errors["relevant_details"]


# --- row 3: industry "Other" without detail, not run ------------------------


def test_row03_other_industry_without_detail() -> None:
    submission, errors = validate_submission(form(industry="Other"))
    assert submission is None
    assert errors[api_client.INDUSTRY_OTHER_FIELD] == api_client.MSG_OTHER_REQUIRED


# --- row 4: missing LLM_API_KEY or LLM_MODEL, failed ------------------------


@pytest.mark.parametrize("missing", ["LLM_API_KEY", "LLM_MODEL"])
def test_row04_missing_llm_configuration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.delenv(missing)
    search = fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))

    result = run(client)
    assert result.status == "failed"
    assert result.errors[0].message == "The AI service is not configured."
    assert search.calls == []


# --- row 5: LLM timeout, 429, 401, 5xx, failed ------------------------------


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (requests.Timeout("slow"), llm_client.MSG_TIMEOUT),
        (
            llm_client.genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota"}}),
            llm_client.MSG_RATE_LIMIT,
        ),
        (
            llm_client.genai_errors.ClientError(401, {"error": {"code": 401, "message": "bad"}}),
            llm_client.MSG_KEY_REJECTED,
        ),
        (
            llm_client.genai_errors.ServerError(503, {"error": {"code": 503, "message": "busy"}}),
            llm_client.MSG_BUSY,
        ),
    ],
)
def test_row05_llm_api_errors_are_specific_and_readable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, error: BaseException, expected: str
) -> None:
    monkeypatch.setattr(llm_client, "RETRY_BACKOFF_S", (0.0, 0.0))

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.models = self

        def generate_content(self, **kwargs: object) -> object:
            raise error

        def close(self) -> None:
            pass

    monkeypatch.setattr(llm_client.genai, "Client", FakeClient)

    result = run(client)
    assert result.status == "failed"
    assert result.errors[0].message == expected


# --- rows 6 to 8: unusable LLM replies, failed ------------------------------


@pytest.mark.parametrize(
    ("reply", "row"),
    [
        (LLM_REPLY_NOT_JSON, "row06 non-JSON"),
        (LLM_REPLY_MISSING_FIELD, "row07 missing field"),
        (LLM_REPLY_EXTRA_KEY, "row07 extra key"),
        (LLM_REPLY_EMPTY, "row08 empty string"),
    ],
)
def test_rows06to08_unusable_llm_replies_retry_once_then_fail(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, reply: str, row: str
) -> None:
    llm = fake_llm(monkeypatch, reply)
    search = fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))

    result = run(client)
    assert result.status == "failed", row
    assert result.errors[0].code == "llm_invalid_response"
    assert result.errors[0].message == "Could not understand the AI reply. Please try again."
    assert len(llm.calls) == 2, "the agent retries exactly once"
    assert search.calls == []


# --- row 9: missing TAVILY_API_KEY, partial ---------------------------------


def test_row09_missing_search_key_is_partial(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    monkeypatch.delenv("TAVILY_API_KEY")

    result = run(client)
    assert result.status == "partial"
    assert result.idea is not None
    assert result.errors[0].stage == "search"
    assert result.warnings == ["Market and competitor research is not available, so only the structured idea is shown."]


# --- row 10: Tavily 401, 429, timeout, 5xx, partial -------------------------


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (tavily_status(401), search_client.MSG_KEY_REJECTED),
        (tavily_status(429), search_client.MSG_RATE_LIMIT),
        (TAVILY_TIMEOUT, search_client.MSG_TIMEOUT),
        (tavily_status(503), search_client.MSG_BUSY),
        (TAVILY_CONNECTION_ERROR, search_client.MSG_UNREACHABLE),
    ],
)
def test_row10_search_api_errors_are_specific_and_partial(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, outcome: object, expected: str
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(monkeypatch, outcome, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))

    result = run(client)
    assert result.status == "partial"
    assert result.idea is not None
    assert result.search is not None
    assert result.search.sections[0].error == expected


# --- row 11: Tavily non-JSON or no results, partial -------------------------


def test_row11_no_results_shows_the_no_results_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(monkeypatch, tavily_empty())

    result = run(client)
    assert result.status == "complete", "empty results are not a transport failure"
    assert result.search is not None and result.search.total_results == 0
    assert all(
        section.error == web_search_agent.MSG_NO_RESULTS for section in result.search.sections
    )


def test_row11_non_json_body_is_partial(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(monkeypatch, tavily_not_json(), FakeHTTPResponse(200, TAVILY_OK_RESPONSE))

    result = run(client)
    assert result.status == "partial"
    assert result.search is not None
    assert result.search.sections[0].error == search_client.MSG_BAD_REPLY


# --- row 12: one of four queries fails, partial -----------------------------


def test_row12_one_failed_query_only_affects_its_own_section(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(
        monkeypatch, tavily_status(429), FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty()
    )

    result = run(client)
    assert result.status == "partial"
    assert result.search is not None
    assert result.search.queries_failed == 1
    assert result.search.sections[0].error == search_client.MSG_RATE_LIMIT
    assert result.search.sections[1].results, "the other sections still returned results"
    assert result.warnings and "web searches failed" in result.warnings[0]


# --- row 13: backend not running, UI only -----------------------------------


def test_row13_backend_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    submission, errors = validate_submission(form())
    assert errors == {} and submission is not None

    fake_ui_post(monkeypatch, requests.ConnectionError("refused"))
    with pytest.raises(BackendError) as info:
        validate_idea(submission)
    assert info.value.message == api_client.MSG_BACKEND_DOWN
    assert "python app.py" in info.value.message


# --- row 14: unexpected exception anywhere, generic message -----------------


def test_row14_unexpected_exception_returns_the_generic_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, RuntimeError("provider internals"))
    response = client.post(URL, json=BODY)

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong. Please try again."}
    }
    assert "provider internals" not in response.text
    assert "Traceback" not in response.text


# --- Section 11.4 hardening review ------------------------------------------


def test_hardening_very_long_but_legal_input_is_accepted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())

    body = {
        **BODY,
        "idea_description": ("word " * (IDEA_MAX // 5)).strip()[:IDEA_MAX],
        "relevant_details": "x" * DETAILS_MAX,
    }
    assert run(client, body).status == "complete"


@pytest.mark.parametrize(
    "description",
    [
        "छोटे किसानों के लिए एक ऐप जो पत्ती की फोटो से फसल की बीमारी पहचानता है और इलाज बताता है।",
        "🌾🚜 An app that spots crop disease from a leaf photo 📷 and suggests a fix 💡 for farmers",
        'An app for "small" farmers <script>alert(1)</script> that detects crop disease; cost < 5% of yield',
    ],
    ids=["hindi", "emoji", "special-characters"],
)
def test_hardening_unusual_text_is_handled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, description: str
) -> None:
    fake_llm(monkeypatch, LLM_REPLY_OK)
    search = fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())

    result = run(client, {**BODY, "idea_description": description})
    assert result.status == "complete"
    queries = [call[1]["json"]["query"] for call in search.calls]
    assert all(query.strip() for query in queries)


def test_hardening_queries_never_go_out_empty_for_a_punctuation_only_idea(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json as json_module

    reply = json_module.dumps(
        {
            "idea_title": "...",
            "problem": "...",
            "solution": "???",
            "target_customers": ["..."],
            "industry": "!!!",
            "key_features": ["...", "???", "!!!"],
        }
    )
    fake_llm(monkeypatch, reply)
    search = fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())

    run(client)
    queries = [call[1]["json"]["query"] for call in search.calls]
    assert len(queries) == 4
    assert all(query.strip() for query in queries)


def test_hardening_a_second_submission_reuses_nothing_from_the_first(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repeated submit must not inherit the previous run's state."""
    fake_llm(monkeypatch, LLM_REPLY_OK)
    fake_tavily(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())
    first = run(client)

    fake_llm(monkeypatch, LLM_REPLY_NOT_JSON)
    second = run(client)

    assert first.status == "complete" and second.status == "failed"
    assert second.idea is None and second.search is None

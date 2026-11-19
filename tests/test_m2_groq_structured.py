"""Groq Structured Outputs and the repair retry, after the localhost run of 2026-10-28.

In that run Gemini answered 503 or 504 every time and Groq answered for it, in JSON object mode. For
the competitor analysis (Phase C), Groq's first reply was valid JSON with 3 validation issues; the
repair retry asked Gemini again (a second 504, after 28.8 s) and then Groq, which answered HTTP 400
json_validate_failed: its own JSON-mode check rejected what the model generated. The stage failed
with llm_invalid_response and the run ended partial after 142.95 s.

Now a structured call sends Groq the strict JSON schema of the model that validates its reply, so
the reply is generated to match it; the repair retry after a Gemini failure goes to Groq only; and
a Groq reply rejected as invalid JSON gets the same one retry as any unusable reply. The log keeps
issue paths and types, Groq's error code and lengths, never a value, a prompt or a reply.

The run's log counted the 3 issues but did not record them. The three used here are the kinds JSON
object mode allows and the strict schema rules out, built on the standard fake reply.

Both providers are faked and time is simulated, so nothing touches the network.
"""

import json
import logging
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field, ValidationError

from models.schemas import (
    CandidateList,
    CompetitorAnalysisDraft,
    ExtractedIdea,
    MarketOpportunityDraft,
    PipelineResult,
)
from tests.domain_fakes import DOMAINS
from tests.fakes import LLM_REPLY_OK, VALID_EXTRACTION, FakeHTTPResponse
from tests.m2_fakes import ANALYSIS_REPLY, CANDIDATE_REPLY, MARKET_REPLY, analysis_draft
from tests.pipeline_fakes import PIPELINE_MARKET_REPLY, PIPELINE_SEARCH, competitor_replies, market_reply
from tests.test_m2_groq_fallback import (
    BODY,
    FULL_URL,
    GROQ_KEY,
    SYSTEM,
    USER,
    Clock,
    Slow,
    gemini_error,
    groq_error,
    groq_reply,
    use_providers,
    use_searches,
)
from utils import deadline, groq_client, llm_client
from utils.deadline import time_limit
from utils.errors import LLMAPIError, LLMInvalidResponseError
from utils.structured import PROBLEM_NOT_JSON, RETRY_INSTRUCTION, call_structured, issue_locations

REPLY_MODELS = (ExtractedIdea, MarketOpportunityDraft, CandidateList, CompetitorAnalysisDraft)
FAILED_GENERATION = '{"competitors": [{"name": "FAILED-GENERATION-TEXT"'
CANDIDATES, ANALYSIS = competitor_replies()

# Three slips JSON object mode allows: null for a text field, null for the price object, and a cell
# status outside the enum. Each breaks the Pydantic model, and the strict schema rules each out.
THREE_ISSUES = (
    ("competitors.1.relevance_note", "string_type"),
    ("competitors.2.pricing_model", "model_type"),
    ("comparison.rows.0.cells.1.status", "literal_error"),
)


def three_issue_reply() -> dict:
    reply = analysis_draft()
    reply["competitors"][1]["relevance_note"] = None
    reply["competitors"][2]["pricing_model"] = None
    reply["comparison"]["rows"][0]["cells"][1]["status"] = "PARTLY-VALUE"
    return reply


def json_validate_failed() -> FakeHTTPResponse:
    """Groq's answer when its JSON-mode check rejects the generated text (HTTP 400)."""
    return FakeHTTPResponse(
        400,
        {
            "error": {
                "message": "Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.",
                "type": "invalid_request_error",
                "code": "json_validate_failed",
                "failed_generation": FAILED_GENERATION,
            }
        },
    )


@pytest.fixture
def groq_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", GROQ_KEY)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(deadline, "clock", fake)
    return fake


def schema_nodes(node: Any):
    if isinstance(node, dict):
        yield node
        for key, value in node.items():
            if key in ("properties", "$defs"):
                for sub in value.values():
                    yield from schema_nodes(sub)
            elif key in ("items", "anyOf"):
                yield from schema_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from schema_nodes(item)


def nullable_fields(schema: dict) -> set[str]:
    objects = {"#": schema, **{f"#{name}": sub for name, sub in schema.get("$defs", {}).items()}}
    return {
        f"{where}.{field}"
        for where, obj in objects.items()
        for field, sub in obj.get("properties", {}).items()
        if {"type": "null"} in sub.get("anyOf", [])
    }


def strict_validator(model: type[BaseModel]) -> Draft202012Validator:
    return Draft202012Validator(groq_client.strict_schema(model))


def response_formats(requests: list) -> list[str]:
    return [
        request.body["response_format"].get("json_schema", {}).get("name", request.body["response_format"]["type"])
        for request in requests
    ]


# --- the strict schema -----------------------------------------------------------------------


@pytest.mark.parametrize("model", REPLY_MODELS, ids=lambda model: model.__name__)
def test_every_reply_schema_meets_the_strict_mode_rules(model: type[BaseModel]) -> None:
    """https://console.groq.com/docs/structured-outputs: every property required, additionalProperties
    false on every object, and only the documented subset of JSON Schema."""
    schema = groq_client.strict_schema(model)
    nodes = list(schema_nodes(schema))

    assert schema["type"] == "object"
    for node in nodes:
        assert set(node) <= groq_client.STRICT_KEYWORDS, sorted(set(node) - groq_client.STRICT_KEYWORDS)
        if "properties" in node:
            assert node["required"] == list(node["properties"]) and node["additionalProperties"] is False
        if "$ref" in node:
            assert node == {"$ref": node["$ref"]} and node["$ref"].removeprefix("#/$defs/") in schema.get("$defs", {})
    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("model", REPLY_MODELS, ids=lambda model: model.__name__)
def test_a_field_is_nullable_in_the_strict_schema_exactly_when_pydantic_accepts_null(model: type[BaseModel]) -> None:
    assert nullable_fields(groq_client.strict_schema(model)) == nullable_fields(model.model_json_schema())


@pytest.mark.parametrize(
    ("model", "reply"),
    [
        (ExtractedIdea, VALID_EXTRACTION),
        (MarketOpportunityDraft, MARKET_REPLY),
        (MarketOpportunityDraft, PIPELINE_MARKET_REPLY),
        (CandidateList, CANDIDATE_REPLY),
        (CompetitorAnalysisDraft, ANALYSIS_REPLY),
        *[(MarketOpportunityDraft, json.loads(domain.market_reply)) for domain in DOMAINS],
        *[(CandidateList, json.loads(domain.candidate_reply)) for domain in DOMAINS],
        *[(CompetitorAnalysisDraft, json.loads(domain.analysis_reply)) for domain in DOMAINS],
    ],
    ids=lambda value: value.__name__ if isinstance(value, type) else "",
)
def test_every_reply_the_app_accepts_fits_the_strict_schema(model: type[BaseModel], reply: dict) -> None:
    """Strict mode rules out no reply the app accepts: each test reply, with every field written
    out as strict mode requires, is valid against the strict schema."""
    complete = model.model_validate(reply).model_dump(mode="json")
    assert list(strict_validator(model).iter_errors(complete)) == []


def test_the_three_issues_break_the_model_and_the_strict_schema_rules_each_out() -> None:
    reply = three_issue_reply()
    with pytest.raises(ValidationError) as info:
        CompetitorAnalysisDraft.model_validate_json(json.dumps(reply))

    found = {(".".join(str(part) for part in error["loc"]), error["type"]) for error in info.value.errors()}
    assert found == set(THREE_ISSUES) and info.value.error_count() == 3
    paths = {"/".join(str(part) for part in error.absolute_path) for error in strict_validator(CompetitorAnalysisDraft).iter_errors(reply)}
    assert paths == {path.replace(".", "/") for path, _ in THREE_ISSUES}


def test_limits_outside_the_strict_subset_are_still_checked_by_the_model() -> None:
    """Lengths, counts and the sourced-needs-a-source rule are not in the strict subset, so the
    schema leaves them out and Pydantic still enforces them, as before."""
    reply = analysis_draft()
    reply["competitors"][0]["name"] = "N" * 81
    reply["competitors"][0]["strengths"][0]["source_ids"] = []
    reply["data_quality"]["notes"] = [" "]

    assert list(strict_validator(CompetitorAnalysisDraft).iter_errors(reply)) == []
    with pytest.raises(ValidationError) as info:
        CompetitorAnalysisDraft.model_validate(reply)
    assert {error["type"] for error in info.value.errors()} == {"string_too_long", "value_error", "string_too_short"}


class Mapping(BaseModel):
    scores: dict[str, int]


class Ranged(BaseModel):
    share: float = Field(ge=0, le=1)


class Pair(BaseModel):
    point: tuple[int, int]


class Single(BaseModel):
    kind: Literal["only"]


@pytest.mark.parametrize("model", [Mapping, Ranged, Pair], ids=["dict", "minimum", "prefixItems"])
def test_a_model_strict_mode_cannot_express_uses_json_object_mode(
    caplog: pytest.LogCaptureFixture, model: type[BaseModel]
) -> None:
    """Only the documented subset is sent. A keyword outside it, other than a length or count limit
    Pydantic checks anyway, is not dropped: the call falls back to JSON object mode instead."""
    with pytest.raises(ValueError):
        groq_client.strict_schema(model)
    with caplog.at_level(logging.WARNING):
        assert groq_client.response_format(model) == {"type": "json_object"}
    assert f"no strict schema for {model.__name__}" in caplog.text


def test_a_single_literal_becomes_an_enum_and_no_model_means_json_object_mode() -> None:
    assert groq_client.strict_schema(Single)["properties"]["kind"] == {"enum": ["only"], "type": "string"}
    assert groq_client.response_format(None) == {"type": "json_object"}


def test_the_strict_schema_is_a_fresh_copy_each_time() -> None:
    first = groq_client.strict_schema(CompetitorAnalysisDraft)
    first["properties"].clear()
    assert groq_client.strict_schema(CompetitorAnalysisDraft)["properties"]


# --- what Groq is sent -----------------------------------------------------------------------


def test_each_structured_call_sends_groq_the_strict_schema_of_its_own_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, groq_key: None
) -> None:
    use_searches(monkeypatch)
    replies = (LLM_REPLY_OK, market_reply(), CANDIDATES, ANALYSIS)
    providers = use_providers(monkeypatch, [gemini_error(503)], [groq_reply(reply) for reply in replies])
    result = PipelineResult.model_validate(client.post(FULL_URL, json=BODY).json())

    assert result.status == "complete" and result.competitors is not None
    assert response_formats(providers.groq.requests) == [
        "ExtractedIdea",
        "MarketOpportunityDraft",
        "CandidateList",
        "CompetitorAnalysisDraft",
    ]
    phase_c = providers.groq.requests[3].body["response_format"]
    assert phase_c == {
        "type": "json_schema",
        "json_schema": {
            "name": "CompetitorAnalysisDraft",
            "strict": True,
            "schema": groq_client.strict_schema(CompetitorAnalysisDraft),
        },
    }
    assert len(providers.gemini.calls) == 4, "each structured call still asks Gemini first"


def test_a_call_outside_a_structured_call_keeps_json_object_mode(
    monkeypatch: pytest.MonkeyPatch, groq_key: None
) -> None:
    providers = use_providers(monkeypatch, [gemini_error(503)], [groq_reply("{}")])
    assert llm_client.generate_json(SYSTEM, USER) == "{}"
    assert providers.groq.requests[0].body["response_format"] == {"type": "json_object"}


def test_the_structured_scope_ends_with_the_call_even_when_it_fails(
    monkeypatch: pytest.MonkeyPatch, groq_key: None
) -> None:
    use_providers(monkeypatch, [gemini_error(503)], [groq_error(503)])
    with pytest.raises(LLMAPIError):
        call_structured(SYSTEM, USER, ExtractedIdea, caller=llm_client.generate_json)
    assert llm_client._structured_call.get() is None

    providers = use_providers(monkeypatch, ["{}"])
    with pytest.raises(LLMInvalidResponseError):
        call_structured(SYSTEM, USER, ExtractedIdea, caller=llm_client.generate_json)
    assert len(providers.gemini.calls) == 2 and providers.groq.requests == [], "a new call asks Gemini first"


# --- the repair retry ------------------------------------------------------------------------


def test_after_a_gemini_failure_the_repair_retry_goes_to_groq_only(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None
) -> None:
    providers = use_providers(
        monkeypatch, [gemini_error(504, "DEADLINE_EXCEEDED")], [groq_reply(json.dumps(three_issue_reply())), groq_reply(ANALYSIS)]
    )
    with caplog.at_level(logging.INFO):
        draft = call_structured(SYSTEM, USER, CompetitorAnalysisDraft, caller=llm_client.generate_json)

    assert draft == CompetitorAnalysisDraft.model_validate_json(ANALYSIS)
    assert len(providers.gemini.calls) == 1 and len(providers.groq.requests) == 2
    retry_prompt = providers.groq.requests[1].body["messages"][1]["content"]
    assert retry_prompt.startswith(USER) and RETRY_INSTRUCTION.split("{")[0] in retry_prompt
    for path, _ in THREE_ISSUES:
        assert path in retry_prompt, "the retry names each problem"
    assert "Gemini failed earlier in this call (server_error, HTTP 504); sending the retry to Groq only" in caplog.text


def test_a_gemini_answer_is_still_repaired_on_gemini(monkeypatch: pytest.MonkeyPatch, groq_key: None) -> None:
    providers = use_providers(monkeypatch, [json.dumps(three_issue_reply()), ANALYSIS])
    draft = call_structured(SYSTEM, USER, CompetitorAnalysisDraft, caller=llm_client.generate_json)

    assert draft == CompetitorAnalysisDraft.model_validate_json(ANALYSIS)
    assert len(providers.gemini.calls) == 2 and providers.groq.requests == []


def test_a_reply_groq_rejects_as_invalid_json_gets_the_one_retry(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None
) -> None:
    providers = use_providers(monkeypatch, [gemini_error(503)], [json_validate_failed(), groq_reply(ANALYSIS)])
    with caplog.at_level(logging.INFO):
        draft = call_structured(SYSTEM, USER, CompetitorAnalysisDraft, caller=llm_client.generate_json)

    assert draft == CompetitorAnalysisDraft.model_validate_json(ANALYSIS)
    assert len(providers.gemini.calls) == 1 and len(providers.groq.requests) == 2
    assert RETRY_INSTRUCTION.format(problem=PROBLEM_NOT_JSON) in providers.groq.requests[1].body["messages"][1]["content"]
    assert "structured reply was rejected as invalid JSON, retrying once" in caplog.text


def test_two_invalid_json_rejections_end_the_call(monkeypatch: pytest.MonkeyPatch, groq_key: None) -> None:
    providers = use_providers(monkeypatch, [gemini_error(503)], [json_validate_failed()])
    with pytest.raises(LLMInvalidResponseError):
        call_structured(SYSTEM, USER, CompetitorAnalysisDraft, caller=llm_client.generate_json)
    assert len(providers.gemini.calls) == 1 and len(providers.groq.requests) == 2, "bounded: two attempts"


def test_malformed_output_gets_the_one_retry_then_fails_with_no_content_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None
) -> None:
    providers = use_providers(monkeypatch, [gemini_error(503)], [groq_reply('{"competitors": [MALFORMED-TEXT')])
    with caplog.at_level(logging.INFO):
        with pytest.raises(LLMInvalidResponseError):
            call_structured(SYSTEM, USER, CompetitorAnalysisDraft, caller=llm_client.generate_json)

    assert len(providers.gemini.calls) == 1 and len(providers.groq.requests) == 2
    assert "structured reply failed after retry (1 issues: reply json_invalid)" in caplog.text
    assert "MALFORMED-TEXT" not in caplog.text


def test_the_repair_retry_keeps_the_deadline_rules(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None, clock: Clock
) -> None:
    providers = use_providers(
        monkeypatch,
        [Slow(20.0, gemini_error(504))],
        [Slow(5.0, groq_reply(json.dumps(three_issue_reply()))), groq_reply(ANALYSIS)],
        clock,
    )
    with time_limit(34), caplog.at_level(logging.WARNING):
        with pytest.raises(LLMAPIError) as info:
            call_structured(SYSTEM, USER, CompetitorAnalysisDraft, caller=llm_client.generate_json)

    assert info.value.user_message == llm_client.MSG_TIME_LIMIT
    assert len(providers.groq.requests) == 1, "9 s left: the retry is not sent"
    assert "LLM call not sent: 9.0s left, below the 10s minimum deadline" in caplog.text


@pytest.mark.parametrize(("left", "timeouts"), [(58.75, [30.0, 30.0]), (12.0, [17.0, 12.0])])
def test_the_repair_retry_waits_at_most_the_time_left(
    monkeypatch: pytest.MonkeyPatch, groq_key: None, clock: Clock, left: float, timeouts: list
) -> None:
    """The first Groq reply takes 5 s, so the retry starts with `left` seconds to go."""
    providers = use_providers(
        monkeypatch,
        [gemini_error(504)],
        [Slow(5.0, groq_reply(json.dumps(three_issue_reply()))), groq_reply(ANALYSIS)],
        clock,
    )
    with time_limit(100):
        clock.advance(100 - left - 5)
        call_structured(SYSTEM, USER, CompetitorAnalysisDraft, caller=llm_client.generate_json)
    assert [request.timeout for request in providers.groq.requests] == timeouts


# --- what is logged --------------------------------------------------------------------------


def test_the_issue_paths_and_types_are_logged_never_their_values(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None
) -> None:
    use_providers(monkeypatch, [gemini_error(503)], [groq_reply(json.dumps(three_issue_reply())), groq_reply(ANALYSIS)])
    with caplog.at_level(logging.INFO):
        call_structured(SYSTEM, USER, CompetitorAnalysisDraft, caller=llm_client.generate_json)

    expected = "; ".join(f"{path} {kind}" for path, kind in THREE_ISSUES)
    assert f"structured reply invalid (3 issues: {expected}), retrying once" in caplog.text
    assert "PARTLY-VALUE" not in caplog.text and "Plantix" not in caplog.text


def test_issue_locations_hide_unusual_path_parts_and_cap_the_list() -> None:
    class Tags(BaseModel):
        values: list[int]

    with pytest.raises(ValidationError) as info:
        Tags.model_validate({"values": ["x"] * 12})
    text = issue_locations(info.value)
    assert text.startswith("values.0 int_parsing; values.1 int_parsing") and text.endswith("; 4 more")

    with pytest.raises(ValidationError) as info:
        ExtractedIdea.model_validate({**VALID_EXTRACTION, "odd key!": 1})
    assert issue_locations(info.value) == "? extra_forbidden"


def test_a_groq_400_logs_its_code_and_length_never_the_generated_text(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None
) -> None:
    use_providers(monkeypatch, [gemini_error(503)], [json_validate_failed()])
    with caplog.at_level(logging.WARNING):
        with pytest.raises(LLMInvalidResponseError):
            call_structured(SYSTEM, USER, CompetitorAnalysisDraft, caller=llm_client.generate_json)

    note = f"invalid_json, HTTP 400, code json_validate_failed, {len(FAILED_GENERATION)} characters generated"
    assert caplog.text.count(f"Groq fallback failed ({note})") == 2
    assert "FAILED-GENERATION-TEXT" not in caplog.text and "Failed to validate" not in caplog.text


def test_an_unusual_groq_error_code_is_not_logged(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None) -> None:
    body = {"error": {"message": "x", "type": "invalid_request_error", "code": "Not An Identifier <b>"}}
    use_providers(monkeypatch, [gemini_error(503)], [FakeHTTPResponse(400, body)])
    with caplog.at_level(logging.WARNING):
        with pytest.raises(LLMAPIError):
            llm_client.generate_json(SYSTEM, USER)
    assert "Groq fallback failed (invalid_request, HTTP 400)" in caplog.text and "Identifier" not in caplog.text


def test_groq_token_counts_and_finish_reason_are_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None
) -> None:
    reply = groq_reply("{}")
    reply._json_data["usage"] = {
        "prompt_tokens": 3120,
        "completion_tokens": 4096,
        "completion_tokens_details": {"reasoning_tokens": 1200},
    }
    reply._json_data["choices"][0]["finish_reason"] = "length"
    use_providers(monkeypatch, [gemini_error(503)], [reply])
    with caplog.at_level(logging.INFO):
        llm_client.generate_json(SYSTEM, USER)

    assert f"({groq_client.MODEL}): 3120 prompt + 4096 completion tokens (1200 reasoning), finish length" in caplog.text


# --- the live run of 2026-10-28, replayed ----------------------------------------------------
# Each call takes the time it took in that run's log; searches take their logged times.

LIVE_SEARCH_SECONDS = (20.69, 7.88, 16.28)  # standard, market-size, competitor searches


def use_live_run(monkeypatch: pytest.MonkeyPatch, clock: Clock, retry_reply: Any) -> Any:
    use_searches(monkeypatch, clock, seconds=LIVE_SEARCH_SECONDS)
    return use_providers(
        monkeypatch,
        [
            Slow(3.5, gemini_error(503, "UNAVAILABLE")),  # extraction
            Slow(2.6, gemini_error(503, "UNAVAILABLE")),  # market analysis
            Slow(9.3, gemini_error(503, "UNAVAILABLE")),  # Phase A
            Slow(28.8, gemini_error(504, "DEADLINE_EXCEEDED")),  # Phase C, and the old retry
        ],
        [
            Slow(1.83, groq_reply(LLM_REPLY_OK)),
            Slow(5.14, groq_reply(market_reply())),
            Slow(1.79, groq_reply(CANDIDATES)),
            Slow(5.44, groq_reply(json.dumps(three_issue_reply()))),  # Phase C: 3 issues
            Slow(3.99, retry_reply),  # the repair retry
        ],
        clock,
    )


LIVE_RUN_SECONDS = 3.5 + 1.83 + 20.69 + 7.88 + 2.6 + 5.14 + 9.3 + 1.79 + 16.28 + 28.8 + 5.44 + 3.99


def test_the_live_failure_now_skips_the_second_gemini_wait_and_keeps_the_partial_result(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, groq_key: None, clock: Clock
) -> None:
    providers = use_live_run(monkeypatch, clock, json_validate_failed())
    with caplog.at_level(logging.INFO):
        response = client.post(FULL_URL, json=BODY)
    result = PipelineResult.model_validate(response.json())

    assert len(providers.gemini.calls) == 4, "Phase C asked Gemini once, not again for the retry"
    assert len(providers.groq.requests) == 5
    assert clock.now == pytest.approx(LIVE_RUN_SECONDS), "28.8 s sooner than the same calls with a second Gemini wait"
    assert result.status == "partial"
    assert [(e.stage, e.code, e.message) for e in result.errors] == [
        ("competitor_analysis", "llm_invalid_response", LLMInvalidResponseError.default_message)
    ]
    assert result.idea is not None and result.search == PIPELINE_SEARCH
    assert result.market is not None and result.market_search is not None, "the finished stages are kept"
    assert result.competitors is None and result.competitor_candidates == [] and result.competitor_search is None
    assert "FAILED-GENERATION-TEXT" not in caplog.text and GROQ_KEY not in response.text


def test_the_live_run_completes_when_the_repair_retry_succeeds(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, groq_key: None, clock: Clock
) -> None:
    providers = use_live_run(monkeypatch, clock, groq_reply(ANALYSIS))
    result = PipelineResult.model_validate(client.post(FULL_URL, json=BODY).json())

    assert result.status == "complete" and result.errors == []
    assert result.competitors is not None and result.market is not None
    assert len(providers.gemini.calls) == 4 and len(providers.groq.requests) == 5
    assert clock.now == pytest.approx(LIVE_RUN_SECONDS) and clock.now < 162


# --- grounding -------------------------------------------------------------------------------


def test_the_guards_still_drop_an_invented_competitor_in_a_groq_reply(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, groq_key: None
) -> None:
    reply = analysis_draft()
    invented = dict(reply["competitors"][2], name="AgroGhost", relevance_note="A crop diagnosis app.", source_ids=["S1"])
    reply["competitors"].append(invented)
    replies = (LLM_REPLY_OK, market_reply(), CANDIDATES, json.dumps(reply))

    use_searches(monkeypatch)
    use_providers(monkeypatch, [gemini_error(503)], [groq_reply(text) for text in replies])
    on_groq = PipelineResult.model_validate(client.post(FULL_URL, json=BODY).json())
    use_providers(monkeypatch, list(replies))
    on_gemini = PipelineResult.model_validate(client.post(FULL_URL, json=BODY).json())

    assert on_groq.competitors is not None
    assert "AgroGhost" not in [competitor.name for competitor in on_groq.competitors.competitors]
    assert any("AgroGhost" in warning for warning in on_groq.warnings), "dropped with a warning, as before"
    assert on_groq.model_dump(exclude={"timings", "usage"}) == on_gemini.model_dump(exclude={"timings", "usage"})

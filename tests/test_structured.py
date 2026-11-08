"""Structured LLM call helper (KIRO_PROMPT_M2.md Section 5.3)."""

import json

import pytest
from pydantic import BaseModel

from agents import extraction_agent
from models.schemas import ExtractedIdea
from tests.fakes import (
    LLM_REPLY_EMPTY,
    LLM_REPLY_EXTRA_KEY,
    LLM_REPLY_FENCED,
    LLM_REPLY_NOT_JSON,
    LLM_REPLY_OK,
    VALID_EXTRACTION,
    make_sequence,
)
from utils import llm_client, structured
from utils.errors import LLMAPIError, LLMConfigError, LLMInvalidResponseError


class Tiny(BaseModel):
    name: str
    count: int


def test_valid_reply_is_validated_into_the_model() -> None:
    fake = make_sequence(json.dumps({"name": "LeafDoc", "count": 3}))
    assert structured.call_structured("sys", "usr", Tiny, caller=fake) == Tiny(name="LeafDoc", count=3)
    assert fake.calls[0][0] == ("sys", "usr")


def test_code_fenced_reply_is_unwrapped_once() -> None:
    fake = make_sequence(LLM_REPLY_FENCED)
    assert structured.call_structured("sys", "usr", ExtractedIdea, caller=fake).model_dump() == VALID_EXTRACTION
    assert len(fake.calls) == 1


@pytest.mark.parametrize("bad", [LLM_REPLY_NOT_JSON, LLM_REPLY_EMPTY, LLM_REPLY_EXTRA_KEY])
def test_invalid_then_valid_retries_exactly_once(bad: str) -> None:
    fake = make_sequence(bad, LLM_REPLY_OK)
    idea = structured.call_structured("sys", "usr", ExtractedIdea, caller=fake)
    assert idea.model_dump() == VALID_EXTRACTION
    assert len(fake.calls) == 2
    retry_system, retry_user = fake.calls[1][0]
    assert retry_system == "sys"
    assert retry_user.startswith("usr\n\n")
    assert "could not be used because" in retry_user


def test_retry_prompt_names_the_problem_without_echoing_the_reply() -> None:
    fake = make_sequence(LLM_REPLY_EXTRA_KEY, LLM_REPLY_OK)
    structured.call_structured("sys", "usr", ExtractedIdea, caller=fake)
    retry_user = fake.calls[1][0][1]
    assert "market_size" in retry_user
    assert "USD 5 billion" not in retry_user


def test_invalid_twice_raises_invalid_response() -> None:
    fake = make_sequence(LLM_REPLY_NOT_JSON, LLM_REPLY_NOT_JSON, LLM_REPLY_OK)
    with pytest.raises(LLMInvalidResponseError):
        structured.call_structured("sys", "usr", ExtractedIdea, caller=fake)
    assert len(fake.calls) == 2


@pytest.mark.parametrize("error", [LLMConfigError(), LLMAPIError("busy")])
def test_config_and_api_errors_are_not_retried(error: Exception) -> None:
    fake = make_sequence(error, LLM_REPLY_OK)
    with pytest.raises(type(error)):
        structured.call_structured("sys", "usr", ExtractedIdea, caller=fake)
    assert len(fake.calls) == 1


def test_api_error_during_the_retry_passes_through() -> None:
    fake = make_sequence(LLM_REPLY_NOT_JSON, LLMAPIError("timeout"))
    with pytest.raises(LLMAPIError):
        structured.call_structured("sys", "usr", ExtractedIdea, caller=fake)


def test_default_caller_is_the_llm_client_looked_up_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_sequence(LLM_REPLY_OK)
    monkeypatch.setattr(llm_client, "generate_json", fake)
    assert structured.call_structured("sys", "usr", ExtractedIdea).idea_title == VALID_EXTRACTION["idea_title"]
    assert len(fake.calls) == 1


def test_validation_summary_is_short_and_has_no_input_values() -> None:
    from pydantic import ValidationError

    try:
        Tiny.model_validate_json(json.dumps({"name": "secret-ish value", "count": "x" * 2000}))
    except ValidationError as exc:
        summary = structured.describe_validation_error(exc)
    assert "count" in summary
    assert "secret-ish value" not in summary and "xxxx" not in summary
    assert len(summary) <= 500


def test_extraction_reuses_the_shared_helper_not_a_copy() -> None:
    assert extraction_agent.strip_code_fences is structured.strip_code_fences
    assert extraction_agent.RETRY_INSTRUCTION is structured.RETRY_INSTRUCTION
    for name in ("_parse", "_describe", "_FENCE_PATTERN"):
        assert not hasattr(extraction_agent, name)

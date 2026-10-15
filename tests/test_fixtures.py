import socket

import pytest
import requests

from tests.fakes import (
    TAVILY_TIMEOUT,
    make_sequence,
    tavily_not_json,
    tavily_status,
)


def test_fake_llm_returns_valid_json(fake_llm_ok) -> None:
    from models.schemas import ExtractedIdea

    assert ExtractedIdea.model_validate_json(fake_llm_ok("system", "user"))
    assert len(fake_llm_ok.calls) == 1


def test_fake_tavily_has_answer_and_results(fake_tavily_ok) -> None:
    body = fake_tavily_ok("https://api.tavily.com/search", json={}).json()
    assert body["answer"] and len(body["results"]) == 2


def test_make_sequence_raises_and_repeats_last() -> None:
    fake = make_sequence(TAVILY_TIMEOUT, tavily_status(429))
    with pytest.raises(requests.Timeout):
        fake()
    assert fake().status_code == 429
    assert fake().status_code == 429


def test_failure_helpers_behave_like_requests() -> None:
    with pytest.raises(ValueError):
        tavily_not_json().json()
    with pytest.raises(requests.HTTPError):
        tavily_status(401).raise_for_status()


def test_network_is_blocked() -> None:
    with pytest.raises(RuntimeError, match="Network access is blocked"):
        socket.create_connection(("93.184.216.34", 443), timeout=1)

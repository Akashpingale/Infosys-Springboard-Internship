"""Reusable query execution (KIRO_PROMPT_M2.md Section 5.5)."""

import pytest

from agents import web_search_agent as agent
from models.schemas import ExtractedIdea
from tests.fakes import (
    TAVILY_CONNECTION_ERROR,
    TAVILY_OK_RESPONSE,
    TAVILY_TIMEOUT,
    VALID_EXTRACTION,
    FakeHTTPResponse,
    make_sequence,
    tavily_empty,
    tavily_status,
)
from utils import search_client
from utils.errors import SearchAPIError


def use_fake_post(monkeypatch: pytest.MonkeyPatch, *outcomes: object):
    fake = make_sequence(*outcomes)
    monkeypatch.setattr(search_client.requests, "post", fake)
    return fake


def body(*urls: str) -> FakeHTTPResponse:
    results = [{"url": u, "title": u, "content": f"text about {u}", "score": 0.5} for u in urls]
    return FakeHTTPResponse(200, {"answer": None, "results": results})


def test_runs_a_custom_query_list_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, body("https://a.example"), body("https://b.example"))
    result = agent.run_queries([("Competitor: LeafDoc", "LeafDoc pricing features"), ("Alternatives", "crop app alternatives")])
    assert [s.label for s in result.sections] == ["Competitor: LeafDoc", "Alternatives"]
    assert [call[1]["json"]["query"] for call in fake.calls] == ["LeafDoc pricing features", "crop app alternatives"]
    assert result.total_results == 2 and result.queries_failed == 0


def test_passes_options_and_uses_milestone1_defaults_otherwise(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, body("https://a.example"))
    agent.run_queries([("A", "a")], max_results=5, depth="advanced")
    sent = fake.calls[0][1]["json"]
    assert (sent["max_results"], sent["search_depth"], sent["include_answer"]) == (5, "advanced", True)

    fake = use_fake_post(monkeypatch, body("https://a.example"))
    agent.run_queries([("A", "a")])
    sent = fake.calls[0][1]["json"]
    assert (sent["max_results"], sent["search_depth"]) == (3, "basic")


def test_an_explicit_zero_is_not_replaced_by_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, body())
    agent.run_queries([("A", "a")], max_results=0)
    assert fake.calls[0][1]["json"]["max_results"] == 0


def test_duplicates_are_removed_across_the_custom_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, body("https://same.example", "https://a.example"), body("https://same.example"))
    result = agent.run_queries([("A", "a"), ("B", "b")])
    assert [r.url for r in result.sections[0].results] == ["https://same.example", "https://a.example"]
    assert result.sections[1].results == []
    assert result.sections[1].error == agent.MSG_NO_RESULTS


@pytest.mark.parametrize("failure", [tavily_status(429), TAVILY_TIMEOUT, TAVILY_CONNECTION_ERROR])
def test_one_failed_query_is_recorded_and_the_rest_continue(monkeypatch: pytest.MonkeyPatch, failure: object) -> None:
    use_fake_post(monkeypatch, failure, body("https://b.example"))
    result = agent.run_queries([("A", "a"), ("B", "b")])
    assert result.queries_failed == 1
    assert result.sections[0].error and result.sections[0].results == []
    assert [r.url for r in result.sections[1].results] == ["https://b.example"]


def test_all_queries_failing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, tavily_status(503))
    with pytest.raises(SearchAPIError) as info:
        agent.run_queries([("A", "a"), ("B", "b")])
    assert info.value.user_message == agent.MSG_ALL_QUERIES_FAILED


def test_missing_key_fails_every_query_without_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, body("https://a.example"))
    monkeypatch.delenv("TAVILY_API_KEY")
    with pytest.raises(SearchAPIError):
        agent.run_queries([("A", "a")])
    assert fake.calls == []


def test_an_empty_query_list_returns_an_empty_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, body("https://a.example"))
    result = agent.run_queries([])
    assert (result.sections, result.total_results, result.queries_failed) == ([], 0, 0)
    assert fake.calls == []


def test_run_web_search_is_run_queries_over_the_template_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    idea = ExtractedIdea(**VALID_EXTRACTION)
    use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())
    via_wrapper = agent.run_web_search(idea)
    use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())
    via_queries = agent.run_queries(agent.generate_queries(idea))
    assert via_wrapper == via_queries


# --- Task 1 bug-fix phase: an optional snippet builder ---------------------------------------

LONG_CONTENT = ("Intro sentence about farming apps and their many uses in rural areas. " * 5) + (
    "The market was valued at USD 1.2 billion in 2024."
)


def long_body() -> FakeHTTPResponse:
    return FakeHTTPResponse(
        200, {"answer": None, "results": [{"title": "Report", "url": "https://a.example", "content": LONG_CONTENT}]}
    )


def test_without_a_builder_snippets_are_the_milestone1_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, long_body())
    snippet = agent.run_queries([("A", "a")]).sections[0].results[0].snippet
    assert snippet == agent._snippet(LONG_CONTENT) and "USD 1.2 billion" not in snippet


def test_a_builder_gets_the_content_and_the_query_and_chooses_the_snippet(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, long_body())
    seen: list[tuple[str, str]] = []

    def builder(content: str, query: str) -> str:
        seen.append((content, query))
        return "The market was valued at USD 1.2 billion in 2024."

    result = agent.run_queries([("A", "crop app market size")], snippet=builder)
    assert seen == [(LONG_CONTENT, "crop app market size")]
    assert result.sections[0].results[0].snippet == "The market was valued at USD 1.2 billion in 2024."


@pytest.mark.parametrize("bad", ["", "   ", "x" * 301], ids=["empty", "blank", "too long"])
def test_an_unusable_builder_snippet_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    use_fake_post(monkeypatch, long_body())
    result = agent.run_queries([("A", "a")], snippet=lambda content, query: bad)
    assert result.sections[0].results[0].snippet == agent._snippet(LONG_CONTENT)

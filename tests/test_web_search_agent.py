import pytest

from agents import web_search_agent as agent
from models.schemas import SNIPPET_MAX, ExtractedIdea, SearchBundle
from tests.fakes import (
    TAVILY_OK_RESPONSE,
    TAVILY_TIMEOUT,
    VALID_EXTRACTION,
    FakeHTTPResponse,
    make_sequence,
    tavily_empty,
    tavily_not_json,
    tavily_status,
)
from utils import search_client
from utils.errors import SearchAPIError

IDEA = ExtractedIdea(**VALID_EXTRACTION)
EXPECTED_LABELS = [
    agent.LABEL_MARKET,
    agent.LABEL_COMPETITORS,
    agent.LABEL_DEMAND,
    agent.LABEL_NEWS,
]


def use_fake_post(monkeypatch: pytest.MonkeyPatch, *outcomes: object):
    fake = make_sequence(*outcomes)
    monkeypatch.setattr(search_client.requests, "post", fake)
    return fake


def body(results: list[dict], answer: str | None = None) -> FakeHTTPResponse:
    return FakeHTTPResponse(200, {"answer": answer, "results": results})


def result(url: str, title: str = "A title", content: str = "Some content", score: float = 0.5):
    return {"url": url, "title": title, "content": content, "score": score}


# --- query generation --------------------------------------------------------


def test_four_labelled_queries_in_order() -> None:
    queries = agent.generate_queries(IDEA)
    assert [label for label, _ in queries] == EXPECTED_LABELS


def test_queries_are_distinct_non_empty_and_trimmed() -> None:
    texts = [query for _, query in agent.generate_queries(IDEA)]
    assert len(set(texts)) == 4
    assert all(text.strip() for text in texts)
    assert all(len(text) <= agent.MAX_QUERY_CHARS for text in texts)


def test_queries_use_the_extracted_fields() -> None:
    queries = dict(agent.generate_queries(IDEA))
    assert "Agriculture" in queries[agent.LABEL_MARKET]
    assert "market size growth trends" in queries[agent.LABEL_MARKET]
    assert queries[agent.LABEL_COMPETITORS].endswith("competitors alternatives startups")
    assert "Small farmers in India" in queries[agent.LABEL_DEMAND]
    assert queries[agent.LABEL_DEMAND].endswith("demand pain points")
    assert queries[agent.LABEL_NEWS].endswith("startups funding news recent")


def test_punctuation_noise_is_removed() -> None:
    idea = IDEA.model_copy(update={"solution": "A phone app -- detects disease (fast!), cheaply."})
    market = dict(agent.generate_queries(idea))[agent.LABEL_MARKET]
    assert "(" not in market and "!" not in market and "," not in market
    assert "  " not in market


def test_long_fields_are_trimmed_on_a_word_boundary() -> None:
    idea = IDEA.model_copy(update={"industry": "word " * 60, "solution": "phrase " * 60})
    market = dict(agent.generate_queries(idea))[agent.LABEL_MARKET]
    assert len(market) <= agent.MAX_QUERY_CHARS
    assert not market.endswith(" ")
    assert "wor" not in market.split()[-1] or market.split()[-1] == "word"


def test_queries_stay_non_empty_for_a_punctuation_only_idea() -> None:
    idea = IDEA.model_copy(update={"problem": "...", "solution": "???", "industry": "!!!"})
    texts = [query for _, query in agent.generate_queries(idea)]
    assert all(text.strip() for text in texts)
    assert len(set(texts)) == 4


# --- running the search ------------------------------------------------------


def test_complete_run_collects_results_from_every_section(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = use_fake_post(
        monkeypatch,
        body([result("https://a.test")], answer="Summary A"),
        body([result("https://b.test"), result("https://c.test")]),
        body([result("https://d.test")]),
        body([result("https://e.test")]),
    )
    bundle = agent.run_web_search(IDEA)

    assert len(fake.calls) == 4
    assert [section.label for section in bundle.sections] == EXPECTED_LABELS
    assert bundle.total_results == 5
    assert bundle.queries_failed == 0
    assert bundle.sections[0].answer == "Summary A"
    assert all(section.error is None for section in bundle.sections)


def test_each_result_has_title_url_and_snippet(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE), tavily_empty())
    first = agent.run_web_search(IDEA).sections[0].results[0]
    assert first.title and first.url.startswith("https://") and first.snippet
    assert first.score == 0.91


def test_search_options_sent_to_tavily(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, FakeHTTPResponse(200, TAVILY_OK_RESPONSE))
    agent.run_web_search(IDEA)
    sent = fake.calls[0][1]["json"]
    assert sent["search_depth"] == "basic"
    assert sent["max_results"] == 3
    assert sent["include_answer"] is True


def test_duplicate_urls_are_dropped_across_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    shared = body([result("https://same.test"), result("https://other.test")])
    use_fake_post(monkeypatch, shared)
    bundle = agent.run_web_search(IDEA)

    urls = [r.url for section in bundle.sections for r in section.results]
    assert urls == ["https://same.test", "https://other.test"]
    assert bundle.total_results == 2
    assert bundle.sections[1].error == agent.MSG_NO_RESULTS
    assert bundle.queries_failed == 0


def test_entries_without_url_or_content_are_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(
        monkeypatch,
        body(
            [
                {"url": "", "title": "no url", "content": "text"},
                {"url": "https://ok.test", "title": "fine", "content": "text"},
                {"url": "https://empty.test", "title": "no content", "content": "   "},
                {"url": "https://missing.test", "title": "missing content"},
                "not a dict",
            ]
        ),
        tavily_empty(),
    )
    results = agent.run_web_search(IDEA).sections[0].results
    assert [r.url for r in results] == ["https://ok.test"]


def test_missing_title_falls_back_to_the_url(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, body([{"url": "https://x.test", "content": "text"}]), tavily_empty())
    assert agent.run_web_search(IDEA).sections[0].results[0].title == "https://x.test"


def test_long_snippets_are_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, body([result("https://long.test", content="word " * 200)]))
    snippet = agent.run_web_search(IDEA).sections[0].results[0].snippet
    assert len(snippet) <= SNIPPET_MAX and snippet.endswith("...")


def test_out_of_range_score_becomes_none(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(
        monkeypatch,
        body([result("https://s1.test", score=1.4), result("https://s2.test", score="high")]),
        tavily_empty(),
    )
    assert [r.score for r in agent.run_web_search(IDEA).sections[0].results] == [None, None]


def test_zero_results_is_reported_in_the_section(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(monkeypatch, tavily_empty(), body([result("https://a.test")]))
    bundle = agent.run_web_search(IDEA)
    assert bundle.sections[0].results == []
    assert bundle.sections[0].error == agent.MSG_NO_RESULTS
    assert bundle.queries_failed == 0


def test_malformed_results_field_is_treated_as_no_results(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fake_post(monkeypatch, FakeHTTPResponse(200, {"answer": None, "results": "oops"}))
    bundle = agent.run_web_search(IDEA)
    assert bundle.total_results == 0
    assert all(section.error == agent.MSG_NO_RESULTS for section in bundle.sections)


# --- partial and total failure ----------------------------------------------


def test_one_failed_query_does_not_stop_the_others(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_post(
        monkeypatch,
        tavily_status(429),
        body([result("https://b.test")]),
        body([result("https://c.test")]),
        body([result("https://d.test")]),
    )
    bundle = agent.run_web_search(IDEA)

    assert bundle.queries_failed == 1
    assert bundle.total_results == 3
    assert bundle.sections[0].error == search_client.MSG_RATE_LIMIT
    assert bundle.sections[0].results == []
    assert all(section.error is None for section in bundle.sections[1:])


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (tavily_status(401), search_client.MSG_KEY_REJECTED),
        (tavily_status(429), search_client.MSG_RATE_LIMIT),
        (tavily_status(500), search_client.MSG_BUSY),
        (TAVILY_TIMEOUT, search_client.MSG_TIMEOUT),
        (tavily_not_json(), search_client.MSG_BAD_REPLY),
    ],
)
def test_all_queries_failing_raises_a_clear_error(
    monkeypatch: pytest.MonkeyPatch, outcome: object, expected: str
) -> None:
    use_fake_post(monkeypatch, outcome)
    with pytest.raises(SearchAPIError) as info:
        agent.run_web_search(IDEA)
    assert info.value.user_message == agent.MSG_ALL_QUERIES_FAILED
    assert info.value.status_code == 502


def test_missing_key_fails_every_query_and_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_post(monkeypatch, body([result("https://a.test")]))
    monkeypatch.delenv("TAVILY_API_KEY")
    with pytest.raises(SearchAPIError):
        agent.run_web_search(IDEA)
    assert fake.calls == []


def test_three_failures_still_return_the_one_that_worked(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fake_post(
        monkeypatch,
        body([result("https://a.test")]),
        tavily_status(500),
        tavily_status(500),
        tavily_status(500),
    )
    bundle = agent.run_web_search(IDEA)
    assert bundle.queries_failed == 3 and bundle.total_results == 1


# --- markdown rendering ------------------------------------------------------


def test_render_markdown_shows_sections_results_and_notes(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    use_fake_post(
        monkeypatch,
        body([result("https://a.test", title="Market report", content="Growing fast")], "Summary A"),
        tavily_status(429),
        tavily_empty(),
        body([result("https://d.test")]),
    )
    text = agent.render_markdown(agent.run_web_search(IDEA))

    assert text.startswith("# Market and competitor research")
    for label in EXPECTED_LABELS:
        assert f"## {label}" in text
    assert "Summary: Summary A" in text
    assert "1. Market report" in text
    assert "https://a.test" in text
    assert "Growing fast" in text
    assert f"Note: {search_client.MSG_RATE_LIMIT}" in text
    assert f"Note: {agent.MSG_NO_RESULTS}" in text
    assert "Total results: 2" in text
    assert "Queries failed: 1" in text


def test_render_markdown_handles_an_empty_bundle() -> None:
    text = agent.render_markdown(SearchBundle())
    assert "Total results: 0" in text and "Queries failed: 0" in text

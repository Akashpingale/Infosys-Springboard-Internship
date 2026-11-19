import threading
import time
from pathlib import Path
from typing import Any

import pytest

import config
from agents import competitor_analysis_agent as competitor_agent
from agents import market_size, web_search_agent
from agents.evidence import build_evidence, focused_snippet
from models.schemas import ExtractedIdea
from tests.fakes import VALID_EXTRACTION, FakeHTTPResponse
from utils import deadline, search_client
from utils.deadline import stop_check, time_limit
from utils.errors import RunCancelledError
from utils.usage import UsageCounter, counting

ROOT = Path(__file__).resolve().parent.parent
IDEA = ExtractedIdea(**VALID_EXTRACTION)
QUERIES = [(f"Label {number}", f"query {number}") for number in range(1, 7)]
SHARED_URL = "https://shared.example/page"


def body_for(query: str) -> dict[str, Any]:
    number = sum(ord(char) for char in query) % 97
    results = [
        {"title": f"{query} first", "url": f"https://one.example/{number}", "content": f"{query} first page text " * 3,
         "score": 0.5},
        {"title": f"{query} second", "url": f"https://two.example/{number}", "content": f"{query} second page text " * 3,
         "score": 0.9},
        {"title": f"{query} shared", "url": SHARED_URL, "content": f"shared page as seen by {query} " * 3, "score": 0.7},
    ]
    return {"answer": f"Summary for {query}.", "results": results}


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.lock = threading.Lock()

    def __call__(self) -> float:
        with self.lock:
            return self.now

    def advance(self, seconds: float) -> None:
        with self.lock:
            self.now += seconds


class Tavily:
    def __init__(
        self,
        *,
        delays: dict[str, float] | None = None,
        statuses: dict[str, int] | None = None,
        raises: dict[str, BaseException] | None = None,
        clock: Clock | None = None,
        advance: float = 0.0,
        on_call: Any = None,
    ) -> None:
        self.delays = delays or {}
        self.statuses = statuses or {}
        self.raises = raises or {}
        self.clock = clock
        self.advance = advance
        self.on_call = on_call
        self.lock = threading.Lock()
        self.calls: list[dict[str, Any]] = []
        self.finished: list[str] = []
        self.active = 0
        self.most_active = 0

    def __call__(self, url: str, headers: Any = None, json: Any = None, timeout: Any = None, **kwargs: Any) -> Any:
        query = json["query"]
        with self.lock:
            self.calls.append({"query": query, "json": dict(json), "timeout": timeout, "thread": threading.get_ident()})
            self.active += 1
            self.most_active = max(self.most_active, self.active)
        try:
            if self.on_call is not None:
                self.on_call(query)
            time.sleep(self.delays.get(query, 0.0))
            if self.clock is not None:
                self.clock.advance(self.advance)
            if query in self.raises:
                raise self.raises[query]
            status = self.statuses.get(query, 200)
            if status != 200:
                return FakeHTTPResponse(status, {"detail": {"error": f"HTTP {status}"}})
            return FakeHTTPResponse(200, body_for(query))
        finally:
            with self.lock:
                self.active -= 1
                self.finished.append(query)

    def queries(self) -> list[str]:
        return [call["query"] for call in self.calls]


def reverse_delays(queries: list[tuple[str, str]], step: float = 0.03) -> dict[str, float]:
    return {query: (len(queries) - index) * step for index, (_, query) in enumerate(queries)}


def use(monkeypatch: pytest.MonkeyPatch, workers: int, tavily: Tavily) -> Tavily:
    monkeypatch.setenv("SEARCH_MAX_PARALLEL", str(workers))
    monkeypatch.setattr(search_client.requests, "post", tavily)
    return tavily


def test_parallel_results_equal_sequential_results_even_when_answers_arrive_in_reverse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use(monkeypatch, 1, Tavily())
    sequential = web_search_agent.run_queries(QUERIES)
    tavily = use(monkeypatch, 3, Tavily(delays=reverse_delays(QUERIES)))
    parallel = web_search_agent.run_queries(QUERIES)

    assert parallel.model_dump() == sequential.model_dump()
    assert build_evidence(parallel) == build_evidence(sequential)
    assert sorted(tavily.queries()) == sorted(query for _, query in QUERIES)
    assert tavily.finished != [query for _, query in QUERIES]
    assert 2 <= tavily.most_active <= 3
    assert [result.url for result in parallel.sections[0].results].count(SHARED_URL) == 1
    assert all(SHARED_URL not in [result.url for result in section.results] for section in parallel.sections[1:])


@pytest.mark.parametrize("stage", ["standard", "market_size", "competitor"])
def test_every_search_stage_gives_the_same_bundle_in_parallel(monkeypatch: pytest.MonkeyPatch, stage: str) -> None:
    competitor_queries = competitor_agent.competitor_queries([], IDEA, config.DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES)
    run = {
        "standard": lambda: web_search_agent.run_web_search(IDEA),
        "market_size": lambda: market_size.search_market_size(IDEA),
        "competitor": lambda: competitor_agent.search_competitors(competitor_queries),
    }[stage]
    queries = {
        "standard": web_search_agent.generate_queries(IDEA),
        "market_size": market_size.market_size_queries(IDEA),
        "competitor": competitor_queries,
    }[stage]
    use(monkeypatch, 1, Tavily())
    sequential = run()
    tavily = use(monkeypatch, 3, Tavily(delays=reverse_delays(queries)))
    parallel = run()

    assert repr(parallel) == repr(sequential)
    assert sorted(tavily.queries()) == sorted(query for _, query in queries)


def test_snippet_builders_run_in_query_order_too(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, 1, Tavily())
    sequential = web_search_agent.run_queries(QUERIES, snippet=focused_snippet, max_results=2, depth="advanced")
    tavily = use(monkeypatch, 4, Tavily(delays=reverse_delays(QUERIES)))
    parallel = web_search_agent.run_queries(QUERIES, snippet=focused_snippet, max_results=2, depth="advanced")

    assert parallel.model_dump() == sequential.model_dump()
    assert {(call["json"]["max_results"], call["json"]["search_depth"]) for call in tavily.calls} == {(2, "advanced")}


def test_one_failing_query_stays_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = {"query 3": 500}
    use(monkeypatch, 1, Tavily(statuses=statuses))
    sequential = web_search_agent.run_queries(QUERIES)
    use(monkeypatch, 3, Tavily(statuses=statuses, delays=reverse_delays(QUERIES)))
    parallel = web_search_agent.run_queries(QUERIES)

    assert parallel.model_dump() == sequential.model_dump()
    assert parallel.queries_failed == 1
    assert parallel.sections[2].error == search_client.MSG_BUSY and parallel.sections[2].results == []
    assert all(section.results for index, section in enumerate(parallel.sections) if index != 2)


def test_every_query_failing_still_raises_the_plain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, 3, Tavily(statuses={query: 503 for _, query in QUERIES}))
    with pytest.raises(search_client.SearchAPIError) as raised:
        web_search_agent.run_queries(QUERIES)
    assert raised.value.user_message == web_search_agent.MSG_ALL_QUERIES_FAILED


def test_an_unexpected_error_in_a_worker_is_raised_as_in_sequential_order(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = {"query 2": ValueError("not a search error")}
    tavily = use(monkeypatch, 1, Tavily(raises=problem))
    with pytest.raises(ValueError):
        web_search_agent.run_queries(QUERIES)
    assert tavily.queries() == ["query 1", "query 2"]
    tavily = use(monkeypatch, 2, Tavily(raises=problem, delays={"query 1": 0.3}))
    with pytest.raises(ValueError):
        web_search_agent.run_queries(QUERIES)
    assert sorted(tavily.queries()) == ["query 1", "query 2"]
    assert tavily.active == 0


def test_a_cancel_stops_new_submissions_and_raises_after_the_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = threading.Event()

    def first_call_cancels(query: str) -> None:
        stop.set()
        time.sleep(0.05)

    tavily = use(monkeypatch, 1, Tavily(on_call=first_call_cancels))
    with stop_check(stop.is_set), pytest.raises(RunCancelledError):
        web_search_agent.run_queries(QUERIES)
    assert tavily.queries() == ["query 1"]

    stop.clear()
    tavily = use(monkeypatch, 2, Tavily(on_call=first_call_cancels))
    with stop_check(stop.is_set), pytest.raises(RunCancelledError):
        web_search_agent.run_queries(QUERIES)
    assert 1 <= len(tavily.calls) <= 2
    assert set(tavily.queries()) <= {"query 1", "query 2"}
    assert tavily.active == 0


def test_a_cancel_before_the_stage_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    tavily = use(monkeypatch, 3, Tavily())
    with stop_check(lambda: True), pytest.raises(RunCancelledError):
        web_search_agent.run_queries(QUERIES)
    assert tavily.calls == []


def test_worker_requests_keep_the_run_time_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = Clock()
    monkeypatch.setattr(deadline, "clock", clock)
    tavily = use(monkeypatch, 3, Tavily(delays=reverse_delays(QUERIES, 0.01)))
    with time_limit(5):
        web_search_agent.run_queries(QUERIES)
    assert len(tavily.calls) == len(QUERIES)
    assert {call["timeout"] for call in tavily.calls} == {5.0}
    assert {call["thread"] for call in tavily.calls} != {threading.get_ident()}


def test_no_query_is_submitted_once_the_time_limit_has_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = Clock()
    monkeypatch.setattr(deadline, "clock", clock)
    tavily = use(monkeypatch, 1, Tavily(clock=clock, advance=20))
    with time_limit(15):
        sequential = web_search_agent.run_queries(QUERIES)
    assert tavily.queries() == ["query 1"]
    assert [section.error for section in sequential.sections[1:]] == [search_client.MSG_TIME_LIMIT] * 5

    clock.now = 0.0
    tavily = use(monkeypatch, 2, Tavily(clock=clock, advance=20))
    with time_limit(15):
        parallel = web_search_agent.run_queries(QUERIES)
    assert 1 <= len(tavily.calls) <= 2 and set(tavily.queries()) <= {"query 1", "query 2"}
    assert parallel.sections[0].results == sequential.sections[0].results
    assert [section.error for section in parallel.sections[2:]] == [search_client.MSG_TIME_LIMIT] * 4


def test_a_rate_limit_reply_pauses_the_pool_once_and_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    paused = threading.Event()
    pauses: list[tuple[float, set[str]]] = []

    def hold_others(query: str) -> None:
        if query != "query 1":
            paused.wait(2)

    statuses = {"query 1": 429}
    use(monkeypatch, 1, Tavily(statuses=statuses))
    sequential = web_search_agent.run_queries(QUERIES[:4])

    tavily = use(monkeypatch, 2, Tavily(statuses=statuses, on_call=hold_others))

    def record(seconds: float) -> None:
        pauses.append((seconds, set(tavily.queries())))
        paused.set()

    monkeypatch.setattr(web_search_agent, "pause", record)
    parallel = web_search_agent.run_queries(QUERIES[:4])

    assert len(pauses) == 1 and pauses[0][0] == web_search_agent.RATE_LIMIT_PAUSE_S
    assert "query 1" in pauses[0][1] and pauses[0][1] <= {"query 1", "query 2"}
    assert sorted(tavily.queries()) == ["query 1", "query 2", "query 3", "query 4"]
    assert parallel.model_dump() == sequential.model_dump()
    assert parallel.sections[0].error == search_client.MSG_RATE_LIMIT


def test_the_rate_limit_pause_never_runs_past_the_time_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = Clock()
    monkeypatch.setattr(deadline, "clock", clock)
    pauses: list[float] = []
    monkeypatch.setattr(web_search_agent, "pause", pauses.append)
    with time_limit(0.4):
        web_search_agent._pause_for_rate_limit()
    web_search_agent._pause_for_rate_limit()
    clock.now = 1.0
    with time_limit(0.0):
        web_search_agent._pause_for_rate_limit()
    assert pauses == [0.4, web_search_agent.RATE_LIMIT_PAUSE_S]


def test_one_worker_restores_sequential_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_pool(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("no thread pool with one worker")

    monkeypatch.setattr(web_search_agent, "ThreadPoolExecutor", no_pool)
    tavily = use(monkeypatch, 1, Tavily(delays=reverse_delays(QUERIES, 0.005)))
    web_search_agent.run_queries(QUERIES)
    assert tavily.queries() == [query for _, query in QUERIES]
    assert tavily.finished == tavily.queries()
    assert {call["thread"] for call in tavily.calls} == {threading.get_ident()}
    assert tavily.most_active == 1


def test_the_default_is_one_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEARCH_MAX_PARALLEL", raising=False)
    monkeypatch.setattr(web_search_agent, "ThreadPoolExecutor", None)
    tavily = Tavily()
    monkeypatch.setattr(search_client.requests, "post", tavily)
    web_search_agent.run_queries(QUERIES)
    assert config.get_settings().search_max_parallel == config.DEFAULT_SEARCH_MAX_PARALLEL == 1
    assert tavily.queries() == [query for _, query in QUERIES]


def test_counts_from_worker_threads_are_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    queries = [(f"Label {number}", f"query {number}") for number in range(40)]
    tavily = use(monkeypatch, 8, Tavily())
    counter = UsageCounter()
    with counting(counter):
        web_search_agent.run_queries(queries)
    assert counter.totals() == (0, 40) == (0, len(tavily.calls))
    assert tavily.most_active <= 8


@pytest.mark.parametrize(("raw", "expected"), [("1", 1), ("3", 3), ("8", 8), ("0", 1), ("9", 1), ("-2", 1), ("two", 1), (" ", 1)])
def test_the_worker_setting_is_bounded(monkeypatch: pytest.MonkeyPatch, raw: str, expected: int) -> None:
    monkeypatch.setenv("SEARCH_MAX_PARALLEL", raw)
    assert config.get_settings().search_max_parallel == expected
    assert config.SEARCH_MAX_PARALLEL_RANGE == (1, 8)


def test_the_env_example_documents_the_worker_setting() -> None:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert "# SEARCH_MAX_PARALLEL=1" in lines

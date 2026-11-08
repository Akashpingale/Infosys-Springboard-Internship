"""Integration fix 3: the time limit of a run with the analysis stages.

The UI waits PIPELINE_TIMEOUT_S (180 s) for a full run. Without a backend limit a slow provider
could keep the run going after that, so the UI showed a timeout and lost every result while the
backend kept spending credits. The route now gives a full run TIME_LIMIT_SHARE of that wait
(utils/deadline.py): each LLM call and search waits at most the time left, none starts after the
limit, and an analysis stage that would start after it is skipped with a warning.

The localhost run of 2026-10-27 then showed that Gemini rejects a deadline under 10 s: Phase C was
sent with the few seconds left and answered HTTP 400 INVALID_ARGUMENT. So no LLM call is sent with
less than llm_client.MIN_DEADLINE_S, and the fake provider here rejects shorter deadlines as
Gemini does.

Time is simulated: the deadline module reads a fake clock that the fakes move forward, so nothing
sleeps and nothing touches the network.
"""

import math
from types import SimpleNamespace
from typing import Any, Callable

import httpx
import pytest
import requests
from fastapi.testclient import TestClient

import orchestrator
from agents import competitor_analysis_agent as competitor_agent
from agents import market_opportunity_agent as market_agent
from agents import market_size
from agents.web_search_agent import run_queries, run_web_search
from config import get_settings
from models.schemas import PipelineResult
from orchestrator import FULL_STAGES, SKIP_NO_TIME
from routes import idea_routes
from tests.fakes import LLM_REPLY_OK, FakeHTTPResponse
from tests.m2_fakes import COMPETITOR_TARGETED, NO_MARKET_SIZE_RESULTS
from tests.pipeline_fakes import PIPELINE_SEARCH, PIPELINE_SUBMISSION, market_reply, use_full_pipeline
from utils import deadline, llm_client, search_client
from utils.deadline import call_timeout, time_left, time_limit
from utils.errors import LLMAPIError, SearchAPIError

URL = "/api/validate"
FULL_URL = f"{URL}?include_analysis=true"
BODY = PIPELINE_SUBMISSION.model_dump(mode="json")
MARKET_SKIPPED = SKIP_NO_TIME.format(label=orchestrator.MARKET_LABEL)
COMPETITOR_SKIPPED = SKIP_NO_TIME.format(label=orchestrator.COMPETITOR_LABEL)


class Clock:
    """Simulated time for the deadline module; the fakes move it forward."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(deadline, "clock", fake)
    return fake


def taking(clock: Clock, seconds: float, fake: Callable[..., Any]) -> Callable[..., Any]:
    """`fake` (a make_sequence fake), answering after `seconds` of simulated time."""

    def slow(*args: Any, **kwargs: Any) -> Any:
        clock.advance(seconds)
        return fake(*args, **kwargs)

    slow.calls = fake.calls  # type: ignore[attr-defined]
    return slow


def answering(clock: Clock, seconds: float, outcome: Any) -> Callable[..., Any]:
    def slow(*args: Any, **kwargs: Any) -> Any:
        clock.advance(seconds)
        return outcome

    return slow


def deadline_rejection(timeout_ms: int) -> Exception | None:
    """What Gemini answers a request whose deadline is under 10 s. The SDK sends HttpOptions.timeout
    as the X-Server-Timeout header, in seconds rounded up (google/genai/_api_client.py)."""
    deadline_s = math.ceil(timeout_ms / 1000)
    if not timeout_ms or deadline_s >= 10:
        return None
    message = f"Manually set deadline {deadline_s}s is too short. Minimum allowed deadline is 10s."
    return llm_client.genai_errors.ClientError(
        400, {"error": {"code": 400, "message": message, "status": "INVALID_ARGUMENT"}}
    )


class SlowProvider:
    """Stands in for genai.Client. Each call takes its scripted time and returns or raises its
    outcome; one that needs longer than its timeout ends at the timeout with httpx.ReadTimeout,
    as the real client does. Like Gemini, it rejects a deadline under 10 s with HTTP 400.

    With `replay`, each call takes exactly its scripted time, as recorded in a real run's log,
    and its scripted outcome stands for what the provider answered then."""

    def __init__(self, clock: Clock, *script: tuple[float, Any], replay: bool = False) -> None:
        self.clock = clock
        self.script = list(script)
        self.replay = replay
        self.calls: list[tuple[float, float]] = []  # (simulated start, timeout in seconds)
        self.timeouts_ms: list[int] = []
        self.rejected: list[int] = []  # timeouts (ms) that Gemini would answer with HTTP 400
        self.closed = 0

    def __call__(self, **kwargs: Any) -> "SlowProvider":
        self.timeouts_ms.append(kwargs["http_options"].timeout)
        return self

    @property
    def models(self) -> "SlowProvider":
        return self

    def generate_content(self, **kwargs: Any) -> Any:
        needs, outcome = self.script.pop(0)
        timeout_s = self.timeouts_ms[-1] / 1000
        self.calls.append((self.clock.now, timeout_s))
        rejection = deadline_rejection(self.timeouts_ms[-1])
        if rejection is not None:
            self.rejected.append(self.timeouts_ms[-1])
            self.clock.advance(needs if self.replay else 0)
            raise rejection
        if needs > timeout_s and not self.replay:
            self.clock.advance(timeout_s)
            raise httpx.ReadTimeout("timed out")
        self.clock.advance(needs)
        if isinstance(outcome, BaseException):
            raise outcome
        return SimpleNamespace(text=outcome)

    def close(self) -> None:
        self.closed += 1


def use_provider(
    monkeypatch: pytest.MonkeyPatch, clock: Clock, *script: tuple[float, Any], replay: bool = False
) -> SlowProvider:
    """The real llm_client over a fake provider; its retry waits move the clock instead of sleeping."""
    provider = SlowProvider(clock, *script, replay=replay)
    monkeypatch.setattr(llm_client.genai, "Client", provider)
    monkeypatch.setattr(llm_client, "time", SimpleNamespace(sleep=clock.advance))
    return provider


def busy() -> Exception:
    return llm_client.genai_errors.ServerError(503, {"error": {"code": 503, "message": "busy"}})


def tavily_body(number: int) -> dict:
    return {
        "answer": None,
        "results": [
            {"title": f"Page {number}", "url": f"https://site{number}.example", "content": "Some text.", "score": 0.5}
        ],
    }


def slow_post(clock: Clock, seconds: float) -> Callable[..., Any]:
    """Fake requests.post: every Tavily search takes `seconds`, or times out at its timeout."""
    timeouts: list[float] = []

    def post(*args: Any, **kwargs: Any) -> FakeHTTPResponse:
        timeouts.append(kwargs["timeout"])
        if seconds > kwargs["timeout"]:
            clock.advance(kwargs["timeout"])
            raise requests.Timeout("read timed out")
        clock.advance(seconds)
        return FakeHTTPResponse(200, tavily_body(len(timeouts)))

    post.timeouts = timeouts  # type: ignore[attr-defined]
    return post


# --- the limit itself ------------------------------------------------------------------------


def test_without_a_limit_every_call_keeps_its_configured_timeout() -> None:
    assert time_left() is None
    assert call_timeout(30.0) == 30.0


def test_a_limit_cuts_each_call_to_the_time_left(clock: Clock) -> None:
    with time_limit(100):
        assert call_timeout(30.0) == 30.0
        clock.advance(80)
        assert (time_left(), call_timeout(30.0)) == (20.0, 20.0)
        clock.advance(25)
        assert (time_left(), call_timeout(30.0)) == (-5.0, 0.0)


def test_the_limit_ends_with_its_block_even_when_the_block_raises(clock: Clock) -> None:
    with pytest.raises(RuntimeError):
        with time_limit(10):
            raise RuntimeError("stage crashed")
    assert time_left() is None

    with time_limit(50):
        with time_limit(None):
            assert time_left() is None
        assert time_left() == 50.0, "the outer limit is restored"


# --- the search client -----------------------------------------------------------------------


def test_a_search_waits_at_most_the_time_left(clock: Clock, monkeypatch: pytest.MonkeyPatch) -> None:
    post = slow_post(clock, 1)
    monkeypatch.setattr(search_client.requests, "post", post)
    with time_limit(100):
        clock.advance(88)
        search_client.search("q")
    assert post.timeouts == [12.0], "not the configured 30 s"


def test_no_search_is_sent_after_the_limit(clock: Clock, monkeypatch: pytest.MonkeyPatch) -> None:
    post = slow_post(clock, 1)
    monkeypatch.setattr(search_client.requests, "post", post)
    with time_limit(10):
        clock.advance(10)
        with pytest.raises(SearchAPIError) as info:
            search_client.search("q")
    assert info.value.user_message == search_client.MSG_TIME_LIMIT != search_client.MSG_TIMEOUT
    assert post.timeouts == [], "nothing was sent"


def test_the_limit_cuts_a_list_of_searches_short_and_keeps_what_finished(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    post = slow_post(clock, 10)
    monkeypatch.setattr(search_client.requests, "post", post)
    queries = [(f"Label {n}", f"query {n}") for n in range(1, 5)]
    with time_limit(25):
        bundle = run_queries(queries)

    assert post.timeouts == [25.0, 15.0, 5.0], "the third search only had 5 s left; the fourth was not sent"
    assert [section.error for section in bundle.sections] == [
        None,
        None,
        search_client.MSG_TIMEOUT,
        search_client.MSG_TIME_LIMIT,
    ]
    assert [len(section.results) for section in bundle.sections] == [1, 1, 0, 0]
    assert bundle.queries_failed == 2 and clock.now == 25.0


# --- the LLM client --------------------------------------------------------------------------


def test_an_llm_call_waits_at_most_the_time_left(clock: Clock, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = use_provider(monkeypatch, clock, (2, '{"ok": 1}'))
    with time_limit(100):
        clock.advance(80)
        assert llm_client.generate_json("system", "user") == '{"ok": 1}'
    assert provider.timeouts_ms == [20000], "not the configured 30 000 ms"
    assert provider.closed == 1 and provider.rejected == []


@pytest.mark.parametrize(("left", "sent_ms"), [(10.0, 10000), (10.5, 10500), (30.0, 30000), (45.0, 30000)])
def test_with_10_seconds_or_more_left_the_call_is_sent_with_what_is_left(
    clock: Clock, monkeypatch: pytest.MonkeyPatch, left: float, sent_ms: int
) -> None:
    provider = use_provider(monkeypatch, clock, (1, '{"ok": 1}'))
    with time_limit(100):
        clock.advance(100 - left)
        assert llm_client.generate_json("system", "user") == '{"ok": 1}'
    assert provider.timeouts_ms == [sent_ms] and provider.rejected == []


@pytest.mark.parametrize("left", [9.9, 9.999, 7.35, 0.5])
def test_with_less_than_10_seconds_left_no_call_is_sent(
    clock: Clock, monkeypatch: pytest.MonkeyPatch, left: float
) -> None:
    """Gemini would reject the deadline with HTTP 400, so the step reports the time limit instead."""
    provider = use_provider(monkeypatch, clock, (1, '{"ok": 1}'))
    with time_limit(100):
        clock.advance(100 - left)
        with pytest.raises(LLMAPIError) as info:
            llm_client.generate_json("system", "user")
    assert info.value.user_message == llm_client.MSG_TIME_LIMIT
    assert provider.timeouts_ms == [] and provider.calls == [], "no client was created and nothing was sent"


@pytest.mark.parametrize(("left", "sent_ms"), [(None, 10000), (100.0, 10000), (12.0, 10000)])
def test_a_configured_5_second_timeout_is_raised_to_the_10_second_minimum(
    clock: Clock, monkeypatch: pytest.MonkeyPatch, left: float | None, sent_ms: int
) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_S", "5")
    provider = use_provider(monkeypatch, clock, (1, '{"ok": 1}'))
    with time_limit(None if left is None else 100):
        clock.advance(0 if left is None else 100 - left)
        assert llm_client.generate_json("system", "user") == '{"ok": 1}'
    assert provider.timeouts_ms == [sent_ms] and provider.rejected == []


def test_no_llm_call_starts_after_the_limit(clock: Clock, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = use_provider(monkeypatch, clock, (2, '{"ok": 1}'))
    with time_limit(10):
        clock.advance(10)
        with pytest.raises(LLMAPIError) as info:
            llm_client.generate_json("system", "user")
    assert info.value.user_message == llm_client.MSG_TIME_LIMIT != llm_client.MSG_TIMEOUT
    assert provider.timeouts_ms == [] and provider.calls == [], "no client was created"


def test_a_retry_that_would_leave_less_than_10_seconds_is_not_made(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = use_provider(monkeypatch, clock, (0.5, busy()), (1, '{"ok": 1}'))
    with time_limit(100):
        clock.advance(89)
        with pytest.raises(LLMAPIError) as info:
            llm_client.generate_json("system", "user")

    assert info.value.user_message == llm_client.MSG_BUSY, "the real cause is kept"
    assert provider.calls == [(89.0, 11.0)] and provider.closed == 1
    assert clock.now == 89.5, "10.5 s were left, so the 1 s backoff would leave 9.5 s: no wait, no retry"


def test_a_retry_that_leaves_exactly_10_seconds_is_made(clock: Clock, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = use_provider(monkeypatch, clock, (1, busy()), (1, '{"ok": 1}'))
    with time_limit(100):
        clock.advance(88)
        assert llm_client.generate_json("system", "user") == '{"ok": 1}'
    assert provider.calls == [(88.0, 12.0), (90.0, 10.0)] and provider.rejected == []


def test_the_second_backoff_is_checked_against_the_minimum_too(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = use_provider(monkeypatch, clock, (2, busy()), (14.5, busy()), (1, '{"ok": 1}'))
    with time_limit(100):
        clock.advance(70)
        with pytest.raises(LLMAPIError) as info:
            llm_client.generate_json("system", "user")

    assert info.value.user_message == llm_client.MSG_BUSY
    assert provider.calls == [(70.0, 30.0), (73.0, 27.0)], "12.5 s left minus the 3 s backoff is 9.5 s"
    assert clock.now == 87.5


def test_a_retry_with_time_left_gets_only_what_is_left(clock: Clock, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = use_provider(monkeypatch, clock, (5, busy()), (5, '{"ok": 1}'))
    with time_limit(100):
        clock.advance(80)
        assert llm_client.generate_json("system", "user") == '{"ok": 1}'
    assert provider.calls == [(80.0, 20.0), (86.0, 14.0)], "1 s backoff, then the 14 s left"
    assert provider.closed == 2


def test_the_llm_timeout_is_never_rounded_down_to_no_timeout(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """google-genai reads HttpOptions.timeout=0 as no timeout at all (get_timeout_in_seconds). A
    sub-millisecond LLM_TIMEOUT_S is raised to the 10 s minimum, and a sub-millisecond time left
    sends nothing."""
    monkeypatch.setenv("LLM_TIMEOUT_S", "0.0004")
    provider = use_provider(monkeypatch, clock, (0, "{}"), (0, "{}"))
    llm_client.generate_json("system", "user")
    monkeypatch.delenv("LLM_TIMEOUT_S")
    with time_limit(10):
        clock.advance(9.9998)
        with pytest.raises(LLMAPIError):
            llm_client.generate_json("system", "user")
    assert provider.timeouts_ms == [10000]


# --- the orchestrator ------------------------------------------------------------------------


def test_analysis_stages_that_would_start_after_the_limit_are_skipped(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_web_search", taking(clock, 60, fakes.search))
    run = orchestrator.run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, time_limit_s=50)

    assert run.status == "partial" and run.errors == []
    assert run.warnings == [MARKET_SKIPPED, COMPETITOR_SKIPPED]
    assert run.idea is not None and run.search == PIPELINE_SEARCH, "the finished stages are kept"
    assert run.market is None and run.competitors is None, "nothing is filled in for them"
    assert (run.market_search, run.competitor_candidates, run.competitor_search) == (None, [], None)
    assert fakes.analysis_calls() == 0
    assert set(run.timings) == {"extraction", "search", "total"}


def test_a_stage_that_finishes_after_the_limit_keeps_its_result(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    monkeypatch.setattr(market_agent, "generate_json", taking(clock, 60, fakes.market_llm))
    run = orchestrator.run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, time_limit_s=50)

    assert run.status == "partial" and run.errors == []
    assert run.market is not None and run.market_search == NO_MARKET_SIZE_RESULTS
    assert run.warnings[-1] == COMPETITOR_SKIPPED
    assert run.competitors is None and run.competitor_candidates == [] and run.competitor_search is None
    assert fakes.competitor_search.calls == [] and fakes.competitor_llm.calls == []


def test_a_limit_reached_during_the_web_search_is_reported_honestly(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real search stage and search client: two searches finish, the third is cut at the
    limit, the fourth is not sent, and both analyses are skipped."""
    fakes = use_full_pipeline(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_web_search", run_web_search)
    post = slow_post(clock, 10)
    monkeypatch.setattr(search_client.requests, "post", post)
    run = orchestrator.run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, time_limit_s=25)

    assert run.status == "partial" and run.errors == [] and run.search is not None
    assert [section.error for section in run.search.sections] == [
        None,
        None,
        search_client.MSG_TIMEOUT,
        search_client.MSG_TIME_LIMIT,
    ]
    assert run.warnings == [
        "2 of 4 web searches failed, so some sections are empty.",
        MARKET_SKIPPED,
        COMPETITOR_SKIPPED,
    ]
    assert run.market is None and run.competitors is None and fakes.analysis_calls() == 0
    assert len(post.timeouts) == 3 and clock.now == 25.0


def test_a_run_inside_its_limit_is_the_same_as_one_without(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_full_pipeline(monkeypatch)
    limited = orchestrator.run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, time_limit_s=162)
    use_full_pipeline(monkeypatch)
    unlimited = orchestrator.run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert limited.status == "complete" and limited.market is not None and limited.competitors is not None
    assert limited.model_dump(exclude={"timings"}) == unlimited.model_dump(exclude={"timings"})


@pytest.mark.parametrize("stages", [None, FULL_STAGES], ids=["milestone_1", "full"])
def test_without_a_limit_nothing_is_cut(
    clock: Clock, monkeypatch: pytest.MonkeyPatch, stages: list | None
) -> None:
    """The Milestone 1 pipeline and direct callers such as the live runner set no limit."""
    fakes = use_full_pipeline(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_web_search", taking(clock, 1000, fakes.search))
    run = orchestrator.run_pipeline(PIPELINE_SUBMISSION, stages)

    assert run.status == "complete" and run.errors == []
    assert MARKET_SKIPPED not in run.warnings and COMPETITOR_SKIPPED not in run.warnings
    assert (run.market is not None, run.competitors is not None) == (stages is FULL_STAGES,) * 2


class LimitProbe:
    """A stage that records the time left when it runs."""

    name = "limit_probe"

    def __init__(self) -> None:
        self.left: float | None | str = "not run"

    def run(self, context: Any) -> Any:
        self.left = time_left()
        return context


def test_the_limit_lasts_only_for_the_run(clock: Clock, monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    probe = LimitProbe()
    orchestrator.run_pipeline(PIPELINE_SUBMISSION, [*FULL_STAGES, probe], time_limit_s=50)
    assert probe.left == 50.0
    assert time_left() is None

    use_full_pipeline(monkeypatch, extraction=(RuntimeError("provider internals"),))
    with pytest.raises(RuntimeError):
        orchestrator.run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, time_limit_s=50)
    assert time_left() is None, "cleared when a stage crashes, too"


# --- the route -------------------------------------------------------------------------------


def test_only_the_analysis_request_is_time_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    seen: list[tuple] = []
    real = idea_routes.run_pipeline

    def spy(submission: Any, stages: Any = None, time_limit_s: float | None = None) -> PipelineResult:
        seen.append((stages, time_limit_s))
        return real(submission, stages, time_limit_s)

    monkeypatch.setattr(idea_routes, "run_pipeline", spy)
    assert client.post(FULL_URL, json=BODY).status_code == 200
    assert client.post(URL, json=BODY).status_code == 200
    assert seen == [(FULL_STAGES, 162.0), (None, None)], "90% of the UI's 180 s; none for Milestone 1"


@pytest.mark.parametrize(("raw", "expected"), [(None, 162.0), ("240", 216.0), ("slow", 162.0)])
def test_the_analysis_limit_follows_pipeline_timeout_s(
    monkeypatch: pytest.MonkeyPatch, raw: str | None, expected: float
) -> None:
    if raw is not None:
        monkeypatch.setenv("PIPELINE_TIMEOUT_S", raw)
    assert orchestrator.analysis_time_limit_s() == pytest.approx(expected)
    assert orchestrator.analysis_time_limit_s() < get_settings().pipeline_timeout_s


def test_a_milestone_1_request_is_not_cut(
    client: TestClient, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = use_full_pipeline(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_web_search", taking(clock, 1000, fakes.search))
    body = client.post(URL, json=BODY).json()

    assert body["status"] == "complete" and body["warnings"] == [] and body["errors"] == []
    assert set(body["timings"]) == {"extraction", "search", "total"}


# --- a slow provider, end to end -------------------------------------------------------------
# The shape of a slow live run: the Phase A call is answered "busy" three times, slowly, as in the
# agritech run of docs/test_runs_m2, and Phase C then needs longer than its 30 s timeout.

SLOW_PROVIDER = (
    (6, LLM_REPLY_OK),  # extraction
    (22, market_reply()),  # market analysis
    (28, busy()),  # Phase A, attempt 1
    (28, busy()),  # attempt 2, after a 1 s backoff
    (28, busy()),  # attempt 3, after a 3 s backoff
    (90, "{}"),  # Phase C
)


def use_slow_run(monkeypatch: pytest.MonkeyPatch, clock: Clock) -> SlowProvider:
    monkeypatch.setattr(orchestrator, "run_web_search", answering(clock, 15, PIPELINE_SEARCH))
    monkeypatch.setattr(market_size, "run_queries", answering(clock, 8, NO_MARKET_SIZE_RESULTS))
    monkeypatch.setattr(competitor_agent, "run_queries", answering(clock, 20, COMPETITOR_TARGETED))
    return use_provider(monkeypatch, clock, *SLOW_PROVIDER)


def test_without_a_limit_the_slow_run_replies_after_the_ui_has_given_up(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = use_slow_run(monkeypatch, clock)
    orchestrator.run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert provider.calls[-1] == (159.0, 30.0), "Phase C started 21 s before the UI's limit, with 30 s"
    assert clock.now == 189.0 > get_settings().pipeline_timeout_s


def test_through_the_api_the_slow_run_replies_in_time_with_what_finished(
    client: TestClient, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = use_slow_run(monkeypatch, clock)
    response = client.post(FULL_URL, json=BODY)
    assert response.status_code == 200
    result = PipelineResult.model_validate(response.json())

    assert clock.now == 159.0 < get_settings().pipeline_timeout_s, "the reply beats the UI's 180 s"
    assert provider.calls[-1] == (111.0, 30.0), "the last call sent was Phase A's third attempt"
    assert provider.rejected == [], "Phase C, with 3 s left, was not sent at all"
    assert result.status == "partial"
    assert [(e.stage, e.message) for e in result.errors] == [("competitor_analysis", llm_client.MSG_TIME_LIMIT)]
    assert result.idea is not None and result.search == PIPELINE_SEARCH
    assert result.market is not None and result.market_search == NO_MARKET_SIZE_RESULTS
    assert result.competitors is None and result.competitor_candidates == [] and result.competitor_search is None
    assert COMPETITOR_SKIPPED not in result.warnings, "it started in time and failed with its own error"
    assert provider.closed == len(provider.calls), "every client was closed"
    assert time_left() is None


# --- the localhost run of 2026-10-27, replayed ---------------------------------------------------
# The backend log of that run, call by call. Each provider call takes the wall time it took then,
# client set-up included, and gives the answer it gave; each search takes its logged time. The
# market call and Phase A timed out at their full 30 s. The competitor searches ended 153.51 s
# into the 162 s limit, so Phase C was given about 8.5 s, and its request reached Gemini with about
# 7.35 s left. Both deadlines are under 10 s, and Gemini answered HTTP 400 INVALID_ARGUMENT.


def real_run_provider() -> tuple[tuple[float, Any], ...]:
    return (
        (11.39, busy()),  # extraction, attempt 1: HTTP 503
        (13.99, LLM_REPLY_OK),  # extraction, attempt 2 after the 1 s backoff: 200 OK at 26.38 s
        (33.71, httpx.ReadTimeout("timed out")),  # market analysis
        (34.06, httpx.ReadTimeout("timed out")),  # Phase A, the candidate search
        (1.92, "{}"),  # Phase C: answered HTTP 400 after 1.92 s in the real run
    )


COMPETITOR_SEARCHES_START = 145.09  # 11.39 + 1 + 13.99 + 34.27 + 16.67 + 33.71 + 34.06


def use_real_run(monkeypatch: pytest.MonkeyPatch, clock: Clock, phase_c_left: float) -> SlowProvider:
    competitor_searches = orchestrator.analysis_time_limit_s() - phase_c_left - COMPETITOR_SEARCHES_START
    monkeypatch.setattr(orchestrator, "run_web_search", answering(clock, 34.27, PIPELINE_SEARCH))
    monkeypatch.setattr(market_size, "run_queries", answering(clock, 16.67, NO_MARKET_SIZE_RESULTS))
    monkeypatch.setattr(competitor_agent, "run_queries", answering(clock, competitor_searches, COMPETITOR_TARGETED))
    return use_provider(monkeypatch, clock, *real_run_provider(), replay=True)


@pytest.mark.parametrize("phase_c_left", [8.49, 7.35], ids=["when_timed", "when_sent"])
def test_the_real_run_now_sends_no_competitor_call_gemini_would_reject(
    client: TestClient, clock: Clock, monkeypatch: pytest.MonkeyPatch, phase_c_left: float
) -> None:
    provider = use_real_run(monkeypatch, clock, phase_c_left)
    response = client.post(FULL_URL, json=BODY)
    assert response.status_code == 200
    result = PipelineResult.model_validate(response.json())

    assert [timeout for _, timeout in provider.calls] == [30.0, 30.0, 30.0, 30.0], "Phase C was never sent"
    assert provider.rejected == [], "no request had a deadline Gemini rejects"
    assert clock.now == pytest.approx(orchestrator.analysis_time_limit_s() - phase_c_left)
    assert result.status == "partial" and result.warnings == []
    assert [(e.stage, e.message) for e in result.errors] == [
        ("market_opportunity", llm_client.MSG_TIMEOUT),
        ("competitor_analysis", llm_client.MSG_TIME_LIMIT),
    ]
    assert result.idea is not None and result.search == PIPELINE_SEARCH, "the finished stages are kept"
    assert result.market is None and result.market_search == NO_MARKET_SIZE_RESULTS
    assert result.competitors is None and result.competitor_candidates == [] and result.competitor_search is None
    assert set(result.timings) == {"extraction", "search", "market_opportunity", "competitor_analysis", "total"}
    assert provider.closed == len(provider.calls) and time_left() is None

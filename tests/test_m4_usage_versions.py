import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import orchestrator
from agents import competitor_analysis_agent as competitor_agent
from agents import market_size
from agents.strategy_checks import secret_findings
from models.schemas import ExtractedIdea, PipelineResult, StageUsage, StrategyConstraints, Usage, Versions
from orchestrator import FULL_STAGES, STAGES, STRATEGY_ONLY_STAGES, STRATEGY_STAGES, TOTAL_KEY, StageEvent, run_pipeline
from routes.meta_routes import APP_VERSION
from tests.fakes import LLM_REPLY_NOT_JSON, LLM_REPLY_OK, FakeHTTPResponse, tavily_ok, tavily_status
from tests.m2_fakes import COMPETITOR_TARGETED, NO_MARKET_SIZE_RESULTS
from tests.m3_fakes import GROQ_TEST_KEY, gemini_rate_limit, use_fake_strategy
from tests.pipeline_fakes import PIPELINE_SEARCH, PIPELINE_SUBMISSION, competitor_replies, market_reply, use_full_pipeline
from tests.run_fakes import REVIEWED_IDEA, finished, store_in
from utils import deadline, llm_client, search_client
from utils.errors import AppError, SearchAPIError, SearchConfigError
from utils.run_manager import RunManager
from utils.structured import call_structured
from utils.usage import UsageCounter, count_llm_call, count_search_call, counting

ROOT = Path(__file__).resolve().parent.parent
STORED_RUNS = ROOT / "data" / "runs.db"
FIXTURE_RESULTS = sorted(path for path in (ROOT / "docs").glob("test_runs*/*.json") if path.name != "run_summary.json")
FIXTURE_RUNS = [ROOT / "web" / "src" / "test" / "liveAgritech.json", ROOT / "web" / "src" / "test" / "liveFintech.json"]
SYNTHETIC = ROOT / "web" / "src" / "test" / "strategyFixture.synthetic.json"
GEMINI_OK = '{"ok": 1}'
FOUR = ("extraction", "search", "market_opportunity", "competitor_analysis")


def server_error() -> Exception:
    return llm_client.genai_errors.ServerError(503, {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}})


class FakeGemini:
    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, **kwargs: Any) -> "FakeGemini":
        return self

    @property
    def models(self) -> "FakeGemini":
        return self

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls += 1
        outcome = self.outcomes[min(self.calls, len(self.outcomes)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return SimpleNamespace(text=outcome)

    def close(self) -> None:
        pass


class FakeNetwork:
    def __init__(self, tavily: list[Any] | None = None, groq: list[str] | None = None) -> None:
        self.tavily = tavily or [tavily_ok()]
        self.groq = groq or ["{}"]
        self.tavily_calls = 0
        self.groq_calls = 0

    def __call__(self, url: str, headers: Any = None, json: Any = None, timeout: Any = None, **kwargs: Any) -> Any:
        if url == search_client.API_URL:
            self.tavily_calls += 1
            outcome = self.tavily[min(self.tavily_calls, len(self.tavily)) - 1]
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        self.groq_calls += 1
        content = self.groq[min(self.groq_calls, len(self.groq)) - 1]
        return FakeHTTPResponse(200, {"choices": [{"index": 0, "message": {"content": content}, "finish_reason": "stop"}]})


def use_providers(monkeypatch: pytest.MonkeyPatch, *gemini: Any, tavily: list[Any] | None = None,
                  groq: list[str] | None = None) -> tuple[FakeGemini, FakeNetwork]:
    fake_gemini = FakeGemini(*(gemini or (GEMINI_OK,)))
    network = FakeNetwork(tavily, groq)
    monkeypatch.setattr(llm_client.genai, "Client", fake_gemini)
    monkeypatch.setattr(search_client.requests, "post", network)
    monkeypatch.setattr(llm_client, "time", SimpleNamespace(sleep=lambda seconds: None))
    if groq is not None:
        monkeypatch.setenv("GROQ_API_KEY", GROQ_TEST_KEY)
    return fake_gemini, network


def counted(action: Any) -> tuple[int, int]:
    counter = UsageCounter()
    with counting(counter):
        try:
            action()
        except AppError:
            pass
    return counter.totals()


@dataclass
class CallingStage:
    name: str
    llm: int = 0
    searches: int = 0
    error: Exception | None = None
    stop_on_failure = False

    def run(self, context: Any) -> Any:
        for _ in range(self.llm):
            llm_client.generate_json("system", "user")
        for _ in range(self.searches):
            search_client.search("query")
        if self.error is not None:
            raise self.error
        return context


def assert_consistent(usage: Usage, timings: dict[str, float]) -> None:
    assert usage.llm_calls == sum(entry.llm_calls for entry in usage.by_stage.values())
    assert usage.search_calls == sum(entry.search_calls for entry in usage.by_stage.values())
    assert all(entry.seconds == timings[stage] for stage, entry in usage.by_stage.items())
    assert TOTAL_KEY not in usage.by_stage


def test_the_counter_counts_nothing_outside_a_run() -> None:
    count_llm_call()
    count_search_call()
    counter = UsageCounter()
    assert counter.totals() == (0, 0)


def test_the_counter_is_scoped_to_its_block() -> None:
    first, second = UsageCounter(), UsageCounter()
    with counting(first):
        count_llm_call()
        with counting(second):
            count_search_call()
        count_search_call()
    count_llm_call()
    assert first.totals() == (1, 1) and second.totals() == (0, 1)


def test_the_counter_is_safe_across_threads() -> None:
    counter = UsageCounter()

    def work() -> None:
        for _ in range(500):
            counter.add_llm_call()
            counter.add_search_call()

    threads = [threading.Thread(target=work) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert counter.totals() == (4000, 4000)


def test_one_gemini_request_counts_once(monkeypatch: pytest.MonkeyPatch) -> None:
    use_providers(monkeypatch)
    assert counted(lambda: llm_client.generate_json("system", "user")) == (1, 0)


def test_every_gemini_retry_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, _ = use_providers(monkeypatch, server_error(), server_error(), GEMINI_OK)
    assert counted(lambda: llm_client.generate_json("system", "user")) == (3, 0)
    assert gemini.calls == 3


def test_a_request_that_fails_after_every_retry_counts_each_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, _ = use_providers(monkeypatch, server_error())
    assert counted(lambda: llm_client.generate_json("system", "user")) == (3, 0)
    assert gemini.calls == 3


def test_the_groq_fallback_counts_as_a_request(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, network = use_providers(monkeypatch, gemini_rate_limit(), groq=['{"ok": 2}'])
    assert counted(lambda: llm_client.generate_json("system", "user")) == (2, 0)
    assert gemini.calls == 1 and network.groq_calls == 1


def test_the_structured_repair_retry_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    use_providers(monkeypatch, LLM_REPLY_NOT_JSON, LLM_REPLY_OK)
    assert counted(lambda: call_structured("system", "user", ExtractedIdea, caller=llm_client.generate_json)) == (2, 0)


def test_a_retry_sent_to_groq_only_counts_each_request(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, network = use_providers(monkeypatch, gemini_rate_limit(), groq=[LLM_REPLY_NOT_JSON, LLM_REPLY_OK])
    assert counted(lambda: call_structured("system", "user", ExtractedIdea, caller=llm_client.generate_json)) == (3, 0)
    assert gemini.calls == 1 and network.groq_calls == 2


def test_a_call_that_is_not_sent_is_not_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, network = use_providers(monkeypatch)
    with deadline.stop_check(lambda: True):
        assert counted(lambda: llm_client.generate_json("system", "user")) == (0, 0)
        assert counted(lambda: search_client.search("query")) == (0, 0)
    assert gemini.calls == 0 and network.tavily_calls == 0


def test_every_tavily_request_counts_also_when_it_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _, network = use_providers(monkeypatch, tavily=[tavily_ok(), tavily_status(500)])
    counter = UsageCounter()
    with counting(counter):
        search_client.search("query")
        with pytest.raises(SearchAPIError):
            search_client.search("query")
    assert counter.totals() == (0, 2) and network.tavily_calls == 2


def test_a_search_without_a_key_is_not_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    use_providers(monkeypatch)
    monkeypatch.delenv("TAVILY_API_KEY")
    counter = UsageCounter()
    with counting(counter), pytest.raises(SearchConfigError):
        search_client.search("query")
    assert counter.totals() == (0, 0)


def test_a_milestone_1_run_records_its_real_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, network = use_providers(monkeypatch, LLM_REPLY_OK)
    result = run_pipeline(PIPELINE_SUBMISSION, STAGES)

    assert result.status == "complete"
    assert result.usage.by_stage == {
        "extraction": StageUsage(llm_calls=1, search_calls=0, seconds=result.timings["extraction"]),
        "search": StageUsage(llm_calls=0, search_calls=4, seconds=result.timings["search"]),
    }
    assert (result.usage.llm_calls, result.usage.search_calls) == (1, 4) == (gemini.calls, network.tavily_calls)
    assert result.versions == Versions(query_profile="v1", prompt_profile="v1",
                                       prompt_versions={"extraction": "extraction-v1"}, app_version=APP_VERSION)


def by_stage(result: PipelineResult) -> dict[str, tuple[int, int]]:
    return {stage: (entry.llm_calls, entry.search_calls) for stage, entry in result.usage.by_stage.items()}


def test_retries_are_counted_in_their_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, network = use_providers(monkeypatch, GEMINI_OK, server_error(), server_error(), GEMINI_OK, GEMINI_OK)
    stages = [CallingStage("one", llm=1), CallingStage("two", searches=3), CallingStage("three", llm=2),
              CallingStage("four", llm=0, error=AppError())]
    result = run_pipeline(PIPELINE_SUBMISSION, stages)

    assert by_stage(result) == {"one": (1, 0), "two": (0, 3), "three": (4, 0), "four": (0, 0)}
    assert (result.usage.llm_calls, result.usage.search_calls) == (5, 3) == (gemini.calls, network.tavily_calls)
    assert [error.stage for error in result.errors] == ["four"]
    assert_consistent(result.usage, result.timings)


def test_the_fallback_is_counted_in_its_stage_also_when_the_stage_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, network = use_providers(monkeypatch, GEMINI_OK, gemini_rate_limit(), GEMINI_OK, groq=['{"ok": 3}'])
    stages = [CallingStage("one", llm=1), CallingStage("two", llm=1, searches=1, error=AppError())]
    result = run_pipeline(PIPELINE_SUBMISSION, stages)

    assert by_stage(result) == {"one": (1, 0), "two": (2, 1)}
    assert (result.usage.llm_calls, result.usage.search_calls) == (3, 1)
    assert (gemini.calls, network.groq_calls, network.tavily_calls) == (2, 1, 1)
    assert_consistent(result.usage, result.timings)


def test_a_full_run_has_one_entry_per_stage_that_ran(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert list(result.usage.by_stage) == list(FOUR)
    assert_consistent(result.usage, result.timings)
    assert result.versions.prompt_versions == {
        "extraction": "extraction-v1", "market": "market-v1", "competitors": "competitors-v1",
    }


def use_client_level_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "run_web_search", lambda *args, **kwargs: PIPELINE_SEARCH)
    monkeypatch.setattr(market_size, "run_queries", lambda *args, **kwargs: NO_MARKET_SIZE_RESULTS)
    monkeypatch.setattr(competitor_agent, "run_queries", lambda *args, **kwargs: COMPETITOR_TARGETED)


FOUR_STAGE_REPLIES = (LLM_REPLY_OK, market_reply(), *competitor_replies())
FOUR_STAGE_VERSIONS = Versions(
    query_profile="v1",
    prompt_profile="v1",
    prompt_versions={"extraction": "extraction-v1", "market": "market-v1", "competitors": "competitors-v1"},
    app_version=APP_VERSION,
)


def test_a_fixed_four_stage_run_on_gemini_records_exact_counts_and_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    use_client_level_pipeline(monkeypatch)
    gemini, network = use_providers(monkeypatch, *FOUR_STAGE_REPLIES)
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert result.status == "complete"
    assert by_stage(result) == {"extraction": (1, 0), "search": (0, 0), "market_opportunity": (1, 0),
                                "competitor_analysis": (2, 0)}
    assert (result.usage.llm_calls, result.usage.search_calls) == (4, 0)
    assert (gemini.calls, network.groq_calls) == (4, 0)
    assert result.versions == FOUR_STAGE_VERSIONS
    assert_consistent(result.usage, result.timings)


def test_on_the_groq_path_each_call_counts_one_failed_gemini_attempt_and_one_groq_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_client_level_pipeline(monkeypatch)
    gemini, network = use_providers(monkeypatch, gemini_rate_limit(), groq=list(FOUR_STAGE_REPLIES))
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert result.status == "complete"
    assert by_stage(result) == {"extraction": (2, 0), "search": (0, 0), "market_opportunity": (2, 0),
                                "competitor_analysis": (4, 0)}
    assert (result.usage.llm_calls, result.usage.search_calls) == (8, 0)
    assert (gemini.calls, network.groq_calls) == (4, 4)
    assert result.versions == FOUR_STAGE_VERSIONS
    assert_consistent(result.usage, result.timings)


def test_on_the_groq_path_after_a_server_error_each_call_counts_one_gemini_attempt_and_one_groq_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_client_level_pipeline(monkeypatch)
    gemini, network = use_providers(monkeypatch, server_error(), groq=list(FOUR_STAGE_REPLIES))
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert result.status == "complete"
    assert by_stage(result) == {"extraction": (2, 0), "search": (0, 0), "market_opportunity": (2, 0),
                                "competitor_analysis": (4, 0)}
    assert (result.usage.llm_calls, result.usage.search_calls) == (8, 0)
    assert (gemini.calls, network.groq_calls) == (4, 4)
    assert result.versions == FOUR_STAGE_VERSIONS
    assert_consistent(result.usage, result.timings)


def test_the_same_fixed_run_records_the_same_counts_with_a_limit_or_a_cancel_check(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    plain = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)
    use_full_pipeline(monkeypatch)
    limited = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, time_limit_s=600.0, should_stop=lambda: False)

    assert by_stage(limited) == by_stage(plain) == {stage: (0, 0) for stage in FOUR}
    assert limited.versions == plain.versions == FOUR_STAGE_VERSIONS


def test_agent_level_fakes_never_reach_the_counted_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)
    assert (result.usage.llm_calls, result.usage.search_calls) == (0, 0)


def test_a_reviewed_idea_records_no_extraction_usage_or_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, idea=REVIEWED_IDEA)

    assert "extraction" not in result.usage.by_stage
    assert "extraction" not in result.versions.prompt_versions
    assert_consistent(result.usage, result.timings)


def test_a_skipped_stage_records_no_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch, search=(SearchAPIError(),))
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert list(result.usage.by_stage) == ["extraction", "search"]
    assert list(result.versions.prompt_versions) == ["extraction"]


def test_a_seven_stage_run_records_every_strategy_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_STAGES, constraints=StrategyConstraints(team_size=2))

    assert list(result.usage.by_stage) == [*FOUR, "swot_risk", "mvp_recommendation", "go_to_market"]
    assert {key: result.versions.prompt_versions[key] for key in ("swot", "mvp", "gtm")} == {
        "swot": "swot-v1", "mvp": "mvp-v1", "gtm": "gtm-v1",
    }
    assert_consistent(result.usage, result.timings)


def test_a_strategy_only_job_keeps_the_saved_usage_of_the_stages_it_does_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    saved = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)
    saved = saved.model_copy(update={"usage": Usage(
        llm_calls=3, search_calls=9,
        by_stage={**saved.usage.by_stage, "market_opportunity": StageUsage(llm_calls=3, search_calls=9, seconds=1.5)},
    )})
    use_fake_strategy(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=saved)

    assert list(result.usage.by_stage) == [*FOUR, "swot_risk", "mvp_recommendation", "go_to_market"]
    assert result.usage.by_stage["market_opportunity"] == StageUsage(llm_calls=3, search_calls=9, seconds=1.5)
    assert (result.usage.llm_calls, result.usage.search_calls) == (3, 9)
    assert list(result.versions.prompt_versions) == ["extraction", "market", "competitors", "swot", "mvp", "gtm"]


def test_a_strategy_only_job_on_an_old_result_counts_only_its_own_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    saved = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES).model_copy(update={"usage": None, "versions": None})
    use_fake_strategy(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=saved)

    assert list(result.usage.by_stage) == ["swot_risk", "mvp_recommendation", "go_to_market"]
    assert list(result.versions.prompt_versions) == ["swot", "mvp", "gtm"]


def test_every_stage_event_result_carries_the_usage_so_far(monkeypatch: pytest.MonkeyPatch) -> None:
    use_full_pipeline(monkeypatch)
    events: list[StageEvent] = []
    run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES, on_event=events.append)

    ended = [event for event in events if event.result is not None]
    assert [list(event.result.usage.by_stage) for event in ended] == [list(FOUR[: index + 1]) for index in range(4)]


def test_a_background_run_stores_usage_and_versions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    use_full_pipeline(monkeypatch)
    manager = RunManager(store_in(tmp_path))
    try:
        detail = finished(manager, manager.start(PIPELINE_SUBMISSION).id)
    finally:
        manager.shutdown()

    assert list(detail.result.usage.by_stage) == list(FOUR)
    assert detail.result.versions.app_version == APP_VERSION


def test_a_default_background_run_records_exact_usage_and_versions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    use_full_pipeline(monkeypatch)
    manager = RunManager(store_in(tmp_path))
    try:
        detail = finished(manager, manager.start(PIPELINE_SUBMISSION).id)
    finally:
        manager.shutdown()

    assert by_stage(detail.result) == {stage: (0, 0) for stage in FOUR}
    assert (detail.result.usage.llm_calls, detail.result.usage.search_calls) == (0, 0)
    assert detail.result.versions == FOUR_STAGE_VERSIONS
    assert_consistent(detail.result.usage, detail.result.timings)


def test_usage_and_versions_hold_no_secret_url_or_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    use_providers(monkeypatch, LLM_REPLY_OK)
    result = run_pipeline(PIPELINE_SUBMISSION, STAGES)
    data = {"usage": result.usage.model_dump(mode="json"), "versions": result.versions.model_dump(mode="json")}
    text = json.dumps(data)

    assert secret_findings(data) == []
    assert all(value not in text for value in ("test-llm-key", "test-tavily-key", "http", "system", "<submission>"))
    assert set(data["usage"]) == {"llm_calls", "search_calls", "by_stage"}
    assert all(set(entry) == {"llm_calls", "search_calls", "seconds"} for entry in data["usage"]["by_stage"].values())
    assert set(data["versions"]) == {"query_profile", "prompt_profile", "prompt_versions", "app_version"}


def test_the_app_version_is_the_meta_route_constant(client: Any) -> None:
    assert client.get("/api/meta").json()["version"] == APP_VERSION


def test_a_result_without_usage_and_versions_validates_with_null() -> None:
    result = PipelineResult(status="complete")
    assert result.usage is None and result.versions is None
    assert result.model_dump()["usage"] is None and result.model_dump()["versions"] is None


def test_usage_rejects_negative_counts() -> None:
    with pytest.raises(ValueError):
        StageUsage(llm_calls=-1)
    with pytest.raises(ValueError):
        Usage(search_calls=-1)


def assert_old_result(original: dict) -> None:
    validated = PipelineResult.model_validate(original)
    dumped = validated.model_dump(mode="json")
    assert {key: dumped[key] for key in original} == original
    assert dumped["usage"] is None and dumped["versions"] is None


@pytest.mark.parametrize("path", [*FIXTURE_RESULTS, SYNTHETIC], ids=lambda path: f"{path.parent.name}/{path.name}")
def test_every_saved_result_validates_without_usage_and_versions(path: Path) -> None:
    assert_old_result(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("path", FIXTURE_RUNS, ids=lambda path: path.name)
def test_every_saved_run_fixture_result_validates_without_usage_and_versions(path: Path) -> None:
    assert_old_result(json.loads(path.read_text(encoding="utf-8"))["result"])


def fingerprint(path: Path) -> tuple[str, int, int]:
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size, path.stat().st_mtime_ns


def test_every_result_in_a_copy_of_the_stored_runs_validates_without_usage_and_versions(tmp_path: Path) -> None:
    if not STORED_RUNS.exists():
        pytest.skip("no local run history")
    before = fingerprint(STORED_RUNS)
    copy_path = tmp_path / "runs_copy.db"
    source_db = sqlite3.connect(f"{STORED_RUNS.resolve().as_uri()}?mode=ro", uri=True)
    target_db = sqlite3.connect(copy_path)
    try:
        source_db.backup(target_db)
    finally:
        source_db.close()
    try:
        rows = target_db.execute("SELECT result_json FROM runs WHERE result_json IS NOT NULL").fetchall()
    finally:
        target_db.close()
    assert fingerprint(STORED_RUNS) == before
    assert rows
    for (text,) in rows:
        assert_old_result(json.loads(text))

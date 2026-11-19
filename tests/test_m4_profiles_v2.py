import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import config
from agents import competitor_analysis_agent as competitor_agent
from agents import extraction_agent, market_size, query_profile, web_search_agent
from agents.query_profile import (
    CANDIDATE_PHRASINGS,
    DIVERSE_EVIDENCE,
    MARKET_SIZE_DEPTH,
    NEWS_TOPIC,
    REGION_AND_YEAR,
    SEARCH_TERMS,
)
from app import create_app
from models.api import RunRequest
from models.schemas import (
    CompetitorCandidate,
    ExtractedIdea,
    IdeaSubmission,
    PipelineResult,
    SearchTermsIdea,
    StrategyConstraints,
)
from orchestrator import FULL_STAGES, STAGES, run_pipeline
from routes.meta_routes import APP_VERSION
from tests.fakes import VALID_EXTRACTION, FakeHTTPResponse, make_sequence
from tests.pipeline_fakes import PIPELINE_SUBMISSION, use_full_pipeline
from tests.test_m4_profiles_v1_snapshots import QUERY_SOURCES, load_result
from utils import groq_client, search_client
from utils.usage import UsageCounter, counting

ROOT = Path(__file__).resolve().parent.parent
TERMS = ["crop disease detection", "plant disease diagnosis app", "smallholder farm advisory"]
TERMS_TEXT = "crop disease detection plant disease diagnosis app"
IDEA = ExtractedIdea(**VALID_EXTRACTION)
TERMS_IDEA = SearchTermsIdea(**VALID_EXTRACTION, search_terms=TERMS)
REGION = "Maharashtra"
YEAR = 2026
ALL_FLAGS = (SEARCH_TERMS, REGION_AND_YEAR, NEWS_TOPIC, DIVERSE_EVIDENCE, CANDIDATE_PHRASINGS, MARKET_SIZE_DEPTH)
INDUSTRY = "Agriculture / AgriTech"
SOLUTION = "A phone app that detects crop diseases from"
PROBLEM = "Small farmers in India lose crops because diseases"
CUSTOMER = "Small farmers in India"


def candidate(name: str, kind: str = "direct") -> CompetitorCandidate:
    return CompetitorCandidate(name=name, type=kind, basis="sourced", source_ids=["S1"])


CANDIDATES = [candidate("Plantix"), candidate("CropDoc", "emerging"), candidate("FarmRise", "indirect")]


@pytest.fixture(autouse=True)
def fixed_year(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_search_agent, "current_year", lambda: YEAR)
    monkeypatch.delenv("QUERY_PROFILE", raising=False)
    monkeypatch.delenv("SEARCH_MAX_PARALLEL", raising=False)


def only(monkeypatch: pytest.MonkeyPatch, *flags: str) -> None:
    monkeypatch.setitem(query_profile.FLAGS, "v2", frozenset(flags))


def v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERY_PROFILE", "v2")


class Posts:
    def __init__(self, bodies: dict[str, Any] | None = None) -> None:
        self.bodies = bodies or {}
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, headers: Any = None, json: Any = None, timeout: Any = None, **kwargs: Any) -> Any:
        self.calls.append(dict(json))
        body = self.bodies.get(json["query"], {"answer": None, "results": [
            {"title": "Page", "url": f"https://site{len(self.calls)}.example/a", "content": "x" * 80, "score": 0.5},
        ]})
        return FakeHTTPResponse(200, body)


def test_the_profiles_and_flags_are_as_planned() -> None:
    assert config.QUERY_PROFILES == ("v1", "v2") and config.DEFAULT_QUERY_PROFILE == "v1"
    assert query_profile.FLAGS["v1"] == frozenset()
    assert query_profile.FLAGS["v2"] == frozenset({"Q-1", "Q-2", "Q-3", "Q-4", "Q-5", "Q-6"})
    assert query_profile.NEWS_SEARCH == {"topic": "news", "time_range": "year"}
    assert query_profile.DEEP_SEARCH == "advanced"


def test_an_unknown_query_profile_falls_back_to_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    for raw, expected in (("v2", "v2"), ("v1", "v1"), ("v3", "v1"), ("V2", "v1"), ("", "v1")):
        monkeypatch.setenv("QUERY_PROFILE", raw)
        assert config.get_settings().query_profile == expected


def test_v2_standard_queries_use_search_terms_region_and_year() -> None:
    assert web_search_agent.generate_queries(TERMS_IDEA, profile="v2", region=REGION) == [
        ("Market size and trends", f"{TERMS_TEXT} market size and growth {REGION} {YEAR}"),
        ("Competitors", f"{TERMS_TEXT} competitors and alternatives {REGION}"),
        ("Customer demand and pain points", f"{TERMS_TEXT} customer problems and demand {REGION}"),
        ("Recent news and funding", f"{TERMS_TEXT} funding and news {YEAR}"),
    ]


def test_v2_standard_queries_without_terms_or_region_use_todays_text() -> None:
    assert web_search_agent.generate_queries(IDEA, profile="v2") == [
        ("Market size and trends", f"{INDUSTRY} {SOLUTION} market size and growth {YEAR}"),
        ("Competitors", f"{PROBLEM} competitors and alternatives"),
        ("Customer demand and pain points", f"{CUSTOMER} {PROBLEM} customer problems and demand"),
        ("Recent news and funding", f"{INDUSTRY} funding and news {YEAR}"),
    ]
    empty = SearchTermsIdea(**VALID_EXTRACTION)
    assert web_search_agent.generate_queries(empty, profile="v2") == web_search_agent.generate_queries(IDEA, profile="v2")


def test_a_long_region_is_kept_and_the_query_stays_within_the_limit() -> None:
    region = "Maharashtra Karnataka Tamil Nadu Kerala Goa Punjab Haryana Assam Bihar"
    long_terms = SearchTermsIdea(**VALID_EXTRACTION, search_terms=["a" * 40, "b" * 40, "c" * 40])
    queries = web_search_agent.generate_queries(long_terms, profile="v2", region=region)
    shown = "Maharashtra Karnataka Tamil Nadu Kerala Goa Punjab Haryana"
    assert queries[0][1].endswith(f" {shown} {YEAR}") and queries[3][1].endswith(f" {YEAR}")
    assert all(len(query) <= web_search_agent.MAX_QUERY_CHARS for _, query in queries)


def test_v2_market_size_queries_add_units_region_and_terms() -> None:
    assert market_size.market_size_queries(TERMS_IDEA, profile="v2", region=REGION) == [
        ("Market size for this idea", f"{TERMS_TEXT} market size {REGION} billion"),
        ("Market size for the target customers", f"{TERMS_TEXT} number of users or customers {REGION}"),
    ]
    assert market_size.market_size_queries(IDEA, profile="v2") == [
        ("Market size for this idea", "CropScan AI crop disease detection market size billion"),
        ("Market size for the target customers", "CropScan AI crop disease detection number of users or customers"),
    ]


def test_v2_competitor_discovery_uses_two_phrasings() -> None:
    alternatives = ("Alternatives and substitutes", f"alternatives to {TERMS_TEXT}")
    solving = ("Services that solve the problem", f"apps or services that solve {PROBLEM}")
    emerging = ("Emerging approaches", f"{INDUSTRY} {SOLUTION} emerging startups new approaches")
    assert competitor_agent.generic_queries(TERMS_IDEA, profile="v2") == [alternatives, solving, emerging]
    assert competitor_agent.competitor_queries([], TERMS_IDEA, 5, profile="v2") == [alternatives, solving, emerging]
    assert competitor_agent.competitor_queries(CANDIDATES, TERMS_IDEA, 5, profile="v2") == [
        ("Competitor: Plantix", "Plantix pricing features"),
        ("Competitor: CropDoc", "CropDoc pricing features"),
        ("Competitor: FarmRise", "FarmRise pricing features"),
        alternatives,
        solving,
    ]
    assert competitor_agent.generic_queries(IDEA, profile="v2")[0] == ("Alternatives and substitutes", f"alternatives to {SOLUTION}")


@pytest.mark.parametrize("limit", [1, 2, 3, 4, 5, 6, 9])
def test_v2_competitor_searches_never_exceed_the_limit(limit: int) -> None:
    for candidates in ([], CANDIDATES[:1], CANDIDATES):
        v1 = competitor_agent.competitor_queries(candidates, IDEA, limit)
        queries = competitor_agent.competitor_queries(candidates, IDEA, limit, profile="v2")
        assert len(queries) <= limit
        assert len(queries) - len(v1) in (0, 1)
    assert len(competitor_agent.competitor_queries([], IDEA, 5, profile="v2")) == 3
    assert len(competitor_agent.competitor_queries([], IDEA, 5)) == 2


def all_builders(idea: ExtractedIdea, profile: str) -> dict:
    limit = config.DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES
    return {
        "standard": web_search_agent.generate_queries(idea, profile=profile, region=REGION),
        "market_size": market_size.market_size_queries(idea, profile=profile, region=REGION),
        "generic": competitor_agent.competitor_queries([], idea, limit, profile=profile),
        "named": competitor_agent.competitor_queries(CANDIDATES, idea, limit, profile=profile),
        "options": web_search_agent.query_options(profile),
    }


def saved_ideas() -> list[SearchTermsIdea]:
    ideas = [load_result(path).idea for path in QUERY_SOURCES]
    return [SearchTermsIdea(**idea.model_dump(), search_terms=TERMS) for idea in ideas]


def test_v2_with_every_flag_off_builds_exactly_the_v1_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    only(monkeypatch)
    for idea in saved_ideas():
        assert all_builders(idea, "v2") == all_builders(idea, "v1")


@pytest.mark.parametrize("flag", ALL_FLAGS)
def test_each_flag_changes_only_its_own_queries(monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    owned = {
        SEARCH_TERMS: {"standard", "market_size"},
        REGION_AND_YEAR: {"standard"},
        NEWS_TOPIC: {"options"},
        DIVERSE_EVIDENCE: set(),
        CANDIDATE_PHRASINGS: {"generic", "named"},
        MARKET_SIZE_DEPTH: {"market_size"},
    }[flag]
    only(monkeypatch, flag)
    for idea in saved_ideas():
        v1, candidate_set = all_builders(idea, "v1"), all_builders(idea, "v2")
        changed = {name for name in v1 if v1[name] != candidate_set[name]}
        assert changed <= owned
    assert {name for name in v1 if v1[name] != candidate_set[name]} == owned


def test_only_region_and_year_appends_them_to_todays_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    only(monkeypatch, REGION_AND_YEAR)
    v1 = dict(web_search_agent.generate_queries(TERMS_IDEA))
    shown = dict(web_search_agent.generate_queries(TERMS_IDEA, profile="v2", region=REGION))
    assert shown["Market size and trends"] == f"{v1['Market size and trends']} {REGION} {YEAR}"
    assert shown["Competitors"] == f"{v1['Competitors']} {REGION}"
    assert shown["Customer demand and pain points"] == f"{v1['Customer demand and pain points']} {REGION}"
    assert shown["Recent news and funding"] == f"{v1['Recent news and funding']} {YEAR}"
    without = dict(web_search_agent.generate_queries(TERMS_IDEA, profile="v2"))
    assert without["Competitors"] == v1["Competitors"] and without["Recent news and funding"].endswith(str(YEAR))


def test_the_news_query_alone_asks_for_recent_news(monkeypatch: pytest.MonkeyPatch) -> None:
    posts = Posts()
    monkeypatch.setattr(search_client.requests, "post", posts)
    v2(monkeypatch)
    web_search_agent.run_web_search(TERMS_IDEA, region=REGION)
    news = [call for call in posts.calls if call["query"].endswith("funding and news 2026")]
    assert len(posts.calls) == 4 and len(news) == 1
    assert news[0] == {"query": f"{TERMS_TEXT} funding and news 2026", "search_depth": "basic", "max_results": 3,
                       "include_answer": True, "topic": "news", "time_range": "year"}
    assert all(set(call) == {"query", "search_depth", "max_results", "include_answer"} for call in posts.calls if call not in news)


def test_v1_requests_send_the_same_four_fields_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    posts = Posts()
    monkeypatch.setattr(search_client.requests, "post", posts)
    web_search_agent.run_web_search(TERMS_IDEA)
    market_size.search_market_size(TERMS_IDEA)
    assert len(posts.calls) == 6
    assert all(set(call) == {"query", "search_depth", "max_results", "include_answer"} for call in posts.calls)
    assert {call["search_depth"] for call in posts.calls} == {"basic"}
    assert [call["query"] for call in posts.calls[:4]] == [query for _, query in web_search_agent.generate_queries(IDEA)]


def test_v2_market_size_searches_use_the_deeper_level(monkeypatch: pytest.MonkeyPatch) -> None:
    posts = Posts()
    monkeypatch.setattr(search_client.requests, "post", posts)
    v2(monkeypatch)
    bundle, warnings = market_size.search_market_size(TERMS_IDEA, region=REGION)
    assert [call["query"] for call in posts.calls] == [query for _, query in market_size.market_size_queries(
        TERMS_IDEA, profile="v2", region=REGION)]
    assert {call["search_depth"] for call in posts.calls} == {"advanced"}
    assert bundle.total_results == 2 and warnings == []


def result(url: str, score: float | None, content: str = "useful text about crop disease apps " * 2) -> dict:
    return {"title": url, "url": url, "content": content, "score": score}


DIVERSE_BODIES = {
    "first": {"answer": None, "results": [
        result("https://a.example/1", 0.9),
        result("https://a.example/2", 0.8),
        result("https://www.a.example/3", 0.95),
        result("https://a.example/4", 0.7),
        result("https://b.example/short", 0.99, "x" * 39),
        result("https://b.example/enough", 0.1, "y" * 40),
    ]},
    "second": {"answer": "An engine summary.", "results": [
        result("https://a.example/5", 0.99),
        result("https://c.example/1", None),
    ]},
    "third": {"answer": None, "results": [result("https://A.example/6", 0.5)]},
}
DIVERSE_QUERIES = [("First", "first"), ("Second", "second"), ("Third", "third")]


def test_v2_keeps_two_results_per_domain_and_drops_short_snippets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_client.requests, "post", Posts(DIVERSE_BODIES))
    v2(monkeypatch)
    bundle = web_search_agent.run_queries(DIVERSE_QUERIES)
    urls = [[item.url for item in section.results] for section in bundle.sections]
    assert urls == [["https://a.example/1", "https://www.a.example/3", "https://b.example/enough"], ["https://c.example/1"], []]
    assert bundle.total_results == 4 and bundle.queries_failed == 0
    assert bundle.sections[1].answer == "An engine summary."
    assert bundle.sections[2].error == web_search_agent.MSG_NO_RESULTS


def test_v1_keeps_every_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_client.requests, "post", Posts(DIVERSE_BODIES))
    bundle = web_search_agent.run_queries(DIVERSE_QUERIES)
    assert [len(section.results) for section in bundle.sections] == [6, 2, 1]


def test_the_evidence_filter_is_the_same_in_parallel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_client.requests, "post", Posts(DIVERSE_BODIES))
    v2(monkeypatch)
    sequential = web_search_agent.run_queries(DIVERSE_QUERIES)
    monkeypatch.setenv("SEARCH_MAX_PARALLEL", "3")
    assert web_search_agent.run_queries(DIVERSE_QUERIES).model_dump() == sequential.model_dump()


SUBMISSION = PIPELINE_SUBMISSION


def test_search_terms_are_trimmed_deduplicated_short_and_free_of_unnamed_brands() -> None:
    raw = [
        "  crop   disease detection ",
        "Crop disease detection",
        "x" * 41,
        "Plantix alternatives",
        "LeafDoc competitors",
        "plant disease app India",
        "",
        "smallholder farm advisory",
        "farm input advice",
        "sixth term",
    ]
    assert extraction_agent.clean_search_terms(raw, SUBMISSION) == [
        "crop disease detection",
        "LeafDoc competitors",
        "plant disease app India",
        "smallholder farm advisory",
        "farm input advice",
    ]
    assert extraction_agent.clean_search_terms(["a" * 40, "b", "c"], SUBMISSION) == ["a" * 40, "b", "c"]


def test_fewer_than_three_usable_terms_means_none() -> None:
    assert extraction_agent.clean_search_terms(["crop disease detection", "Plantix", "x" * 41], SUBMISSION) == []
    assert extraction_agent.clean_search_terms([], SUBMISSION) == []


def reply(**extra: Any) -> str:
    return json.dumps({**VALID_EXTRACTION, **extra})


def test_v2_extraction_asks_for_search_terms_and_cleans_them(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_sequence(reply(search_terms=[*TERMS, "Plantix alternatives"]))
    monkeypatch.setattr(extraction_agent, "generate_json", fake)
    v2(monkeypatch)
    idea = extraction_agent.extract_idea(SUBMISSION)
    assert isinstance(idea, SearchTermsIdea) and idea.search_terms == TERMS
    assert fake.calls[0][0] == (extraction_agent.SEARCH_TERMS_SYSTEM_PROMPT, extraction_agent.build_user_prompt(SUBMISSION))
    assert "`search_terms` (array of 3 to 5 short noun phrases" in extraction_agent.SEARCH_TERMS_SYSTEM_PROMPT
    assert extraction_agent.SEARCH_TERMS_SYSTEM_PROMPT.startswith(extraction_agent.SYSTEM_PROMPT[:300])


def test_a_v2_reply_without_search_terms_still_gives_an_idea(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extraction_agent, "generate_json", make_sequence(reply()))
    v2(monkeypatch)
    idea = extraction_agent.extract_idea(SUBMISSION)
    assert idea.search_terms == []
    assert web_search_agent.generate_queries(idea, profile="v2") == web_search_agent.generate_queries(IDEA, profile="v2")


def test_v1_extraction_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_sequence(reply())
    monkeypatch.setattr(extraction_agent, "generate_json", fake)
    idea = extraction_agent.extract_idea(SUBMISSION)
    assert type(idea) is ExtractedIdea
    assert fake.calls[0][0][0] == extraction_agent.SYSTEM_PROMPT
    assert extraction_agent.prompt_version() == "extraction-v1" == extraction_agent.prompt_version("v1")
    assert extraction_agent.prompt_version("v2") == "extraction-v1+search-terms"


def test_the_v2_reply_schema_asks_groq_for_search_terms_and_v1_does_not() -> None:
    strict = groq_client.strict_schema(SearchTermsIdea)
    assert "search_terms" in strict["properties"] and "search_terms" in strict["required"]
    assert "search_terms" not in groq_client.strict_schema(ExtractedIdea)["properties"]


def test_search_terms_are_never_stored_or_accepted_from_the_review_step() -> None:
    stored = PipelineResult(status="complete", idea=TERMS_IDEA)
    assert "search_terms" not in stored.model_dump_json()
    assert PipelineResult.model_validate_json(stored.model_dump_json()).idea == IDEA
    with pytest.raises(ValueError):
        RunRequest.model_validate({"submission": SUBMISSION.model_dump(), "idea_override": TERMS_IDEA.model_dump()})


def test_the_review_step_never_shows_search_terms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RUNS_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.setattr(extraction_agent, "generate_json", make_sequence(reply(search_terms=TERMS)))
    v2(monkeypatch)
    body = TestClient(create_app()).post("/api/ideas/extract", json=SUBMISSION.model_dump()).json()
    assert body == VALID_EXTRACTION


def test_old_ideas_without_terms_build_v2_queries_from_their_text() -> None:
    for path in QUERY_SOURCES:
        idea = load_result(path).idea
        assert not hasattr(idea, "search_terms")
        queries = web_search_agent.generate_queries(idea, profile="v2")
        assert len(queries) == 4 and all(query.strip() for _, query in queries)


def test_a_v2_milestone_1_run_records_its_profile_versions_and_real_searches(monkeypatch: pytest.MonkeyPatch) -> None:
    posts = Posts()
    monkeypatch.setattr(search_client.requests, "post", posts)
    monkeypatch.setattr(extraction_agent, "generate_json", make_sequence(reply(search_terms=TERMS)))
    v2(monkeypatch)
    result = run_pipeline(SUBMISSION, STAGES)

    assert result.status == "complete"
    assert result.versions.query_profile == "v2" and result.versions.prompt_profile == "v1"
    assert result.versions.prompt_versions == {"extraction": "extraction-v1+search-terms"}
    assert result.versions.app_version == APP_VERSION
    assert result.usage.search_calls == 4 == len(posts.calls)
    assert [section.query for section in result.search.sections] == [
        query for _, query in web_search_agent.generate_queries(TERMS_IDEA, profile="v2")
    ]
    assert "search_terms" not in result.model_dump_json()


def test_a_v2_full_run_passes_the_launch_region_and_the_deeper_level(monkeypatch: pytest.MonkeyPatch) -> None:
    v2(monkeypatch)
    fakes = use_full_pipeline(monkeypatch, extraction=(reply(search_terms=TERMS),))
    constraints = StrategyConstraints(launch_region=REGION)
    result = run_pipeline(SUBMISSION, FULL_STAGES, constraints=constraints)

    assert result.status == "complete"
    assert fakes.search.calls[0][1] == {"region": REGION}
    assert isinstance(fakes.search.calls[0][0][0], SearchTermsIdea)
    market_queries, market_options = fakes.market_search.calls[0]
    assert market_queries[0] == market_size.market_size_queries(TERMS_IDEA, profile="v2", region=REGION)
    assert market_options["depth"] == "advanced"
    competitor_queries = fakes.competitor_search.calls[0][0][0]
    assert competitor_queries == competitor_agent.competitor_queries(
        result.competitor_candidates, TERMS_IDEA, config.DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES, profile="v2"
    )
    assert ("Services that solve the problem", f"apps or services that solve {PROBLEM}") in competitor_queries
    assert result.versions.query_profile == "v2"
    assert result.versions.prompt_versions["extraction"] == "extraction-v1+search-terms"


def test_a_v1_full_run_passes_nothing_new(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = use_full_pipeline(monkeypatch)
    result = run_pipeline(SUBMISSION, FULL_STAGES, constraints=StrategyConstraints(launch_region=REGION))
    assert result.status == "complete"
    assert fakes.search.calls[0][1] == {}
    assert fakes.market_search.calls[0][1] == {"snippet": market_size.focused_snippet}
    assert result.versions.query_profile == "v1"
    assert result.versions.prompt_versions["extraction"] == "extraction-v1"


def test_v2_counts_its_extra_searches(monkeypatch: pytest.MonkeyPatch) -> None:
    posts = Posts()
    monkeypatch.setattr(search_client.requests, "post", posts)
    counts = {}
    for profile in ("v1", "v2"):
        monkeypatch.setenv("QUERY_PROFILE", profile)
        counter = UsageCounter()
        with counting(counter):
            competitor_agent.search_competitors(competitor_agent.competitor_queries([], TERMS_IDEA, 5, profile=profile))
        counts[profile] = counter.totals()[1]
    assert counts == {"v1": 2, "v2": 3}


def test_the_env_example_documents_the_v2_query_profile() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "# QUERY_PROFILE=v1" in text.splitlines()
    assert "QUERY_PROFILE is v1 (today's queries) or v2" in text


def test_the_founder_text_counts_every_submission_field() -> None:
    submission = IdeaSubmission(
        idea_description="An app for Kisan cooperatives that spots disease early on the farm.",
        industry="AgriTech",
        target_customers="Farmers in Assam",
        relevant_details="Pilot with Tata partners",
    )
    terms = ["kisan crop advisory", "AgriTech disease alerts", "Assam farm support", "Tata farm apps", "Bayer crop tools"]
    assert extraction_agent.clean_search_terms(terms, submission) == terms[:4]

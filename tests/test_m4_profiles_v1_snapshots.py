import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

import config
from agents import advisor_agent, evidence, extraction_agent, gtm_agent, market_size, mvp_agent, swot_risk_agent
from agents import competitor_analysis_agent as competitor_agent
from agents import market_opportunity_agent as market_agent
from agents import web_search_agent
from agents.evidence import build_evidence
from agents.strategy_context import build_digest
from models.schemas import (
    CandidateList,
    CompetitorAnalysisDraft,
    ExtractedIdea,
    IdeaSubmission,
    MarketOpportunityDraft,
    PipelineResult,
)
from models.strategy_drafts import AdvisorDraft, GtmDraft, MvpDraft, SwotRiskDraft
from utils import groq_client, structured

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = Path(__file__).resolve().parent / "snapshots" / "m4_v1_profiles.json"
SYNTHETIC = "web/src/test/strategyFixture.synthetic.json"
M2_IDEAS = ("agritech", "fintech_cashflow", "foodtech_surplus")
QUERY_SOURCES = (
    "docs/test_runs/agritech.json",
    "docs/test_runs/fintech.json",
    "docs/test_runs/foodtech.json",
    "docs/test_runs/healthtech.json",
    *(f"docs/test_runs_m2/{name}.json" for name in M2_IDEAS),
    SYNTHETIC,
)
FIXED_CANARY = "ADVISOR-MARKER-" + "0" * 16
PROMPT_SETTINGS = (
    "EVIDENCE_MAX_ITEMS",
    "STRATEGY_DIGEST_MAX_CHARS",
    "CHAT_CONTEXT_MAX_CHARS",
    "CHAT_HISTORY_TURNS",
    "COMPETITOR_MAX_EXTRA_QUERIES",
    "QUERY_PROFILE",
    "PROMPT_PROFILE",
)
CONSTANTS = (
    (extraction_agent, "agents/extraction_agent.py", ("SYSTEM_PROMPT",)),
    (structured, "utils/structured.py", ("RETRY_INSTRUCTION", "PROBLEM_NOT_JSON")),
    (evidence, "agents/evidence.py", ("EVIDENCE_INSTRUCTION",)),
    (market_agent, "agents/market_opportunity_agent.py", ("SCHEMA_TEXT", "SYSTEM_PROMPT")),
    (competitor_agent, "agents/competitor_analysis_agent.py",
     ("CANDIDATE_SCHEMA", "SYSTEM_CANDIDATES", "ANALYSIS_SCHEMA", "SYSTEM_ANALYSIS")),
    (swot_risk_agent, "agents/swot_risk_agent.py", ("SHARED_RULES", "ROLE", "SYSTEM_PROMPT", "SCHEMA_TEXT", "LENGTH_TEXT", "TASK_TEXT")),
    (mvp_agent, "agents/mvp_agent.py", ("SHARED_RULES", "ROLE", "SYSTEM_PROMPT", "SCHEMA_TEXT", "LENGTH_TEXT", "TASK_TEXT")),
    (gtm_agent, "agents/gtm_agent.py", ("SHARED_RULES", "ROLE", "SYSTEM_PROMPT", "SCHEMA_TEXT", "LENGTH_TEXT", "TASK_TEXT")),
    (advisor_agent, "agents/advisor_agent.py", ("SHARED_RULES", "ROLE", "SCHEMA_TEXT")),
)
REPLY_MODELS = (
    ExtractedIdea,
    MarketOpportunityDraft,
    CandidateList,
    CompetitorAnalysisDraft,
    SwotRiskDraft,
    MvpDraft,
    GtmDraft,
    AdvisorDraft,
)
PROMPT_BUILDERS = (
    extraction_agent.build_user_prompt,
    market_agent.build_user_prompt,
    competitor_agent.build_candidate_prompt,
    competitor_agent.build_analysis_prompt,
    swot_risk_agent.build_prompt,
    mvp_agent.build_prompt,
    gtm_agent.build_prompt,
)
QUERY_BUILDERS = (
    web_search_agent.generate_queries,
    market_size.market_size_queries,
    competitor_agent.generic_queries,
    competitor_agent.competitor_queries,
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def pair(system: str, user: str) -> dict:
    return {"system_sha256": sha(system), "system_chars": len(system), "user_sha256": sha(user), "user_chars": len(user)}


def load_result(path: str) -> PipelineResult:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return PipelineResult.model_validate(data.get("result", data) if "stages" in data else data)


def submission(name: str) -> IdeaSubmission:
    return IdeaSubmission(**json.loads((ROOT / "data" / "test_ideas" / f"{name}.json").read_text(encoding="utf-8")))


def advisor_questions() -> tuple:
    tree = ast.parse((ROOT / "scripts" / "check_advisor_live.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "QUESTIONS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError("QUESTIONS")


def static_prompts() -> dict:
    return {f"{path}:{name}": sha(getattr(module, name)) for module, path, names in CONSTANTS for name in names}


def extraction_prompts() -> dict:
    found = {}
    for path in sorted((ROOT / "data" / "test_ideas").glob("*.json")):
        found[path.name] = pair(extraction_agent.SYSTEM_PROMPT, extraction_agent.build_user_prompt(submission(path.stem)))
    return found


def synthetic_prompts() -> dict:
    result = load_result(SYNTHETIC)
    idea = result.idea
    market_items = market_size.market_evidence(result.search, result.market_search, idea)
    standard = build_evidence(result.search)
    candidates = list(result.competitor_candidates)
    merged = competitor_agent.competitor_evidence(result.search, result.competitor_search, candidates)
    context = competitor_agent.market_context_for_competitors(result.market)
    found = {
        "market": pair(market_agent.SYSTEM_PROMPT, market_agent.build_user_prompt(idea, market_items)),
        "competitor phase A": pair(competitor_agent.SYSTEM_CANDIDATES, competitor_agent.build_candidate_prompt(idea, None, standard)),
        "competitor phase C": pair(
            competitor_agent.SYSTEM_ANALYSIS, competitor_agent.build_analysis_prompt(idea, context, candidates, merged)
        ),
    }
    digests = {
        "swot": (swot_risk_agent.build_prompt, build_digest(idea, result.constraints, result.market, result.competitors)),
        "mvp": (mvp_agent.build_prompt, build_digest(idea, result.constraints, result.market, result.competitors, swot=result.swot)),
        "gtm": (gtm_agent.build_prompt, build_digest(
            idea, result.constraints, result.market, result.competitors, swot=result.swot, mvp=result.mvp
        )),
    }
    for name, (builder, digest) in digests.items():
        found[name] = pair(*builder(digest))
    plain = result.model_copy(update={"swot": None, "mvp": None, "gtm": None})
    for topic, question, _expected, strip in advisor_questions():
        context = advisor_agent.build_context(plain if strip else result, advisor_agent.route_question(question))
        if not context.answerable:
            found[f"advisor {topic}"] = {"model_call": False}
            continue
        found[f"advisor {topic}"] = pair(*advisor_agent.build_prompt(context, (), question, FIXED_CANARY))
    return found


def saved_live_prompts() -> dict:
    found = {}
    for name in M2_IDEAS:
        saved = load_result(f"docs/test_runs_m2/{name}.json")
        items = build_evidence(saved.search)
        found[f"{name} competitor phase A"] = pair(
            competitor_agent.SYSTEM_CANDIDATES, competitor_agent.build_candidate_prompt(saved.idea, submission(name), items)
        )
        found[f"{name} swot"] = pair(*swot_risk_agent.build_prompt(build_digest(saved.idea, None, saved.market, saved.competitors)))
    return found


def query_sets() -> dict:
    found = {}
    for path in QUERY_SOURCES:
        saved = load_result(path)
        row = {
            "standard": [list(item) for item in web_search_agent.generate_queries(saved.idea)],
            "market_size": [list(item) for item in market_size.market_size_queries(saved.idea)],
            "competitor_generic": [
                list(item)
                for item in competitor_agent.competitor_queries([], saved.idea, config.DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES)
            ],
        }
        if saved.competitor_candidates:
            row["competitor_with_candidates"] = [
                list(item)
                for item in competitor_agent.competitor_queries(
                    list(saved.competitor_candidates), saved.idea, config.DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES
                )
            ]
        found[path] = row
    return found


def reply_schemas() -> dict:
    return {
        model.__name__: {
            "pydantic_json_schema_sha256": sha(canonical(model.model_json_schema())),
            "groq_strict_schema_sha256": sha(canonical(groq_client.strict_schema(model))),
        }
        for model in REPLY_MODELS
    }


def render_snapshot() -> dict:
    return {
        "static_prompts": static_prompts(),
        "extraction": extraction_prompts(),
        "synthetic": synthetic_prompts(),
        "saved_live": saved_live_prompts(),
        "queries": query_sets(),
        "reply_schemas": reply_schemas(),
    }


@pytest.fixture(autouse=True)
def default_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in PROMPT_SETTINGS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="module")
def stored() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@pytest.mark.parametrize("part", ["static_prompts", "extraction", "synthetic", "saved_live", "queries", "reply_schemas"])
def test_every_v1_prompt_query_and_schema_equals_its_snapshot(stored: dict, part: str) -> None:
    rendered = render_snapshot()[part]
    assert set(rendered) == set(stored[part])
    for key, value in rendered.items():
        assert value == stored[part][key], key


def test_the_snapshot_covers_every_prompt_and_query_source(stored: dict) -> None:
    assert len(stored["static_prompts"]) == 31
    assert len(stored["extraction"]) == 6
    assert len(stored["synthetic"]) == 14
    assert len(stored["saved_live"]) == 6
    assert sorted(stored["queries"]) == sorted(QUERY_SOURCES)
    assert len(stored["reply_schemas"]) == 8


def test_the_v1_extraction_reply_schema_is_unchanged(stored: dict) -> None:
    assert sha(canonical(groq_client.strict_schema(ExtractedIdea))) == stored["reply_schemas"]["ExtractedIdea"]["groq_strict_schema_sha256"]
    assert "search_terms" not in ExtractedIdea.model_fields


@pytest.mark.parametrize("builder", [*PROMPT_BUILDERS, *QUERY_BUILDERS], ids=lambda builder: f"{builder.__module__}.{builder.__name__}")
def test_every_prompt_and_query_builder_takes_a_profile_defaulting_to_v1(builder) -> None:
    parameter = inspect.signature(builder).parameters["profile"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default == "v1"


def test_an_explicit_v1_profile_renders_the_same_text() -> None:
    result = load_result(SYNTHETIC)
    idea = result.idea
    items = build_evidence(result.search)
    candidates = list(result.competitor_candidates)
    digest = build_digest(idea, result.constraints, result.market, result.competitors)
    limit = config.DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES
    assert extraction_agent.build_user_prompt(submission("agritech"), profile="v1") == extraction_agent.build_user_prompt(submission("agritech"))
    assert market_agent.build_user_prompt(idea, items, profile="v1") == market_agent.build_user_prompt(idea, items)
    assert competitor_agent.build_candidate_prompt(idea, None, items, profile="v1") == competitor_agent.build_candidate_prompt(idea, None, items)
    assert competitor_agent.build_analysis_prompt(idea, None, candidates, items, profile="v1") == competitor_agent.build_analysis_prompt(
        idea, None, candidates, items
    )
    for builder in (swot_risk_agent.build_prompt, mvp_agent.build_prompt, gtm_agent.build_prompt):
        assert builder(digest, profile="v1") == builder(digest)
    assert web_search_agent.generate_queries(idea, profile="v1") == web_search_agent.generate_queries(idea)
    assert market_size.market_size_queries(idea, profile="v1") == market_size.market_size_queries(idea)
    assert competitor_agent.generic_queries(idea, profile="v1") == competitor_agent.generic_queries(idea)
    assert competitor_agent.competitor_queries(candidates, idea, limit, profile="v1") == competitor_agent.competitor_queries(
        candidates, idea, limit
    )


def test_only_v1_profiles_are_valid_for_now(monkeypatch: pytest.MonkeyPatch) -> None:
    assert config.QUERY_PROFILES == ("v1", "v2") and config.PROMPT_PROFILES == ("v1", "v2")
    assert config.get_settings().query_profile == "v1" and config.get_settings().prompt_profile == "v1"
    monkeypatch.setenv("QUERY_PROFILE", "v1")
    monkeypatch.setenv("PROMPT_PROFILE", "v1")
    assert config.get_settings().query_profile == "v1" and config.get_settings().prompt_profile == "v1"
    monkeypatch.setenv("QUERY_PROFILE", "v2")
    monkeypatch.setenv("PROMPT_PROFILE", " ")
    assert config.get_settings().query_profile == "v2" and config.get_settings().prompt_profile == "v1"

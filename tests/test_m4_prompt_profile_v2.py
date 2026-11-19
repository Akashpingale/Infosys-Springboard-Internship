from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import config
from agents import competitor_analysis_agent as competitor_agent
from agents import extraction_agent, gtm_agent, market_size, mvp_agent, prompt_profile, swot_risk_agent
from agents import market_opportunity_agent as market_agent
from agents.evidence import build_evidence
from agents.prompt_profile import (
    DISTINCT_FACTS,
    FEATURE_WORDING,
    FIELD_LENGTHS,
    MATRIX_CONSISTENCY,
    RULE_TEXT,
    RULES_HEADING,
    SOURCE_RULES,
    SPECIFIC_POINTS,
)
from agents.strategy_context import DIGEST_CLOSE, DIGEST_OPEN, build_digest, build_facts, distinct_facts
from models.schemas import PipelineResult, StrategyConstraints
from orchestrator import FULL_STAGES, STRATEGY_STAGES, run_pipeline
from tests.fakes import LLM_REPLY_OK
from tests.m2_fakes import COMPETITOR_TARGETED, NO_MARKET_SIZE_RESULTS
from tests.m3_fakes import use_fake_strategy
from tests.pipeline_fakes import PIPELINE_SEARCH, PIPELINE_SUBMISSION, competitor_replies, market_reply, use_full_pipeline
from tests.test_m4_profiles_v1_snapshots import SYNTHETIC, load_result, submission
from utils import llm_client

ROOT = Path(__file__).resolve().parent.parent
IDEA_NAMES = sorted(path.stem for path in (ROOT / "data" / "test_ideas").glob("*.json"))
EXTRA_CHARS_MAX = 700
KEYWORDS = {
    SOURCE_RULES: ("units and magnitudes exactly", "cut off in the snippet", "conclusions the source does not state",
                   "pain points about this idea's problem", "report both figures"),
    FIELD_LENGTHS: ("each field to the stated length", "fewer, stronger points"),
    FEATURE_WORDING: ("key features must come from its own cited text", "same wording for a feature"),
    SPECIFIC_POINTS: ("specific from this idea's own facts", "would fit any startup"),
}
STRATEGY_BUILDERS = {"swot": swot_risk_agent.build_prompt, "mvp": mvp_agent.build_prompt, "gtm": gtm_agent.build_prompt}


class Stop(Exception):
    pass


@pytest.fixture(autouse=True)
def default_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PROMPT_PROFILE", "QUERY_PROFILE", "EVIDENCE_MAX_ITEMS", "STRATEGY_DIGEST_MAX_CHARS"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="module")
def synthetic() -> PipelineResult:
    return load_result(SYNTHETIC)


def digests(result: PipelineResult, profile: str = "v1") -> dict:
    inputs = (result.idea, result.constraints, result.market, result.competitors)
    return {
        "swot": build_digest(*inputs, profile=profile),
        "mvp": build_digest(*inputs, swot=result.swot, profile=profile),
        "gtm": build_digest(*inputs, swot=result.swot, mvp=result.mvp, profile=profile),
    }


def analysis_prompt(result: PipelineResult, profile: str) -> str:
    candidates = list(result.competitor_candidates)
    evidence = competitor_agent.competitor_evidence(result.search, result.competitor_search, candidates)
    context = competitor_agent.market_context_for_competitors(result.market)
    return competitor_agent.build_analysis_prompt(result.idea, context, candidates, evidence, profile=profile)


def market_prompt(result: PipelineResult, profile: str) -> str:
    evidence = market_size.market_evidence(result.search, result.market_search, result.idea)
    return market_agent.build_user_prompt(result.idea, evidence, profile=profile)


def has(text: str, flag: str) -> bool:
    return all(keyword in text for keyword in KEYWORDS[flag])


def position(text: str, flag: str) -> int:
    return text.index(RULE_TEXT[flag])


def test_the_prompt_profiles_and_flags_are_as_planned() -> None:
    assert config.PROMPT_PROFILES == ("v1", "v2") and config.DEFAULT_PROMPT_PROFILE == "v1"
    assert prompt_profile.FLAGS["v1"] == frozenset()
    assert prompt_profile.FLAGS["v2"] == frozenset({"P-1", "P-2", "P-4", "P-5", "P-6", "M-1"})
    assert "P-3" not in prompt_profile.FLAGS["v2"] and "P-3" not in RULE_TEXT


def test_an_unknown_prompt_profile_falls_back_to_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    for raw, expected in (("v2", "v2"), ("v1", "v1"), ("v3", "v1"), ("V2", "v1"), ("", "v1")):
        monkeypatch.setenv("PROMPT_PROFILE", raw)
        assert config.get_settings().prompt_profile == expected
        assert prompt_profile.active_profile() == expected


def test_the_env_example_documents_the_v2_prompt_profile() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "# PROMPT_PROFILE=v1" in text.splitlines()
    assert "PROMPT_PROFILE is v1 (today's prompts) or v2" in text


def test_every_rule_holds_its_keyword_group() -> None:
    for flag, keywords in KEYWORDS.items():
        assert all(keyword in RULE_TEXT[flag] for keyword in keywords), flag


def test_the_v2_market_prompt_states_the_source_and_length_rules_before_the_facts(synthetic: PipelineResult) -> None:
    v1, v2 = market_prompt(synthetic, "v1"), market_prompt(synthetic, "v2")
    assert v1 == market_prompt(synthetic, "v1") and not any(text in v1 for text in RULE_TEXT.values())
    assert has(v2, SOURCE_RULES) and has(v2, FIELD_LENGTHS)
    assert not has(v2, FEATURE_WORDING) and not has(v2, SPECIFIC_POINTS)
    assert v2.index(RULES_HEADING) < position(v2, SOURCE_RULES) < position(v2, FIELD_LENGTHS) < v2.index("<idea>")
    assert v2.index("<idea>") < v2.index("<evidence>")
    assert v2.replace("\n".join([RULES_HEADING, RULE_TEXT[SOURCE_RULES], RULE_TEXT[FIELD_LENGTHS], ""]) + "\n", "") == v1


def test_the_v2_competitor_analysis_prompt_adds_the_feature_wording_rule(synthetic: PipelineResult) -> None:
    v1, v2 = analysis_prompt(synthetic, "v1"), analysis_prompt(synthetic, "v2")
    assert not any(text in v1 for text in RULE_TEXT.values())
    assert has(v2, SOURCE_RULES) and has(v2, FIELD_LENGTHS) and has(v2, FEATURE_WORDING)
    assert not has(v2, SPECIFIC_POINTS)
    assert position(v2, SOURCE_RULES) < position(v2, FIELD_LENGTHS) < position(v2, FEATURE_WORDING) < v2.index("<idea>")
    added = [RULES_HEADING, RULE_TEXT[SOURCE_RULES], RULE_TEXT[FIELD_LENGTHS], RULE_TEXT[FEATURE_WORDING], ""]
    assert v2.replace("\n".join(added) + "\n", "") == v1


def test_the_candidate_prompt_and_every_system_prompt_stay_as_in_v1(synthetic: PipelineResult) -> None:
    items = build_evidence(synthetic.search)
    assert competitor_agent.build_candidate_prompt(synthetic.idea, None, items, profile="v2") == (
        competitor_agent.build_candidate_prompt(synthetic.idea, None, items)
    )
    for name, builder in STRATEGY_BUILDERS.items():
        system_v2, _ = builder(digests(synthetic, "v2")[name], profile="v2")
        system_v1, _ = builder(digests(synthetic)[name])
        assert system_v2 == system_v1, name


def test_the_v2_extraction_prompt_states_the_length_rule_before_the_submission() -> None:
    for name in IDEA_NAMES:
        v1 = extraction_agent.build_user_prompt(submission(name))
        v2 = extraction_agent.build_user_prompt(submission(name), profile="v2")
        assert has(v2, FIELD_LENGTHS) and not has(v2, SOURCE_RULES) and not has(v1, FIELD_LENGTHS)
        assert position(v2, FIELD_LENGTHS) < v2.index("<submission>")
        assert v2.replace("\n".join([RULES_HEADING, RULE_TEXT[FIELD_LENGTHS], ""]) + "\n", "") == v1


@pytest.mark.parametrize("name", list(STRATEGY_BUILDERS))
def test_v2_strategy_prompts_put_the_length_rule_before_the_facts_and_the_self_check_last(
    synthetic: PipelineResult, name: str
) -> None:
    builder = STRATEGY_BUILDERS[name]
    _, v1 = builder(digests(synthetic)[name])
    _, v2 = builder(digests(synthetic)[name], profile="v2")
    assert has(v2, FIELD_LENGTHS) and has(v2, SPECIFIC_POINTS)
    assert not has(v2, SOURCE_RULES) and not has(v2, FEATURE_WORDING)
    assert position(v2, FIELD_LENGTHS) < v2.index(DIGEST_OPEN) < v2.index(DIGEST_CLOSE) < position(v2, SPECIFIC_POINTS)
    assert v2.endswith(RULE_TEXT[SPECIFIC_POINTS])
    assert v2.index(builder.__globals__["SCHEMA_TEXT"]) < position(v2, SPECIFIC_POINTS)
    restored = v2.replace("\n".join([RULES_HEADING, RULE_TEXT[FIELD_LENGTHS], ""]) + "\n", "")
    assert restored.removesuffix("\n\n" + RULE_TEXT[SPECIFIC_POINTS]) == v1


def test_v2_prompts_stay_within_the_length_budget(synthetic: PipelineResult) -> None:
    pairs = [(market_prompt(synthetic, "v1"), market_prompt(synthetic, "v2")),
             (analysis_prompt(synthetic, "v1"), analysis_prompt(synthetic, "v2"))]
    pairs += [(extraction_agent.build_user_prompt(submission(name)),
               extraction_agent.build_user_prompt(submission(name), profile="v2")) for name in IDEA_NAMES]
    for name, builder in STRATEGY_BUILDERS.items():
        pairs.append(("".join(builder(digests(synthetic)[name])), "".join(builder(digests(synthetic, "v2")[name], profile="v2"))))
    for v1, v2 in pairs:
        assert 0 < len(v2) - len(v1) <= EXTRA_CHARS_MAX


def test_the_v1_digest_keeps_duplicate_facts_and_v2_drops_them_with_stable_refs(synthetic: PipelineResult) -> None:
    demand = synthetic.market.market_demand
    doubled = synthetic.market.model_copy(update={"market_demand": demand.model_copy(
        update={"demand_evidence": [*demand.demand_evidence, demand.demand_evidence[0]]}
    )})
    inputs = (synthetic.idea, synthetic.constraints, doubled, synthetic.competitors)
    v1 = build_digest(*inputs, max_chars=100_000)
    v2 = build_digest(*inputs, max_chars=100_000, profile="v2")
    texts = [fact.text for fact in v1.facts]
    duplicates = [fact for index, fact in enumerate(v1.facts) if fact.text in texts[:index]]

    assert duplicates and len(v2.facts) == len(v1.facts) - len(duplicates)
    assert [fact for fact in v1.facts if fact not in duplicates] == list(v2.facts)
    assert v2.refs < v1.refs and len({fact.text.casefold() for fact in v2.facts}) == len(v2.facts)
    assert build_digest(*inputs, max_chars=100_000, profile="v1") == v1


def test_distinct_facts_ignores_case_and_spacing_and_keeps_the_first() -> None:
    facts = build_facts(load_result(SYNTHETIC).idea)
    first = facts[0]
    copy = first.__class__(ref="IDEA.99", kind=first.kind, text=f"  {first.text.upper()} ", basis=first.basis)
    assert distinct_facts([first, copy, *facts[1:]]) == facts
    assert distinct_facts(facts) == facts


def test_v2_drops_duplicates_before_it_trims_to_the_digest_limit(synthetic: PipelineResult) -> None:
    demand = synthetic.market.market_demand
    doubled = synthetic.market.model_copy(update={"market_demand": demand.model_copy(
        update={"demand_evidence": demand.demand_evidence * 4}
    )})
    inputs = (synthetic.idea, synthetic.constraints, doubled, synthetic.competitors)
    full = build_digest(*inputs, max_chars=100_000, profile="v2")
    limit = len(full.text)
    assert build_digest(*inputs, max_chars=limit, profile="v2").dropped == ()
    assert build_digest(*inputs, max_chars=limit).dropped != ()


def test_the_agents_send_the_active_profile_and_record_v2_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, str]] = []

    class Gemini:
        replies = [LLM_REPLY_OK, market_reply(), *competitor_replies()]

        def __call__(self, **kwargs: Any) -> "Gemini":
            return self

        @property
        def models(self) -> "Gemini":
            return self

        def generate_content(self, **kwargs: Any) -> Any:
            sent.append((kwargs["config"].system_instruction, kwargs["contents"]))
            return SimpleNamespace(text=self.replies[len(sent) - 1])

        def close(self) -> None:
            pass

    import orchestrator

    monkeypatch.setattr(orchestrator, "run_web_search", lambda *args, **kwargs: PIPELINE_SEARCH)
    monkeypatch.setattr(market_size, "run_queries", lambda *args, **kwargs: NO_MARKET_SIZE_RESULTS)
    monkeypatch.setattr(competitor_agent, "run_queries", lambda *args, **kwargs: COMPETITOR_TARGETED)
    monkeypatch.setattr(llm_client.genai, "Client", Gemini())
    monkeypatch.setattr(llm_client, "time", SimpleNamespace(sleep=lambda seconds: None))
    monkeypatch.setenv("PROMPT_PROFILE", "v2")
    result = run_pipeline(PIPELINE_SUBMISSION, FULL_STAGES)

    assert result.status in ("complete", "partial") and len(sent) == 4
    extraction, market, candidates, analysis = (user for _, user in sent)
    assert has(extraction, FIELD_LENGTHS) and not has(extraction, SOURCE_RULES)
    assert has(market, SOURCE_RULES) and has(market, FIELD_LENGTHS) and not has(market, FEATURE_WORDING)
    assert not any(text in candidates for text in RULE_TEXT.values())
    assert has(analysis, SOURCE_RULES) and has(analysis, FEATURE_WORDING)
    assert [system for system, _ in sent] == [
        extraction_agent.SYSTEM_PROMPT, market_agent.SYSTEM_PROMPT, competitor_agent.SYSTEM_CANDIDATES,
        competitor_agent.SYSTEM_ANALYSIS,
    ]
    assert result.versions.prompt_profile == "v2" and result.versions.query_profile == "v1"
    assert result.versions.prompt_versions == {
        "extraction": "extraction-v2", "market": "market-v2", "competitors": "competitors-v2",
    }


@pytest.mark.parametrize("profile", ["v1", "v2"])
def test_each_strategy_agent_builds_its_digest_and_prompt_with_the_active_profile(
    monkeypatch: pytest.MonkeyPatch, synthetic: PipelineResult, profile: str
) -> None:
    monkeypatch.setenv("PROMPT_PROFILE", profile)
    expected = digests(synthetic, profile)
    calls = {
        "swot": (swot_risk_agent, lambda: swot_risk_agent.analyse_swot(
            synthetic.idea, synthetic.constraints, synthetic.market, synthetic.competitors)),
        "mvp": (mvp_agent, lambda: mvp_agent.recommend_mvp(
            synthetic.idea, synthetic.constraints, synthetic.market, synthetic.competitors, synthetic.swot)),
        "gtm": (gtm_agent, lambda: gtm_agent.plan_go_to_market(
            synthetic.idea, synthetic.constraints, synthetic.market, synthetic.competitors, synthetic.swot, synthetic.mvp)),
    }
    for name, (module, call) in calls.items():
        sent: list[tuple[str, str]] = []

        def capture(system: str, user: str, *args: Any, **kwargs: Any) -> Any:
            sent.append((system, user))
            raise Stop

        monkeypatch.setattr(module, "call_structured", capture)
        with pytest.raises(Stop):
            call()
        assert sent == [STRATEGY_BUILDERS[name](expected[name], profile=profile)], name
        assert has(sent[0][1], SPECIFIC_POINTS) is (profile == "v2")


def test_the_competitor_agent_passes_the_active_profile_to_its_prompt_and_its_checks(
    monkeypatch: pytest.MonkeyPatch, synthetic: PipelineResult
) -> None:
    seen: dict[str, Any] = {}

    def guards(*args: Any, profile: str = "v1", **kwargs: Any) -> Any:
        seen["guards"] = profile
        raise Stop

    def capture(system: str, user: str, *args: Any, **kwargs: Any) -> Any:
        seen["user"] = user
        return SimpleNamespace()

    monkeypatch.setenv("PROMPT_PROFILE", "v2")
    monkeypatch.setattr(competitor_agent, "find_candidates", lambda *args: (list(synthetic.competitor_candidates), []))
    monkeypatch.setattr(competitor_agent, "search_competitors", lambda queries: (synthetic.competitor_search, []))
    monkeypatch.setattr(competitor_agent, "call_structured", capture)
    monkeypatch.setattr(competitor_agent, "_apply_guards", guards)
    with pytest.raises(Stop):
        competitor_agent.analyse_competitors(synthetic.idea, synthetic.search)
    assert seen["guards"] == "v2" and has(seen["user"], FEATURE_WORDING)
    assert MATRIX_CONSISTENCY in prompt_profile.FLAGS["v2"] and DISTINCT_FACTS in prompt_profile.FLAGS["v2"]


def test_a_v2_seven_stage_run_records_every_v2_prompt_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMPT_PROFILE", "v2")
    use_full_pipeline(monkeypatch)
    use_fake_strategy(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_STAGES, constraints=StrategyConstraints(team_size=2))

    assert result.versions.prompt_profile == "v2"
    assert result.versions.prompt_versions == {
        "extraction": "extraction-v2", "market": "market-v2", "competitors": "competitors-v2",
        "swot": "swot-v2", "mvp": "mvp-v2", "gtm": "gtm-v2",
    }


def test_the_extraction_version_names_both_profiles() -> None:
    assert extraction_agent.prompt_version() == "extraction-v1"
    assert extraction_agent.prompt_version("v1", "v2") == "extraction-v2"
    assert extraction_agent.prompt_version("v2", "v1") == "extraction-v1+search-terms"
    assert extraction_agent.prompt_version("v2", "v2") == "extraction-v2+search-terms"
    assert prompt_profile.prompt_version("market-v1", "v9") == "market-v1"

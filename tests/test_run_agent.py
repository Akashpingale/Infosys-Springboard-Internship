"""Dev script scripts/run_agent.py (KIRO_PROMPT_M2.md Section 6). Fakes only: no network."""

import json
from pathlib import Path

import pytest

from agents import market_opportunity_agent as market_agent
from agents import market_size
from models.schemas import ExtractedIdea
from scripts import run_agent
from tests.conftest import FAKE_ENV
from tests.fakes import VALID_EXTRACTION, make_sequence
from tests.m2_fakes import M2_SETTINGS, MARKET_SEARCH, MARKET_SIZE_SEARCH, market_reply
from utils.errors import LLMAPIError, SearchAPIError

IDEA_FILE = Path(__file__).resolve().parent.parent / "data" / "test_ideas" / "agritech.json"
IDEA = ExtractedIdea(**VALID_EXTRACTION)
SECRETS = ("test-llm-key", "test-tavily-key")


@pytest.fixture(autouse=True)
def default_m2_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in M2_SETTINGS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def targeted_search(monkeypatch: pytest.MonkeyPatch):
    """The agent's own market-size searches, which would otherwise call Tavily."""
    fake = make_sequence(MARKET_SIZE_SEARCH)
    monkeypatch.setattr(market_size, "run_queries", fake)
    return fake


@pytest.fixture
def fake_pipeline(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace extraction and web search, which would otherwise call the real services."""
    calls = {"extract": 0, "search": 0}

    def fake_extract(submission: object) -> ExtractedIdea:
        calls["extract"] += 1
        return IDEA

    def fake_search(idea: object) -> object:
        calls["search"] += 1
        return MARKET_SEARCH

    monkeypatch.setattr(run_agent, "extract_idea", fake_extract)
    monkeypatch.setattr(run_agent, "run_web_search", fake_search)
    return calls


def test_market_run_prints_the_result_and_a_clean_integrity_check(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, fake_pipeline: dict
) -> None:
    monkeypatch.setattr(market_agent, "generate_json", make_sequence(market_reply()))
    assert run_agent.main(["market", "--idea", str(IDEA_FILE)]) == 0
    out = capsys.readouterr().out
    assert '"industry_overview"' in out and '"market_size"' in out
    assert "Warnings:\n- none" in out
    assert out.rstrip().endswith("Integrity check: no violations")
    assert fake_pipeline == {"extract": 1, "search": 1}
    assert not any(secret in out for secret in SECRETS)


@pytest.mark.parametrize("missing", ["LLM_API_KEY", "LLM_MODEL", "TAVILY_API_KEY"])
def test_missing_keys_stop_before_any_call(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, fake_pipeline: dict, missing: str
) -> None:
    monkeypatch.delenv(missing)
    assert run_agent.main(["market", "--idea", str(IDEA_FILE)]) == 1
    out = capsys.readouterr().out
    assert "needs real keys" in out
    assert fake_pipeline == {"extract": 0, "search": 0}
    assert not any(secret in out for secret in SECRETS)


def test_a_stage_error_is_reported_plainly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, fake_pipeline: dict
) -> None:
    monkeypatch.setattr(
        market_agent, "generate_json", make_sequence(LLMAPIError("The AI service is busy right now."))
    )
    assert run_agent.main(["market", "--idea", str(IDEA_FILE)]) == 1
    out = capsys.readouterr().out
    assert "Stopped: The AI service is busy right now. (llm_api_error)" in out
    assert "Traceback" not in out


def test_an_unreadable_idea_file_is_reported(
    capsys: pytest.CaptureFixture, tmp_path: Path, fake_pipeline: dict
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert run_agent.main(["market", "--idea", str(bad)]) == 1
    assert "Could not read" in capsys.readouterr().out
    assert fake_pipeline == {"extract": 0, "search": 0}


# --- Task 1 scope fixes: audit output and targeted searches --------------------------------


def test_the_output_shows_the_idea_searches_and_evidence_for_auditing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, fake_pipeline: dict, targeted_search
) -> None:
    monkeypatch.setattr(market_agent, "generate_json", make_sequence(market_reply()))
    assert run_agent.main(["market", "--idea", str(IDEA_FILE)]) == 0
    out = capsys.readouterr().out
    expected = [
        "Idea:\n- Title: CropScan: AI crop disease detection",
        "- Target customers: Small farmers in India; Agricultural cooperatives",
        "Standard searches:",
        *(f"- {section.label}: {section.query} ({len(section.results)} results)" for section in MARKET_SEARCH.sections),
        "Targeted market-size searches:",
        *(f"- {section.label}: {section.query} ({len(section.results)} results)" for section in MARKET_SIZE_SEARCH.sections),
        "Evidence used by the market agent:",
        "[S0] Search engine summary\n    URL: none (search summary, not a source)",
        "[S1] Crop AI market report\n    URL: https://reports.example/crop-ai-market",
        "    Text: The AI crop disease detection market was valued at USD 1.8 billion in 2025.",
        "[S5] India crop disease detection market\n    URL: https://research.example/india-crop-disease-detection",
        "    Section: Market size for this idea",
    ]
    for text in expected:
        assert text in out, text
    assert out.index("Evidence used by the market agent:") < out.index("Result:") < out.index('"industry_overview"')
    assert out.rstrip().endswith("Integrity check: no violations")
    assert not any(value in out for value in FAKE_ENV.values()), "no key or setting value is printed"
    assert len(targeted_search.calls) == 1


def test_a_failed_targeted_search_is_shown_and_the_run_still_completes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, fake_pipeline: dict
) -> None:
    failure = SearchAPIError("Web search could not be completed. Please try again.")
    monkeypatch.setattr(market_size, "run_queries", make_sequence(failure))
    monkeypatch.setattr(market_agent, "generate_json", make_sequence(market_reply()))
    assert run_agent.main(["market", "--idea", str(IDEA_FILE)]) == 0
    out = capsys.readouterr().out
    assert f"Targeted market-size searches:\n{run_agent.NO_TARGETED_SEARCH}" in out
    assert "- Market opportunity: the targeted market-size searches failed" in out
    assert "[S5]" not in out
    assert out.rstrip().endswith("Integrity check: no violations")


def test_a_stage_error_still_shows_what_the_agent_saw(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, fake_pipeline: dict
) -> None:
    monkeypatch.setattr(market_agent, "generate_json", make_sequence(LLMAPIError("The AI service is busy right now.")))
    assert run_agent.main(["market", "--idea", str(IDEA_FILE)]) == 1
    out = capsys.readouterr().out
    assert out.index("Idea:") < out.index("Evidence used by the market agent:") < out.index("Stopped:")
    assert '"industry_overview"' not in out and "Traceback" not in out


@pytest.mark.parametrize("missing", ["LLM_API_KEY", "TAVILY_API_KEY"])
def test_missing_keys_never_start_the_targeted_searches(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, fake_pipeline: dict, targeted_search, missing: str
) -> None:
    monkeypatch.delenv(missing)
    assert run_agent.main(["market", "--idea", str(IDEA_FILE)]) == 1
    assert targeted_search.calls == []
    assert "Idea:" not in capsys.readouterr().out


# --- Task 2: competitor mode ---------------------------------------------------------------------


@pytest.fixture
def competitor_pipeline(monkeypatch: pytest.MonkeyPatch, fake_pipeline: dict) -> dict:
    """The competitor mode with fakes: the standard search names competitors, and Phase B returns
    the five targeted results."""
    from agents import competitor_analysis_agent as competitor_agent
    from tests.m2_fakes import COMPETITOR_SEARCH, COMPETITOR_TARGETED

    monkeypatch.setattr(run_agent, "run_web_search", lambda idea: COMPETITOR_SEARCH)
    targeted = make_sequence(COMPETITOR_TARGETED)
    monkeypatch.setattr(competitor_agent, "run_queries", targeted)
    return {"agent": competitor_agent, "targeted": targeted}


def use_competitor_llm(monkeypatch: pytest.MonkeyPatch, pipeline: dict, *replies: object):
    from tests.m2_fakes import ANALYSIS_REPLY, CANDIDATE_REPLY

    fake = make_sequence(*(replies or (json.dumps(CANDIDATE_REPLY), json.dumps(ANALYSIS_REPLY))))
    monkeypatch.setattr(pipeline["agent"], "generate_json", fake)
    return fake


def test_competitor_mode_prints_the_audit_the_result_and_a_clean_integrity_check(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, competitor_pipeline: dict
) -> None:
    use_competitor_llm(monkeypatch, competitor_pipeline)
    assert run_agent.main(["competitor", "--idea", str(IDEA_FILE)]) == 0
    out = capsys.readouterr().out
    expected = [
        "Idea:\n- Title: CropScan: AI crop disease detection",
        "Market context: none (not requested)",
        "Standard searches:",
        "Phase A candidates kept:\n- Plantix (direct, sourced): https://plantix.example/about, https://directory.example/agrio/alternatives",
        "Phase A candidates dropped:\n- 'LeafDoc': the founder did not name it in the submission",
        "- 'AgroGhost': it is not named in its cited sources",
        "Targeted competitor searches:\n- Competitor: LeafDoc: Competitor: LeafDoc query (1 results)",
        "- Competitor: CropSense: Competitor: CropSense query (No live results found for this query.)",
        "Evidence used by the competitor agent:\n[S0] Search engine summary",
        "[S5] Plantix pricing\n    URL: https://plantix.example/pricing",
        '"comparison"',
        '"feature_coverage"',
    ]
    for text in expected:
        assert text in out, text
    assert out.index("Evidence used by the competitor agent:") < out.index("Result:") < out.index('"competitors"')
    assert out.rstrip().endswith("Integrity check: no violations")
    assert not any(value in out for value in FAKE_ENV.values())
    assert len(competitor_pipeline["targeted"].calls) == 1


def test_competitor_mode_with_market_context(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, competitor_pipeline: dict
) -> None:
    monkeypatch.setattr(market_agent, "generate_json", make_sequence(market_reply()))
    fake = use_competitor_llm(monkeypatch, competitor_pipeline)
    assert run_agent.main(["competitor", "--idea", str(IDEA_FILE), "--with-market"]) == 0
    out = capsys.readouterr().out
    assert "Market context: from the market agent (AI crop disease detection)" in out
    assert "Market context: category: AI crop disease detection" in fake.calls[1][0][1]


def test_a_failed_market_stage_leaves_the_competitor_run_going(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, competitor_pipeline: dict
) -> None:
    monkeypatch.setattr(market_agent, "generate_json", make_sequence(LLMAPIError("The AI service is busy right now.")))
    fake = use_competitor_llm(monkeypatch, competitor_pipeline)
    assert run_agent.main(["competitor", "--idea", str(IDEA_FILE), "--with-market"]) == 0
    out = capsys.readouterr().out
    assert "Market context: none; the market agent stopped (The AI service is busy right now.)" in out
    assert "Market context: none" in fake.calls[1][0][1]


def test_a_competitor_stage_error_is_reported_after_the_audit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, competitor_pipeline: dict
) -> None:
    from tests.m2_fakes import CANDIDATE_REPLY

    use_competitor_llm(monkeypatch, competitor_pipeline, json.dumps(CANDIDATE_REPLY), LLMAPIError("The AI service is busy right now."))
    assert run_agent.main(["competitor", "--idea", str(IDEA_FILE)]) == 1
    out = capsys.readouterr().out
    assert out.index("Standard searches:") < out.index("Stopped: The AI service is busy right now. (llm_api_error)")
    assert '"competitors"' not in out and "Traceback" not in out


@pytest.mark.parametrize("missing", ["LLM_API_KEY", "TAVILY_API_KEY"])
def test_competitor_mode_stops_before_any_call_without_keys(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, competitor_pipeline: dict, missing: str
) -> None:
    fake = use_competitor_llm(monkeypatch, competitor_pipeline)
    monkeypatch.delenv(missing)
    assert run_agent.main(["competitor", "--idea", str(IDEA_FILE)]) == 1
    assert fake.calls == [] and competitor_pipeline["targeted"].calls == []
    assert "needs real keys" in capsys.readouterr().out

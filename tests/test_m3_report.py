import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents import gtm_agent, mvp_agent, swot_risk_agent
from app import create_app
from frontend import analysis_views as views
from models.chat import ChatMessage, ChatParagraph
from models.schemas import PipelineResult, StrategyConstraints
from orchestrator import STRATEGY_STAGES, run_pipeline
from tests.fakes import make_sequence
from tests.pipeline_fakes import PIPELINE_SUBMISSION, use_full_pipeline
from tests.run_fakes import store_in
from tests.test_m3_gtm_agent import draft as gtm_draft
from tests.test_m3_mvp_agent import draft as mvp_draft
from tests.test_m3_swot_agent import draft as swot_draft
from utils.chat_store import ChatStore
from utils.errors import LLMAPIError
from utils.run_manager import RunManager

CONSTRAINTS = StrategyConstraints(team_size=2, months_to_mvp=3, budget_level="small", launch_region="Maharashtra")
STRATEGY_FIELDS = ("swot", "mvp", "gtm", "constraints")
TIMINGS = {
    "extraction": 1.0,
    "search": 2.0,
    "market_opportunity": 3.0,
    "competitor_analysis": 4.0,
    "swot_risk": 5.0,
    "mvp_recommendation": 6.0,
    "go_to_market": 7.0,
    "total": 28.0,
}
SNAPSHOT_SHA256 = "3f7005f18b5e38b96329968efa49f021cd3393af114030436eb7981f80aefe33"
STRATEGY_HEADINGS = ("## SWOT and risks", "## MVP recommendation", "## Go-to-market plan")
SECRETS = ("test-llm-key", "test-tavily-key")
QUESTION = "Synthetic advisor question about cooperative pricing"
ANSWER = "Synthetic advisor answer that must stay out of the report."
FOLLOW_UP = "Synthetic advisor follow-up question"


def use_replies(monkeypatch: pytest.MonkeyPatch, swot=None, mvp=None, gtm=None) -> None:
    for module, outcome, data in ((swot_risk_agent, swot, swot_draft), (mvp_agent, mvp, mvp_draft), (gtm_agent, gtm, gtm_draft)):
        monkeypatch.setattr(module, "generate_json", make_sequence(outcome if outcome is not None else json.dumps(data())))


def strategy_result(
    monkeypatch: pytest.MonkeyPatch, constraints: StrategyConstraints | None = CONSTRAINTS, pipeline: dict | None = None,
    **replies,
) -> PipelineResult:
    use_full_pipeline(monkeypatch, **(pipeline or {}))
    use_replies(monkeypatch, **replies)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_STAGES, constraints=constraints)
    return result.model_copy(update={"timings": TIMINGS})


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def headings(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("#")]


def without_strategy(result: PipelineResult) -> PipelineResult:
    return result.model_copy(update=dict.fromkeys(STRATEGY_FIELDS))


@pytest.fixture
def complete(monkeypatch: pytest.MonkeyPatch) -> PipelineResult:
    result = strategy_result(monkeypatch)
    assert result.status == "complete" and result.swot and result.mvp and result.gtm, "the fixture must be complete"
    return result


def test_the_default_report_is_byte_identical_to_the_stored_snapshot(complete: PipelineResult) -> None:
    assert sha256(views.report_markdown(complete)) == SNAPSHOT_SHA256


def test_the_default_report_never_carries_strategy(complete: PipelineResult) -> None:
    text = views.report_markdown(complete)

    assert text == views.report_markdown(without_strategy(complete))
    assert not set(STRATEGY_HEADINGS) & set(headings(text))
    assert complete.gtm.positioning.statement not in text


def test_the_full_report_without_strategy_is_unchanged(complete: PipelineResult) -> None:
    plain = without_strategy(complete)

    assert sha256(views.report_markdown(plain, full=True)) == SNAPSHOT_SHA256
    assert not views.has_strategy(plain)


def test_the_full_report_appends_the_strategy_sections_after_the_analyses(complete: PipelineResult) -> None:
    text = views.report_markdown(complete, full=True)
    before = views.report_markdown(without_strategy(complete), full=True)

    assert text.startswith(before + "\n")
    found = headings(text)
    assert [heading for heading in found if heading in STRATEGY_HEADINGS] == list(STRATEGY_HEADINGS)
    assert found.index("## SWOT and risks") > found.index("## Competitors")
    assert len([line for line in found if line.startswith("# ")]) == 1, "still exactly one top-level heading"
    assert views.report_file_name(complete) == views.REPORT_FILE_NAME


def test_the_swot_section_covers_every_item_and_risk(complete: PipelineResult) -> None:
    text = views.report_markdown(complete, full=True)
    swot = complete.swot

    for name, title in views.SWOT_QUADRANTS:
        assert f"**{title}**" in text
        for item in getattr(swot, name):
            assert f"- {views.strategy_line(item.text, item.basis, item.sources)}" in text
    assert f"### Risks ({len(swot.risks)})" in headings(text)
    for risk in swot.risks:
        assert f"**{risk.title}** ({risk.severity.capitalize()} severity, {risk.category})" in text
        assert f"- Mitigation: {risk.mitigation}" in text
        assert f"- Early warning sign: {risk.early_warning_signal}" in text
    assert views.MSG_STRATEGY_CAVEAT in text
    assert "(AI interpretation: competitors S1, competitors S5, market S2)" in text, "inherited sources by analysis"


def test_the_mvp_section_keeps_the_backend_order_tiers_and_capacity(complete: PipelineResult) -> None:
    text = views.report_markdown(complete, full=True)
    mvp = complete.mvp
    first = [feature for feature in sorted(mvp.features, key=lambda feature: feature.rank) if feature.tier == "mvp"]
    later = [feature for feature in sorted(mvp.features, key=lambda feature: feature.rank) if feature.tier == "later"]

    assert f"Planned {mvp.planned_person_months:g} of {mvp.capacity_person_months:g} person-months." in text
    assert f"### In the first release ({len(first)})" in headings(text) and f"### Later ({len(later)})" in headings(text)
    positions = [text.index(f"**Rank {feature.rank}: {feature.name}**") for feature in [*first, *later]]
    assert positions == sorted(positions)
    assert text.index("### Later") > positions[len(first) - 1]
    for feature_id, reason in mvp.deferred_reasons.items():
        assert f"- Why later: {reason}" in text, feature_id
    assert "- Team size: 2\n" in text and "(assumed)" not in text
    for metric in mvp.success_metrics:
        assert metric.name in text


def test_the_go_to_market_section_covers_positioning_channels_and_the_launch_plan(complete: PipelineResult) -> None:
    text = views.report_markdown(complete, full=True)
    gtm = complete.gtm

    assert gtm.positioning.statement in text
    assert f"- Differentiator ({gtm.positioning.differentiator_status.capitalize()}): {gtm.positioning.differentiator}" in text
    starts = [channel for channel in gtm.channels if channel.start_here]
    assert len(starts) == 1 and f"**Rank 1: {starts[0].name}** (Start here)" in text
    assert text.count("(Start here)") == 1
    for channel in gtm.channels:
        assert f"- First experiment: {channel.first_experiment}" in text
    for tactic in gtm.early_customers:
        assert f"**{tactic.tactic}**" in text
    for number, phase in enumerate(gtm.launch_phases, 1):
        assert f"{number}. **{phase.name}**: {phase.goal}" in text
    assert "| Audience | Message | Proof needed |" in text
    names = {feature.id: feature.name for feature in complete.mvp.features}
    linked = [names[feature_id] for feature_id in starts[0].uses_feature_ids]
    assert linked and f"- Uses the features: {'; '.join(linked)}" in text, "feature ids become feature names"


def test_no_backend_id_or_key_reaches_the_strategy_sections(complete: PipelineResult) -> None:
    text = views.report_markdown(complete, full=True)
    strategy = text[text.index("## SWOT and risks"):]

    for marker in ("RSK.", "MKT.", "CMP.", "IDEA.", "MVP.", "CON.", "based_on", "mitigates_risk_ids", "Traceback"):
        assert marker not in strategy, marker
    for feature in complete.mvp.features:
        assert f"{feature.id}:" not in strategy and f"({feature.id})" not in strategy
    assert all(secret not in text for secret in SECRETS)


def test_assumed_resources_are_marked_in_the_report(monkeypatch: pytest.MonkeyPatch) -> None:
    result = strategy_result(monkeypatch, constraints=None)
    text = views.report_markdown(result, full=True)

    assert "- Team size: 2 (assumed)" in text
    assert "- Months to the first release: 3 (assumed)" in text


def test_a_budget_conflict_is_noted_on_the_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    result = strategy_result(monkeypatch, constraints=CONSTRAINTS.model_copy(update={"budget_level": "bootstrapped"}))
    text = views.report_markdown(result, full=True)

    conflicts = [channel for channel in result.gtm.channels if channel.budget_conflict]
    assert conflicts and text.count(f"- Budget: {views.MSG_BUDGET_CONFLICT}") == len(conflicts)


def test_a_missing_strategy_part_is_stated(monkeypatch: pytest.MonkeyPatch) -> None:
    result = strategy_result(monkeypatch, mvp=LLMAPIError())
    text = views.report_markdown(result, full=True)

    assert result.mvp is None and result.swot is not None and result.gtm is not None
    assert [heading for heading in headings(text) if heading in STRATEGY_HEADINGS] == list(STRATEGY_HEADINGS)
    assert views.MSG_NO_MVP in text and "### In the first release" not in text
    assert result.gtm.positioning.statement in text and "- Uses the features:" not in text


def test_the_report_route_exports_strategy_and_never_the_advisor_conversation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_full_pipeline(monkeypatch)
    use_replies(monkeypatch)
    store = store_in(tmp_path)
    manager = RunManager(store)
    app = create_app()
    app.state.run_manager = manager
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            body = {"submission": PIPELINE_SUBMISSION.model_dump(mode="json"), "include_strategy": True,
                    "constraints": CONSTRAINTS.model_dump(mode="json")}
            response = client.post("/api/runs", json=body)
            assert response.status_code == 202, response.text
            run_id = response.json()["run_id"]
            assert manager.wait(run_id, 10)
            created = "2026-01-01T00:00:00Z"
            assert ChatStore(store).append(
                run_id,
                ChatMessage(id="m1", role="user", created_at=created, text=QUESTION),
                ChatMessage(id="m2", role="assistant", created_at=created, follow_ups=[FOLLOW_UP],
                            paragraphs=[ChatParagraph(text=ANSWER, basis="ai_interpretation")]),
            )

            response = client.get(f"/api/runs/{run_id}/report.md")
    finally:
        manager.shutdown()

    assert response.status_code == 200
    text = response.text
    assert [heading for heading in headings(text) if heading in STRATEGY_HEADINGS] == list(STRATEGY_HEADINGS)
    for chat_text in (QUESTION, ANSWER, FOLLOW_UP):
        assert chat_text not in text
    assert not [heading for heading in headings(text) if "advisor" in heading.lower() or "conversation" in heading.lower()]

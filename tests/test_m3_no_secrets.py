import json
import logging
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents import advisor_agent
from app import create_app
from models.schemas import PipelineResult
from orchestrator import STAGE_GTM, STAGE_MVP, STAGE_SWOT, STRATEGY_ONLY_STAGES, run_pipeline
from scripts import check_m3_contracts
from scripts.check_m3_contracts import check_result
from tests.fakes import make_sequence
from tests.m3_fakes import CONSTRAINTS, FIELDS, full_result, use_capturing_providers
from tests.pipeline_fakes import PIPELINE_SUBMISSION, use_full_pipeline
from tests.test_m3_gtm_agent import draft as gtm_draft
from tests.test_m3_gtm_agent import use_mvp_reply, use_swot_reply
from tests.test_m3_gtm_agent import use_reply as use_gtm_reply
from tests.test_m3_mvp_agent import as_reply
from tests.test_m3_mvp_agent import draft as mvp_draft
from tests.test_m3_swot_agent import draft as swot_draft
from utils import llm_client, run_manager
from utils.run_store import REDACTED

RUNS = "/api/runs"
BODY = {"submission": PIPELINE_SUBMISSION.model_dump(mode="json")}
WITH_STRATEGY = {**BODY, "include_strategy": True, "constraints": CONSTRAINTS.model_dump(mode="json")}
LLM_KEY = "-".join(("planted", "llm", "value", "0451"))
SEARCH_KEY = "-".join(("planted", "search", "value", "0452"))
GROQ_KEY = "-".join(("planted", "groq", "value", "0453"))
PLANTED = (LLM_KEY, SEARCH_KEY, GROQ_KEY)
SHAPED = "gs" + "k_" + "Q7w8E9r0T1y2U3i4O5p6A7s8"
QUESTION = "How big is the TAM for this idea?"
ADVISOR_REPLY = json.dumps({
    "in_scope": True,
    "paragraphs": [{"text": "Start by talking to the first farmers who would use it.", "basis": "assumption", "refs": []}],
    "follow_ups": [],
    "needs_more_evidence": False,
})
DRAFTS = {STAGE_SWOT: swot_draft, STAGE_MVP: mvp_draft, STAGE_GTM: gtm_draft}
REPLIES = {STAGE_SWOT: use_swot_reply, STAGE_MVP: use_mvp_reply, STAGE_GTM: use_gtm_reply}
M2_RESULTS = Path(__file__).resolve().parent.parent / "docs" / "test_runs_m2"


@pytest.fixture
def planted(monkeypatch: pytest.MonkeyPatch) -> tuple[str, ...]:
    for name, value in zip(("LLM_API_KEY", "TAVILY_API_KEY", "GROQ_API_KEY"), PLANTED):
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("CHAT_COOLDOWN_S", "0")
    return PLANTED


@pytest.fixture
def client(planted: tuple[str, ...], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RUNS_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.setattr(run_manager, "_default", None)
    manager = run_manager.default_manager()
    assert manager._store.path.resolve() == (tmp_path / "runs.db").resolve()
    app = create_app()
    app.state.run_manager = manager
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    run_manager.shutdown_default_manager()


def use_replies(monkeypatch: pytest.MonkeyPatch, **planted_in: str) -> list:
    fakes = []
    for stage, draft in DRAFTS.items():
        data = draft()
        if stage in planted_in:
            data["summary"] = f"Keep {planted_in[stage]} for later."
        fakes.append(REPLIES[stage](monkeypatch, as_reply(data)))
    return fakes


def use_advisor(monkeypatch: pytest.MonkeyPatch):
    fake = make_sequence(ADVISOR_REPLY)
    monkeypatch.setattr(advisor_agent, "generate_json", fake)
    return fake


def start(client: TestClient, body: dict, responses: list[str]) -> str:
    response = client.post(RUNS, json=body)
    assert response.status_code == 202, response.text
    responses.append(response.text)
    return response.json()["run_id"]


def wait_for(client: TestClient, run_id: str) -> dict:
    assert client.app.state.run_manager.wait(run_id, 10), "the run did not finish in time"
    return client.get(f"{RUNS}/{run_id}").json()


def outside(client: TestClient, run_id: str, tmp_path: Path, responses: list[str], logs: str) -> dict[str, str]:
    texts = {
        "detail": client.get(f"{RUNS}/{run_id}").text,
        "list": client.get(RUNS).text,
        "report": client.get(f"{RUNS}/{run_id}/report.md").text,
        "meta": client.get("/api/meta").text,
        "responses": "\n".join(responses),
        "logs": logs,
    }
    for path in sorted(tmp_path.glob("runs.db*")):
        texts[path.name] = path.read_bytes().decode("utf-8", "ignore")
    return texts


def found_in(texts: dict[str, str], values: tuple[str, ...]) -> list[str]:
    return [name for name, text in texts.items() if any(value in text for value in values)]


def prompts(*fakes) -> str:
    return "\n".join(repr(call) for fake in fakes for call in fake.calls)


def test_the_store_redacts_every_configured_key(client: TestClient) -> None:
    assert set(client.app.state.run_manager._store._secrets) == set(PLANTED)


def test_configured_keys_never_reach_a_prompt_a_response_a_row_or_a_log(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    pipeline = use_full_pipeline(monkeypatch)
    strategy = use_replies(monkeypatch)
    advisor = use_advisor(monkeypatch)
    responses: list[str] = []

    run_id = start(client, WITH_STRATEGY, responses)
    body = wait_for(client, run_id)
    assert body["result"]["status"] == "complete" and all(body["result"][name] for name in ("swot", "mvp", "gtm"))
    asked = client.post(f"{RUNS}/{run_id}/chat", json={"message": QUESTION})
    assert asked.status_code == 200, asked.text
    responses += [asked.text, client.get(f"{RUNS}/{run_id}/chat").text]
    again = client.post(f"{RUNS}/{run_id}/strategy", json={"mode": "all"})
    assert again.status_code == 202, again.text
    responses.append(again.text)
    assert wait_for(client, run_id)["result"]["status"] == "complete"

    texts = outside(client, run_id, tmp_path, responses, caplog.text)
    texts["prompts"] = prompts(pipeline.extraction_llm, pipeline.market_llm, pipeline.competitor_llm, *strategy, advisor)
    assert all(len(fake.calls) == 2 for fake in strategy) and len(advisor.calls) == 1
    assert found_in(texts, PLANTED) == []


@pytest.mark.parametrize("stage", [STAGE_SWOT, STAGE_MVP, STAGE_GTM])
@pytest.mark.parametrize("kind", ["configured", "shaped"])
def test_a_key_in_a_strategy_reply_fails_only_that_stage_and_goes_nowhere(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    stage: str,
    kind: str,
) -> None:
    caplog.set_level(logging.DEBUG)
    value = LLM_KEY if kind == "configured" else SHAPED
    use_full_pipeline(monkeypatch)
    use_replies(monkeypatch, **{stage: value})
    responses: list[str] = []

    run_id = start(client, WITH_STRATEGY, responses)
    result = wait_for(client, run_id)["result"]

    assert result["status"] == "partial"
    assert [(error["stage"], error["code"]) for error in result["errors"]] == [(stage, "internal_error")]
    assert result[FIELDS[stage]] is None
    assert all(result[FIELDS[other]] is not None for other in DRAFTS if other != stage)
    assert found_in(outside(client, run_id, tmp_path, responses, caplog.text), (value, *PLANTED)) == []


def test_a_key_in_a_strategy_reply_for_a_saved_run_goes_nowhere(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    use_full_pipeline(monkeypatch)
    responses: list[str] = []
    run_id = start(client, BODY, responses)
    assert wait_for(client, run_id)["result"]["gtm"] is None
    use_replies(monkeypatch, **{STAGE_GTM: SHAPED})

    response = client.post(f"{RUNS}/{run_id}/strategy", json={"mode": "missing"})
    assert response.status_code == 202, response.text
    responses.append(response.text)
    result = wait_for(client, run_id)["result"]

    assert result["status"] == "partial" and result["swot"] is not None and result["mvp"] is not None
    assert result["gtm"] is None and [error["stage"] for error in result["errors"]] == [STAGE_GTM]
    assert found_in(outside(client, run_id, tmp_path, responses, caplog.text), (SHAPED, *PLANTED)) == []


def test_a_provider_error_that_quotes_the_keys_is_neither_logged_nor_returned(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    use_full_pipeline(monkeypatch)
    error = llm_client.genai_errors.ClientError(
        400, {"error": {"code": 400, "message": f"API key {LLM_KEY} is not valid; {SEARCH_KEY} and {GROQ_KEY} were sent.",
                        "status": "INVALID_ARGUMENT"}}
    )
    use_capturing_providers(monkeypatch, error)
    monkeypatch.setenv("GROQ_API_KEY", GROQ_KEY)
    use_mvp_reply(monkeypatch, as_reply(mvp_draft()))
    use_gtm_reply(monkeypatch, as_reply(gtm_draft()))
    responses: list[str] = []

    run_id = start(client, WITH_STRATEGY, responses)
    result = wait_for(client, run_id)["result"]

    assert result["swot"] is None and [error["stage"] for error in result["errors"]] == [STAGE_SWOT]
    assert "LLM call failed" in caplog.text
    assert found_in(outside(client, run_id, tmp_path, responses, caplog.text), PLANTED) == []


def test_a_key_typed_into_a_question_stays_out_of_the_rows_the_logs_and_the_saved_thread(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    use_full_pipeline(monkeypatch)
    use_advisor(monkeypatch)
    responses: list[str] = []
    run_id = start(client, BODY, responses)
    wait_for(client, run_id)

    asked = client.post(f"{RUNS}/{run_id}/chat", json={"message": f"Is {LLM_KEY} safe to share?"})
    assert asked.status_code == 200, asked.text
    responses.append(asked.text)
    thread = client.get(f"{RUNS}/{run_id}/chat")
    responses.append(thread.text)

    assert thread.json()["messages"][0]["text"] == f"Is {REDACTED} safe to share?"
    assert found_in(outside(client, run_id, tmp_path, responses, caplog.text), PLANTED) == []


@pytest.fixture
def synthetic(monkeypatch: pytest.MonkeyPatch) -> PipelineResult:
    bare, _ = full_result(monkeypatch)
    use_replies(monkeypatch)
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=bare, constraints=CONSTRAINTS)
    assert result.status == "complete" and result.swot and result.mvp and result.gtm
    return result


def saved(tmp_path: Path, data: dict | str, name: str = "result.json") -> Path:
    path = tmp_path / name
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def test_the_contract_script_passes_on_the_synthetic_result(
    synthetic: PipelineResult, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    path = saved(tmp_path, synthetic.model_dump(mode="json"))

    assert check_result(synthetic) == []
    assert check_m3_contracts.main([str(path)]) == 0
    assert capsys.readouterr().out.splitlines() == [f"{path}: checked swot, mvp, gtm; no violations", "All 1 file(s) pass."]


def test_saved_milestone_2_results_have_no_strategy_to_break(capsys: pytest.CaptureFixture) -> None:
    paths = [M2_RESULTS / name for name in ("agritech.json", "fintech_cashflow.json", "foodtech_surplus.json")]

    assert check_m3_contracts.main([str(path) for path in paths]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == [f"{path}: checked nothing; not present swot, mvp, gtm; no violations" for path in paths] + ["All 3 file(s) pass."]


def _no_ref_item(data: dict) -> dict:
    return next(item for name in ("strengths", "weaknesses", "opportunities", "threats") for item in data["swot"][name]
                if not item["based_on"])


def _market_only_item(data: dict) -> dict:
    return next(item for item in data["swot"]["opportunities"] if all(ref.startswith("MKT.") for ref in item["based_on"]))


def _later_feature(data: dict) -> dict:
    return next(feature for feature in data["mvp"]["features"] if feature["tier"] == "later")


def _rename_founder_features(data: dict) -> None:
    for number, feature in enumerate(data["mvp"]["features"]):
        if feature["origin"] == "founder_listed":
            feature.update(name=f"Unrelated tool {number}", origin="suggested")


def _swap_ranks(data: dict) -> None:
    first, second = data["mvp"]["features"][:2]
    first["rank"], second["rank"] = second["rank"], first["rank"]


def _suggested_as_founder(data: dict) -> None:
    next(feature for feature in data["mvp"]["features"] if feature["origin"] != "founder_listed")["origin"] = "founder_listed"


def _first_channel(data: dict) -> dict:
    return data["gtm"]["channels"][0]


def _flip_budget(data: dict) -> None:
    channel = next(channel for channel in data["gtm"]["channels"] if channel["cost_level"] == "high")
    channel["budget_conflict"] = not channel["budget_conflict"]


PLANTED_VIOLATIONS: dict[str, tuple[str, Callable[[dict], object]]] = {
    "unknown_ref": ("ref_unknown", lambda data: data["swot"]["strengths"][0]["based_on"].append("MKT.999")),
    "interpretation_without_refs": ("basis_inconsistent", lambda data: _no_ref_item(data).update(basis="ai_interpretation")),
    "founder_basis_without_founder_ref": ("basis_inconsistent", lambda data: _market_only_item(data).update(basis="user_provided")),
    "foreign_source": ("sources_mismatch", lambda data: data["swot"]["opportunities"][0]["sources"].append(
        {"analysis": "market", "id": "S999"})),
    "unsupported_figure": ("figure_unsupported", lambda data: data["swot"]["strengths"][0].update(
        text="Farmers lose $4,321 a season to late diagnosis.")),
    "overclaim": ("overclaim", lambda data: data["swot"]["threats"][0].update(text="Success is guaranteed for this app.")),
    "duplicate": ("duplicate", lambda data: data["swot"]["threats"].append({**data["swot"]["threats"][0], "id": "SW99"})),
    "repeated_id": ("id_repeated", lambda data: data["swot"]["risks"][1].update(id=data["swot"]["risks"][0]["id"])),
    "wrong_severity": ("severity", lambda data: data["swot"]["risks"][0].update(severity="low")),
    "risks_out_of_order": ("risk_order", lambda data: data["swot"]["risks"].reverse()),
    "wrong_coverage": ("coverage", lambda data: data["swot"]["risk_category_coverage"].update(market=9)),
    "wrong_gaps": ("coverage", lambda data: data["swot"].update(coverage_gaps=["financial"])),
    "too_few_without_warning": ("shortfall_unexplained", lambda data: data["swot"].update(
        strengths=data["swot"]["strengths"][:2])),
    "too_little_swot": ("count", lambda data: data["swot"].update(
        strengths=data["swot"]["strengths"][:1], weaknesses=[], opportunities=[], threats=data["swot"]["threats"][:2])),
    "wrong_score": ("score", lambda data: data["mvp"]["features"][0].update(score=1.0)),
    "swapped_ranks": ("rank", _swap_ranks),
    "wrong_tier": ("tier", lambda data: _later_feature(data).update(tier="mvp")),
    "wrong_capacity": ("capacity", lambda data: data["mvp"].update(capacity_person_months=9.0)),
    "wrong_over_capacity": ("capacity", lambda data: data["mvp"].update(over_capacity=not data["mvp"]["over_capacity"])),
    "missing_deferred_reason": ("deferred_reasons", lambda data: data["mvp"].update(deferred_reasons={})),
    "founder_feature_dropped": ("founder_feature_missing", _rename_founder_features),
    "invented_founder_origin": ("origin", _suggested_as_founder),
    "unknown_risk_link": ("risk_link", lambda data: data["mvp"]["features"][0].update(mitigates_risk_ids=["R99"])),
    "metric_basis": ("basis_inconsistent", lambda data: data["mvp"]["success_metrics"][0].update(basis="ai_interpretation")),
    "metric_target_figure": ("figure_unsupported", lambda data: data["mvp"]["success_metrics"][0].update(
        suggested_target="Save farmers $9,876 each")),
    "rewritten_statement": ("statement", lambda data: data["gtm"]["positioning"].update(statement="For everyone, a better app.")),
    "other_segment": ("segment", lambda data: data["gtm"]["positioning"].update(target_segment="Urban gardeners")),
    "supported_gap": ("differentiator_status", lambda data: data["gtm"]["positioning"].update(differentiator_status="supported")),
    "channels_out_of_order": ("channel_rank", lambda data: data["gtm"]["channels"].reverse()),
    "two_start_here": ("channel_rank", lambda data: data["gtm"]["channels"][1].update(start_here=True)),
    "budget_flag": ("budget_conflict", _flip_budget),
    "unknown_feature_link": ("feature_link", lambda data: _first_channel(data).update(uses_feature_ids=["F99"])),
    "too_few_channels": ("count", lambda data: data["gtm"].update(channels=data["gtm"]["channels"][:2])),
    "phases_out_of_order": ("launch_phases", lambda data: data["gtm"]["launch_phases"].reverse()),
    "phase_missing_without_warning": ("shortfall_unexplained", lambda data: data["gtm"].update(
        launch_phases=data["gtm"]["launch_phases"][:2])),
    "summary_overclaim": ("overclaim", lambda data: data["gtm"].update(summary="This plan can't fail.")),
}


@pytest.mark.parametrize("case", list(PLANTED_VIOLATIONS))
def test_the_contract_script_flags_a_planted_violation(
    synthetic: PipelineResult, tmp_path: Path, capsys: pytest.CaptureFixture, case: str
) -> None:
    rule, plant = PLANTED_VIOLATIONS[case]
    data = synthetic.model_dump(mode="json")
    plant(data)
    path = saved(tmp_path, data)

    assert rule in {violation.rule for violation in check_result(PipelineResult.model_validate(data))}
    assert check_m3_contracts.main([str(path)]) == 1
    out = capsys.readouterr().out
    assert f": {rule}: " in out and out.splitlines()[-1] == "1 of 1 file(s) break a rule."


def test_the_contract_script_flags_secrets_without_printing_them(
    synthetic: PipelineResult, tmp_path: Path, capsys: pytest.CaptureFixture, planted: tuple[str, ...]
) -> None:
    data = synthetic.model_dump(mode="json")
    data["gtm"]["summary"] = f"Keep {LLM_KEY} for later."
    data["mvp"]["limitations"].append(f"Found {SHAPED} on a page.")
    data["swot"]["strengths"][0]["based_on"].append(SHAPED)
    path = saved(tmp_path, data)

    assert check_m3_contracts.main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "gtm: secret: contains configured key value" in out
    assert "mvp: secret: contains key-shaped text (Groq)" in out
    assert "swot: secret: contains key-shaped text (Groq)" in out
    assert "cites a malformed ref, which is not a finding of this result" in out
    assert not any(value in out for value in (SHAPED, *planted))


def test_a_strategy_item_labelled_sourced_fails_the_schema(
    synthetic: PipelineResult, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    data = synthetic.model_dump(mode="json")
    data["swot"]["strengths"][0]["basis"] = "sourced"

    assert check_m3_contracts.main([str(saved(tmp_path, data))]) == 1
    out = capsys.readouterr().out
    assert "not checked; 1 violation(s)" in out and "swot.strengths.0.basis: schema: literal_error" in out


def test_a_file_that_is_not_json_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = saved(tmp_path, "{not json", "broken.json")

    assert check_m3_contracts.main([str(path)]) == 1
    assert "file: unreadable: could not be read as JSON (JSONDecodeError)" in capsys.readouterr().out

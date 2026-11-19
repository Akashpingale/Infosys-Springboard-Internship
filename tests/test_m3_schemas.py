import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

import config
from app import create_app
from config import get_settings
from models.api import RunDetail, RunRequest, StrategyRequest
from models.chat import ChatMessage, ChatReply, ChatRequest, ChatThread
from models.schemas import (
    GtmResult,
    MvpResult,
    PipelineResult,
    RiskItem,
    StrategyConstraints,
    SwotRiskResult,
)
from models.strategy_drafts import STRATEGY_DRAFT_MODELS, AdvisorDraft, MvpDraft, SwotRiskDraft
from tests.test_m2_groq_structured import nullable_fields, schema_nodes
from utils import groq_client
from utils.errors import (
    AppError,
    ChatBusyError,
    ChatCooldownError,
    ChatLimitError,
    ChatMessageInvalidError,
    ChatUnavailableError,
    RunNotFinishedError,
    StrategyAlreadyCompleteError,
    StrategyNotReadyError,
)

ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = ROOT / ".env.example"
STORED_RUNS = ROOT / "data" / "runs.db"
NEW_RESULT_FIELDS = ("swot", "mvp", "gtm", "constraints")
SECRET_PATTERN = re.compile(r"tvly-[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}")

M3_SETTINGS = {
    "STRATEGY_TIME_LIMIT_S": ("strategy_time_limit_s", 150.0, "200", 200.0, ["soon", "0", "29", "901", "nan"]),
    "STRATEGY_DIGEST_MAX_CHARS": ("strategy_digest_max_chars", 24000, "8000", 8000, ["many", "2.5", "3999", "100001"]),
    "CHAT_MAX_USER_TURNS": ("chat_max_user_turns", 25, "10", 10, ["ten", "0", "-1", "101"]),
    "CHAT_MAX_MESSAGE_CHARS": ("chat_max_message_chars", 1000, "500", 500, ["long", "99", "4001"]),
    "CHAT_HISTORY_TURNS": ("chat_history_turns", 6, "3", 3, ["few", "0", "21"]),
    "CHAT_CONTEXT_MAX_CHARS": ("chat_context_max_chars", 30000, "20000", 20000, ["big", "3999", "120001"]),
    "CHAT_MAX_CONCURRENT": ("chat_max_concurrent", 2, "1", 1, ["two", "0", "9"]),
    "CHAT_COOLDOWN_S": ("chat_cooldown_s", 2.0, "0.5", 0.5, ["wait", "-1", "61"]),
}

FIXTURE_RESULTS = sorted(
    path for path in (ROOT / "docs").glob("test_runs*/*.json") if path.name != "run_summary.json"
)
FIXTURE_RUNS = [ROOT / "web" / "src" / "test" / "liveAgritech.json", ROOT / "web" / "src" / "test" / "liveFintech.json"]


@pytest.fixture(autouse=True)
def default_m3_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in M3_SETTINGS:
        monkeypatch.delenv(name, raising=False)


def source(analysis: str = "market", id: str = "S1") -> dict:
    return {"analysis": analysis, "id": id}


def swot_item(n: int, **changes: Any) -> dict:
    item = {
        "id": f"SW{n}",
        "text": "The idea targets a stated pain point.",
        "why_it_matters": "It gives a reason to switch.",
        "basis": "ai_interpretation",
        "based_on": ["MKT.1"],
        "sources": [source()],
    }
    return {**item, **changes}


def risk(n: int = 1, **changes: Any) -> dict:
    item = {
        "id": f"R{n}",
        "category": "market",
        "title": "Slow adoption",
        "description": "Buyers may keep their current tools.",
        "likelihood": "medium",
        "impact": "high",
        "severity": "high",
        "mitigation": "Run a pilot with five users.",
        "early_warning_signal": "Few pilot sign-ups.",
        "confidence": "low",
        "basis": "ai_interpretation",
        "based_on": ["MKT.9"],
        "sources": [source()],
    }
    return {**item, **changes}


def swot_result(**changes: Any) -> dict:
    result = {
        "summary": "A plausible idea with adoption risk.",
        "strengths": [swot_item(1)],
        "weaknesses": [swot_item(2, basis="assumption", based_on=[], sources=[])],
        "opportunities": [swot_item(3)],
        "threats": [swot_item(4, sources=[source("competitors", "S2")])],
        "risks": [risk()],
        "risk_category_coverage": {"market": 1},
        "coverage_gaps": ["business", "technical", "financial", "operational"],
        "limitations": ["No pricing data."],
        "quality": {
            "inputs_used": ["idea", "market", "competitors"],
            "inputs_missing": [],
            "constraints_provided": [],
            "constraints_assumed": ["team_size", "months_to_mvp"],
            "basis_counts": {"ai_interpretation": 4, "assumption": 1},
            "grounded_share": 0.8,
            "warnings_count": 0,
        },
        "warnings": [],
    }
    return {**result, **changes}


def feature(n: int = 1, **changes: Any) -> dict:
    item = {
        "id": f"F{n}",
        "name": "Offline price lookup",
        "description": "Shows recent prices without a connection.",
        "user_problem": "Farmers lack price information.",
        "origin": "founder_listed",
        "essential": True,
        "customer_need": 5,
        "differentiation": 3,
        "feasibility": 4,
        "effort": "M",
        "score": 4.1,
        "tier": "mvp",
        "rank": 1,
        "rationale": "Closes the main gap.",
        "mitigates_risk_ids": ["R1"],
        "basis": "ai_interpretation",
        "based_on": ["MKT.2"],
        "sources": [source()],
    }
    return {**item, **changes}


def mvp_result(**changes: Any) -> dict:
    result = {
        "summary": "A small first release.",
        "features": [feature()],
        "capacity_person_months": 3.6,
        "planned_person_months": 1.0,
        "over_capacity": False,
        "constraints_used": {"team_size": 2, "months_to_mvp": 3},
        "deferred_reasons": {},
        "success_metrics": [
            {"name": "Weekly active users", "how_to_measure": "Count logins.", "suggested_target": None, "basis": "assumption"}
        ],
        "limitations": [],
        "warnings": [],
    }
    return {**result, **changes}


def channel(n: int = 1, **changes: Any) -> dict:
    item = {
        "id": f"CH{n}",
        "name": "Agri-input retailers",
        "kind": "partnership",
        "role": "both",
        "fit_rationale": "Farmers already visit them.",
        "audience_fit": 4,
        "cost_level": "low",
        "speed_to_first_result": "weeks",
        "first_experiment": "Leave flyers at three shops.",
        "success_signal": "Ten sign-ups in a month.",
        "priority": n,
        "start_here": n == 1,
        "uses_feature_ids": ["F1"],
        "addresses_risk_ids": ["R1"],
        "basis": "ai_interpretation",
        "based_on": ["MKT.4"],
        "sources": [source()],
    }
    return {**item, **changes}


def gtm_result(**changes: Any) -> dict:
    result = {
        "summary": "Start with retailers.",
        "positioning": {
            "target_segment": "Smallholder farmers",
            "for_whom": "smallholder farmers",
            "problem": "lack timely prices",
            "category": "price app",
            "key_benefit": "shows prices offline",
            "alternative": "word of mouth",
            "differentiator": "works without a connection",
            "statement": "For smallholder farmers who lack timely prices, the app is a price app.",
            "differentiator_status": "hypothesis",
            "basis": "ai_interpretation",
            "based_on": ["CMP.3"],
            "sources": [source("competitors", "S4")],
        },
        "channels": [channel(1), channel(2), channel(3)],
        "early_customers": [
            {
                "tactic": "Village demos",
                "where_to_find_them": "Weekly markets",
                "offer": "Free first season",
                "how_to_measure": "Demo to sign-up rate",
                "basis": "assumption",
                "based_on": [],
                "sources": [],
            }
        ],
        "launch_phases": [
            {"name": name, "goal": "Reach first users.", "actions": ["Recruit pilots.", "Collect feedback."]}
            for name in ("Before launch", "Launch", "First 90 days")
        ],
        "key_messages": [{"audience": "Farmers", "message": "Know today's price.", "proof_needed": "Pilot data"}],
        "limitations": [],
        "warnings": [],
    }
    return {**result, **changes}


def full_result() -> dict:
    return {
        "status": "complete",
        "swot": swot_result(),
        "mvp": mvp_result(),
        "gtm": gtm_result(),
        "constraints": {"team_size": 2, "budget_level": "bootstrapped"},
    }


def submission() -> dict:
    return {
        "idea_description": "A mobile app that tells small farmers the best local crop prices every day.",
        "industry": "Agriculture / AgriTech",
        "target_customers": "Small farmers",
    }


# --- settings -------------------------------------------------------------------------------------


def test_new_settings_have_the_planned_defaults() -> None:
    settings = get_settings()
    assert {name: getattr(settings, spec[0]) for name, spec in M3_SETTINGS.items()} == {
        name: spec[1] for name, spec in M3_SETTINGS.items()
    }


@pytest.mark.parametrize("name", list(M3_SETTINGS))
def test_a_value_inside_the_bounds_is_read(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    attribute, _, raw, expected, _ = M3_SETTINGS[name]
    monkeypatch.setenv(name, raw)
    assert getattr(get_settings(), attribute) == expected


@pytest.mark.parametrize(
    ("name", "raw"), [(name, raw) for name, spec in M3_SETTINGS.items() for raw in spec[4]]
)
def test_a_bad_or_out_of_bounds_value_falls_back_to_the_default(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, name: str, raw: str
) -> None:
    attribute, default, *_ = M3_SETTINGS[name]
    monkeypatch.setenv(name, raw)
    assert getattr(get_settings(), attribute) == default
    assert name in caplog.text


def test_the_bounds_are_inclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAT_MAX_USER_TURNS", str(config.CHAT_MAX_USER_TURNS_RANGE[1]))
    monkeypatch.setenv("CHAT_COOLDOWN_S", str(config.CHAT_COOLDOWN_S_RANGE[0]))
    settings = get_settings()
    assert (settings.chat_max_user_turns, settings.chat_cooldown_s) == (100, 0.0)


def test_env_example_documents_every_new_setting_with_its_default() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for name, spec in M3_SETTINGS.items():
        default = spec[1]
        shown = str(int(default)) if isinstance(default, float) and default.is_integer() else str(default)
        assert re.search(rf"^#? ?{name}={shown}\s*$", text, re.MULTILINE), name
    assert not SECRET_PATTERN.search(text)


# --- errors ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error_class", "code", "status", "message"),
    [
        (RunNotFinishedError, "run_not_finished", 409, "This validation is still running."),
        (StrategyNotReadyError, "strategy_not_ready", 409, "There is no market or competitor analysis to build a strategy on."),
        (StrategyAlreadyCompleteError, "strategy_already_complete", 409, "This validation already has a strategy."),
        (ChatUnavailableError, "chat_unavailable", 409, "Questions open once the validation has finished."),
        (ChatLimitError, "chat_limit_reached", 409, "This conversation is full. Clear it to start again."),
        (ChatBusyError, "chat_busy", 409, "Wait for the current answer first."),
        (ChatCooldownError, "chat_cooldown", 429, "Wait a moment before the next question."),
        (ChatMessageInvalidError, "chat_message_invalid", 422, "Write a question of up to 1000 characters."),
    ],
)
def test_each_new_error_has_its_code_status_and_plain_message(
    error_class: type[AppError], code: str, status: int, message: str
) -> None:
    error = error_class()
    assert isinstance(error, AppError)
    assert (error.code, error.status_code, error.user_message) == (code, status, message)


def test_the_message_error_names_the_configured_limit() -> None:
    assert ChatMessageInvalidError(500).user_message == "Write a question of up to 500 characters."


def test_a_new_error_reaches_the_user_in_the_one_error_shape() -> None:
    app = create_app()

    @app.get("/raise-cooldown")
    def raise_cooldown() -> None:
        raise ChatCooldownError()

    response = TestClient(app, raise_server_exceptions=False).get("/raise-cooldown")
    assert response.status_code == 429
    assert response.json() == {"error": {"code": "chat_cooldown", "message": "Wait a moment before the next question."}}


# --- constraints and requests ---------------------------------------------------------------------


def test_constraints_accept_every_documented_value_and_default_to_null() -> None:
    assert StrategyConstraints().model_dump() == dict.fromkeys(
        ("team_size", "months_to_mvp", "budget_level", "technical_skill", "launch_region")
    )
    full = StrategyConstraints(team_size=10, months_to_mvp=1, budget_level="funded", technical_skill="non_technical", launch_region="Kenya")
    assert (full.team_size, full.months_to_mvp, full.launch_region) == (10, 1, "Kenya")


@pytest.mark.parametrize(
    "bad",
    [
        {"team_size": 0},
        {"team_size": 11},
        {"months_to_mvp": 0},
        {"months_to_mvp": 13},
        {"budget_level": "large"},
        {"technical_skill": "expert"},
        {"launch_region": "x" * 61},
        {"team": 2},
    ],
)
def test_constraints_outside_the_limits_or_unknown_are_rejected(bad: dict) -> None:
    with pytest.raises(ValidationError):
        StrategyConstraints.model_validate(bad)


def test_the_launch_region_loses_control_characters() -> None:
    assert StrategyConstraints(launch_region="East\x00 Africa\n").launch_region == "East Africa"
    assert StrategyConstraints(launch_region=" \t ").launch_region is None


def test_an_existing_run_request_is_unchanged_and_the_new_fields_default_off() -> None:
    request = RunRequest.model_validate({"submission": submission()})
    assert request.include_strategy is False and request.constraints is None
    with pytest.raises(ValidationError):
        RunRequest.model_validate({"submission": submission(), "unknown": 1})


def test_a_run_request_accepts_strategy_and_constraints() -> None:
    request = RunRequest.model_validate(
        {"submission": submission(), "include_strategy": True, "constraints": {"team_size": 3}}
    )
    assert request.include_strategy is True and request.constraints == StrategyConstraints(team_size=3)
    with pytest.raises(ValidationError):
        RunRequest.model_validate({"submission": submission(), "constraints": {"team_size": 99}})


def test_a_strategy_request_defaults_to_missing_and_rejects_other_modes() -> None:
    assert StrategyRequest().mode == "missing" and StrategyRequest().constraints is None
    assert StrategyRequest(mode="all").mode == "all"
    for bad in ({"mode": "some"}, {"extra": True}):
        with pytest.raises(ValidationError):
            StrategyRequest.model_validate(bad)


# --- stored strategy models -----------------------------------------------------------------------


def test_a_result_with_all_strategy_parts_validates_and_round_trips() -> None:
    result = PipelineResult.model_validate(full_result())
    assert isinstance(result.swot, SwotRiskResult) and isinstance(result.mvp, MvpResult) and isinstance(result.gtm, GtmResult)
    assert PipelineResult.model_validate_json(result.model_dump_json()) == result


def test_the_new_result_fields_default_to_null() -> None:
    result = PipelineResult(status="complete")
    assert all(getattr(result, name) is None for name in NEW_RESULT_FIELDS)
    assert all(result.model_dump()[name] is None for name in NEW_RESULT_FIELDS)


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (SwotRiskResult, swot_result(strengths=[swot_item(1, basis="sourced")])),
        (SwotRiskResult, swot_result(strengths=[swot_item(n) for n in range(6)])),
        (SwotRiskResult, swot_result(strengths=[swot_item(1, text="x" * 281)])),
        (SwotRiskResult, swot_result(risks=[risk(n) for n in range(11)])),
        (SwotRiskResult, swot_result(coverage_gaps=["legal"])),
        (SwotRiskResult, swot_result(quality={"grounded_share": 1.5})),
        (RiskItem, risk(confidence="high")),
        (RiskItem, risk(severity="critical")),
        (RiskItem, risk(category="legal")),
        (RiskItem, risk(sources=[source("search", "S1")])),
        (MvpResult, mvp_result(features=[feature(customer_need=6)])),
        (MvpResult, mvp_result(features=[feature(score=5.5)])),
        (MvpResult, mvp_result(features=[feature(effort="XL")])),
        (MvpResult, mvp_result(features=[feature(tier="now")])),
        (MvpResult, mvp_result(features=[feature(n) for n in range(13)])),
        (MvpResult, mvp_result(constraints_used={"team_size": 20})),
        (GtmResult, gtm_result(channels=[channel(n) for n in range(1, 8)])),
        (GtmResult, gtm_result(channels=[channel(1, audience_fit=0)])),
        (GtmResult, gtm_result(channels=[channel(1, cost_level="free")])),
        (GtmResult, gtm_result(launch_phases=[{"name": "Growth", "goal": "Grow.", "actions": []}])),
        (GtmResult, gtm_result(positioning={**gtm_result()["positioning"], "differentiator_status": "proven"})),
        (GtmResult, gtm_result(positioning={**gtm_result()["positioning"], "for_whom": "x" * 161})),
    ],
)
def test_stored_strategy_models_enforce_their_limits(model: type[BaseModel], data: dict) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)


# --- drafts ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("model", STRATEGY_DRAFT_MODELS, ids=lambda model: model.__name__)
def test_every_draft_schema_has_a_strict_form_for_groq(model: type[BaseModel]) -> None:
    assert groq_client.response_format(model)["type"] == "json_schema"
    schema = groq_client.strict_schema(model)
    for node in schema_nodes(schema):
        assert set(node) <= groq_client.STRICT_KEYWORDS
    assert nullable_fields(schema) == nullable_fields(model.model_json_schema())


def test_the_draft_shapes_of_the_plan_parse() -> None:
    swot = SwotRiskDraft.model_validate(
        {
            "strengths": [{"text": "...", "why_it_matters": "...", "basis": "ai_interpretation", "based_on": ["MKT.4", "CMP.2"]}],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
            "risks": [
                {
                    "category": "market",
                    "title": "...",
                    "description": "...",
                    "likelihood": "medium",
                    "impact": "high",
                    "mitigation": "...",
                    "early_warning_signal": "...",
                    "confidence": "high",
                    "basis": "ai_interpretation",
                    "based_on": ["MKT.9"],
                }
            ],
            "summary": "...",
            "limitations": ["..."],
        }
    )
    assert swot.risks[0].confidence == "high"
    advisor = AdvisorDraft.model_validate(
        {
            "in_scope": True,
            "paragraphs": [{"text": "...", "basis": "sourced", "refs": ["RSK.1", "MKT.9"]}],
            "follow_ups": ["..."],
            "needs_more_evidence": False,
        }
    )
    assert advisor.paragraphs[0].refs == ["RSK.1", "MKT.9"]


def test_draft_ratings_are_left_for_code_to_clamp_and_strategy_drafts_never_say_sourced() -> None:
    draft = {
        "name": "Price alerts",
        "origin": "suggested",
        "customer_need": 9,
        "differentiation": 0,
        "feasibility": 3,
        "effort": "S",
        "basis": "assumption",
    }
    assert MvpDraft.model_validate({"features": [draft]}).features[0].customer_need == 9
    with pytest.raises(ValidationError):
        MvpDraft.model_validate({"features": [{**draft, "basis": "sourced"}]})


# --- chat -----------------------------------------------------------------------------------------


def test_a_question_is_trimmed_and_loses_control_characters() -> None:
    assert ChatRequest(message="  Why is\x00 this risk high?\x07\n ").message == "Why is this risk high?"
    assert ChatRequest(message="line one\nline two").message == "line one\nline two"


@pytest.mark.parametrize("bad", [{"message": ""}, {"message": " \n\t "}, {"message": "x" * 1001}, {"message": "ok", "role": "user"}])
def test_an_empty_too_long_or_unknown_question_is_rejected(bad: dict) -> None:
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(bad)


def test_the_question_limit_follows_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAT_MAX_MESSAGE_CHARS", "200")
    assert len(ChatRequest(message="x" * 200).message) == 200
    with pytest.raises(ValidationError):
        ChatRequest(message="x" * 201)


def test_a_stored_assistant_message_and_the_thread_validate() -> None:
    message = ChatMessage.model_validate(
        {
            "id": "m2",
            "role": "assistant",
            "created_at": "2026-11-08T10:00:00.000+00:00",
            "status": "ok",
            "paragraphs": [
                {"text": "...", "basis": "ai_interpretation", "sections": ["risks", "market"], "sources": [source()]}
            ],
            "follow_ups": ["..."],
        }
    )
    thread = ChatThread(messages=[message], remaining_turns=24, limits={"max_message_chars": 1000, "max_user_turns": 25})
    assert ChatReply(message=message, remaining_turns=24).message.paragraphs[0].sources[0].analysis == "market"
    assert thread.messages[0].used_sections == [] and thread.available_sections == []


@pytest.mark.parametrize(
    "changes",
    [
        {"role": "system"},
        {"status": "error"},
        {"paragraphs": [{"text": "x" * 601, "basis": "assumption"}]},
        {"paragraphs": [{"text": "...", "basis": "assumption"}] * 6},
        {"paragraphs": [{"text": "...", "basis": "user_provided"}]},
        {"follow_ups": ["a", "b", "c", "d"]},
        {"follow_ups": ["x" * 121]},
        {"used_sections": ["weather"]},
    ],
)
def test_chat_messages_enforce_their_limits(changes: dict) -> None:
    with pytest.raises(ValidationError):
        ChatMessage.model_validate({"id": "m1", "role": "user", "created_at": "now", "text": "Hi", **changes})


# --- compatibility --------------------------------------------------------------------------------


def assert_unchanged(original: dict, validated: BaseModel) -> None:
    dumped = validated.model_dump(mode="json")
    assert {key: dumped[key] for key in original} == original
    assert all(dumped[name] is None for name in NEW_RESULT_FIELDS)


@pytest.mark.parametrize("path", FIXTURE_RESULTS, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_every_saved_pipeline_result_validates_unchanged(path: Path) -> None:
    original = json.loads(path.read_text(encoding="utf-8"))
    assert_unchanged(original, PipelineResult.model_validate(original))


@pytest.mark.parametrize("path", FIXTURE_RUNS, ids=lambda path: path.name)
def test_every_saved_run_fixture_validates_unchanged(path: Path) -> None:
    original = json.loads(path.read_text(encoding="utf-8"))
    run = RunDetail.model_validate(original)
    dumped = run.model_dump(mode="json", exclude={"result"})
    assert {key: dumped[key] for key in original if key != "result"} == {key: value for key, value in original.items() if key != "result"}
    assert set(dumped) - set(original) == {"constraints", "report"}
    assert dumped["constraints"] is None
    assert_unchanged(original["result"], run.result)


def fingerprint(path: Path) -> tuple[str, int, int]:
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size, path.stat().st_mtime_ns


def test_every_result_in_a_copy_of_the_stored_runs_validates_unchanged(tmp_path: Path) -> None:
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
    for (text,) in rows:
        original = json.loads(text)
        assert_unchanged(original, PipelineResult.model_validate(original))


# --- OpenAPI and imports --------------------------------------------------------------------------


def test_the_openapi_schema_generates_with_the_new_optional_request_fields() -> None:
    schema = create_app().openapi()
    run_request = schema["components"]["schemas"]["RunRequest"]
    assert {"include_strategy", "constraints"} <= set(run_request["properties"])
    assert run_request["required"] == ["submission"]
    assert run_request["additionalProperties"] is False
    assert {"StrategyConstraints", "SwotRiskResult", "MvpResult", "GtmResult"} <= set(schema["components"]["schemas"])


@pytest.mark.parametrize("module", ["models.chat", "models.strategy_drafts", "models.api", "models.schemas", "utils.errors", "config"])
def test_each_module_imports_first_without_a_cycle(module: str) -> None:
    others = "models.schemas, models.api, models.chat, models.strategy_drafts, config, utils.errors"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", f"import {module}; import {others}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]

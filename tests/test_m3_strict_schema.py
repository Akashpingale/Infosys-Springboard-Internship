import copy
import inspect
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel

from models import strategy_drafts
from models.schemas import STRATEGY_BASES
from models.strategy_drafts import ADVISOR_BASES, STRATEGY_DRAFT_MODELS, AdvisorDraft, GtmDraft, MvpDraft, SwotRiskDraft
from tests.test_m2_groq_structured import schema_nodes
from utils import groq_client

RANGE_KEYWORDS = frozenset(
    {"minItems", "maxItems", "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "pattern"}
)

REPLIES: dict[type[BaseModel], dict[str, Any]] = {
    SwotRiskDraft: {
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
                "confidence": "low",
                "basis": "ai_interpretation",
                "based_on": ["MKT.9"],
            }
        ],
        "summary": "...",
        "limitations": ["..."],
    },
    MvpDraft: {
        "features": [
            {
                "name": "...",
                "description": "...",
                "user_problem": "...",
                "origin": "founder_listed",
                "essential": True,
                "customer_need": 5,
                "differentiation": 3,
                "feasibility": 4,
                "effort": "M",
                "rationale": "...",
                "mitigates": ["RSK.1"],
                "basis": "user_provided",
                "based_on": ["IDEA.7"],
            }
        ],
        "success_metrics": [{"name": "...", "how_to_measure": "...", "suggested_target": None, "basis": "assumption"}],
        "summary": "...",
        "limitations": [],
    },
    GtmDraft: {
        "positioning": {
            "target_segment": "...",
            "for_whom": "...",
            "problem": "...",
            "category": "...",
            "key_benefit": "...",
            "alternative": "...",
            "differentiator": "...",
            "basis": "ai_interpretation",
            "based_on": ["CMP.3"],
        },
        "channels": [
            {
                "name": "...",
                "kind": "community",
                "role": "acquisition",
                "fit_rationale": "...",
                "audience_fit": 4,
                "cost_level": "low",
                "speed_to_first_result": "weeks",
                "first_experiment": "...",
                "success_signal": "...",
                "uses_features": ["MVP.1"],
                "addresses_risks": [],
                "basis": "ai_interpretation",
                "based_on": ["MKT.2"],
            }
        ],
        "early_customers": [
            {"tactic": "...", "where_to_find_them": "...", "offer": "...", "how_to_measure": "...", "basis": "assumption", "based_on": []}
        ],
        "launch_phases": [{"name": "Before launch", "goal": "...", "actions": ["...", "..."]}],
        "key_messages": [{"audience": "...", "message": "...", "proof_needed": "..."}],
        "summary": "...",
        "limitations": [],
    },
    AdvisorDraft: {
        "in_scope": True,
        "paragraphs": [{"text": "...", "basis": "ai_interpretation", "refs": ["RSK.1", "MKT.9"]}],
        "follow_ups": ["..."],
        "needs_more_evidence": False,
    },
}


def validator(model: type[BaseModel]) -> Draft202012Validator:
    return Draft202012Validator(groq_client.strict_schema(model))


def draft_classes() -> set[str]:
    return {
        name
        for name, value in inspect.getmembers(strategy_drafts, inspect.isclass)
        if issubclass(value, BaseModel) and value is not BaseModel and value.__module__ == strategy_drafts.__name__
    }


def basis_enums(schema: dict) -> list[list[str]]:
    return [node["properties"]["basis"]["enum"] for node in schema_nodes(schema) if "basis" in node.get("properties", {})]


def test_the_draft_list_names_the_four_llm_facing_drafts() -> None:
    assert [model.__name__ for model in STRATEGY_DRAFT_MODELS] == ["SwotRiskDraft", "MvpDraft", "GtmDraft", "AdvisorDraft"]
    assert set(REPLIES) == set(STRATEGY_DRAFT_MODELS)


@pytest.mark.parametrize("model", STRATEGY_DRAFT_MODELS, ids=lambda model: model.__name__)
def test_the_groq_strict_schema_validator_accepts_the_draft_schema(model: type[BaseModel]) -> None:
    schema = groq_client.strict_schema(model)
    Draft202012Validator.check_schema(schema)
    assert schema["type"] == "object"
    for node in schema_nodes(schema):
        assert set(node) <= groq_client.STRICT_KEYWORDS, sorted(set(node) - groq_client.STRICT_KEYWORDS)
        if "properties" in node:
            assert node["required"] == list(node["properties"])
            assert node["additionalProperties"] is False
        if "$ref" in node:
            assert node == {"$ref": node["$ref"]}
            assert node["$ref"].removeprefix("#/$defs/") in schema.get("$defs", {})


def test_every_item_draft_is_reached_by_a_strict_schema() -> None:
    reached = {model.__name__ for model in STRATEGY_DRAFT_MODELS}
    for model in STRATEGY_DRAFT_MODELS:
        reached |= set(groq_client.strict_schema(model).get("$defs", {}))
    assert draft_classes() <= reached


@pytest.mark.parametrize("model", STRATEGY_DRAFT_MODELS, ids=lambda model: model.__name__)
def test_drafts_leave_counts_and_lengths_to_code_and_have_no_free_form_maps(model: type[BaseModel]) -> None:
    raw = model.model_json_schema()
    for node in schema_nodes(raw):
        assert not set(node) & RANGE_KEYWORDS, sorted(set(node) & RANGE_KEYWORDS)
        assert not isinstance(node.get("additionalProperties"), dict)
        assert "patternProperties" not in node


def test_strategy_drafts_never_offer_sourced_and_the_advisor_does() -> None:
    for model in (SwotRiskDraft, MvpDraft, GtmDraft):
        enums = basis_enums(groq_client.strict_schema(model))
        assert enums and all(sorted(enum) == sorted(STRATEGY_BASES) for enum in enums)
        assert all("sourced" not in enum for enum in enums)
    assert basis_enums(groq_client.strict_schema(AdvisorDraft)) == [list(ADVISOR_BASES)]


@pytest.mark.parametrize("model", STRATEGY_DRAFT_MODELS, ids=lambda model: model.__name__)
def test_a_complete_reply_of_the_plan_shape_fits_the_strict_schema(model: type[BaseModel]) -> None:
    complete = model.model_validate(REPLIES[model]).model_dump(mode="json")
    assert list(validator(model).iter_errors(complete)) == []


@pytest.mark.parametrize("model", STRATEGY_DRAFT_MODELS, ids=lambda model: model.__name__)
def test_the_strict_schema_rejects_extra_keys_and_missing_keys(model: type[BaseModel]) -> None:
    complete = model.model_validate(REPLIES[model]).model_dump(mode="json")
    extra = {**complete, "sources": [{"analysis": "market", "id": "S1"}]}
    assert list(validator(model).iter_errors(extra))
    missing = copy.deepcopy(complete)
    missing.pop(next(iter(missing)))
    assert list(validator(model).iter_errors(missing))


def test_the_strict_schema_rejects_values_outside_the_enums() -> None:
    reply = SwotRiskDraft.model_validate(REPLIES[SwotRiskDraft]).model_dump(mode="json")
    for path, value in ((("strengths", 0, "basis"), "sourced"), (("risks", 0, "category"), "legal"), (("risks", 0, "likelihood"), "certain")):
        broken = copy.deepcopy(reply)
        target = broken
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        assert list(validator(SwotRiskDraft).iter_errors(broken)), path

"""GET /api/meta (KIRO_UI_UPGRADE_SPEC.md Sections 10.1 and 8.1).

The limits the interface shows must be the ones models/schemas.py enforces, so a number is never
repeated by hand, and no key or key length may appear anywhere in the reply.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from models.api import MetaResponse
from models.schemas import (
    CUSTOMERS_MAX,
    CUSTOMERS_MIN,
    DETAILS_MAX,
    IDEA_MAX,
    IDEA_MIN,
    IDEA_MIN_WORDS,
    IDEA_TITLE_MAX,
    INDUSTRIES,
    INDUSTRY_MAX,
    INDUSTRY_MIN,
    KEY_FEATURES_RANGE,
    TARGET_CUSTOMERS_RANGE,
    IdeaSubmission,
)
from routes.meta_routes import APP_NAME, EXAMPLES, example_ideas
from utils.groq_client import MODEL as GROQ_MODEL
from utils.run_manager import MAX_CONCURRENT_RUNS, run_time_limit_s

META = "/api/meta"
SECRETS = ("test-llm-key", "test-tavily-key")


@pytest.fixture
def meta(client: TestClient) -> dict:
    response = client.get(META)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_reply_matches_its_model(meta: dict) -> None:
    assert MetaResponse.model_validate(meta).app_name == APP_NAME


def test_the_form_limits_are_the_ones_the_schemas_enforce(meta: dict) -> None:
    limits = meta["limits"]

    assert limits["idea_description"] == {"min_chars": IDEA_MIN, "max_chars": IDEA_MAX, "min_words": IDEA_MIN_WORDS}
    assert limits["industry"] == {"min_chars": INDUSTRY_MIN, "max_chars": INDUSTRY_MAX, "min_words": None}
    assert limits["target_customers"] == {"min_chars": CUSTOMERS_MIN, "max_chars": CUSTOMERS_MAX, "min_words": None}
    assert limits["relevant_details"] == {"min_chars": None, "max_chars": DETAILS_MAX, "min_words": None}


def test_the_review_step_limits_come_from_the_extracted_idea_model(meta: dict) -> None:
    review = meta["limits"]["extracted_idea"]

    assert review["title_max_chars"] == IDEA_TITLE_MAX
    assert review["target_customers"] == {"min_items": TARGET_CUSTOMERS_RANGE[0], "max_items": TARGET_CUSTOMERS_RANGE[1]}
    assert review["key_features"] == {"min_items": KEY_FEATURES_RANGE[0], "max_items": KEY_FEATURES_RANGE[1]}


def test_a_submission_at_the_published_limits_is_accepted_by_the_backend(meta: dict) -> None:
    """The published minimums really are usable: a submission built from them validates."""
    limits = meta["limits"]
    submission = IdeaSubmission(
        idea_description="word " * limits["idea_description"]["min_words"] + "x" * limits["idea_description"]["min_chars"],
        industry="x" * limits["industry"]["min_chars"],
        target_customers="x" * limits["target_customers"]["min_chars"],
    )
    assert submission.idea_description


def test_the_industry_list_is_the_shared_one(meta: dict) -> None:
    assert meta["industries"] == INDUSTRIES
    assert "Other" in meta["industries"]


def test_the_stage_labels_are_the_plain_ones_in_pipeline_order(meta: dict) -> None:
    assert meta["stages"] == [
        {"key": "extraction", "label": "Understanding your idea"},
        {"key": "search", "label": "Searching the web"},
        {"key": "market_opportunity", "label": "Analysing the market"},
        {"key": "competitor_analysis", "label": "Comparing competitors"},
    ]


def test_the_examples_are_the_three_task_4_ideas(meta: dict) -> None:
    assert [example["key"] for example in meta["examples"]] == [key for key, _ in EXAMPLES]
    for example in meta["examples"]:
        submission = IdeaSubmission.model_validate(example["submission"])
        assert submission.idea_description and submission.industry and example["label"]


def test_a_missing_example_file_is_left_out_rather_than_invented(tmp_path: Path) -> None:
    assert example_ideas(tmp_path) == []


def test_an_unreadable_example_file_is_left_out(tmp_path: Path) -> None:
    (tmp_path / f"{EXAMPLES[0][0]}.json").write_text("{not json", encoding="utf-8")
    (tmp_path / f"{EXAMPLES[1][0]}.json").write_text(json.dumps({"idea_description": "too short"}), encoding="utf-8")
    assert example_ideas(tmp_path) == []


def test_the_run_limits_are_the_configured_ones(meta: dict) -> None:
    limits = meta["run_limits"]

    assert limits["time_limit_s"] == run_time_limit_s()
    assert limits["max_concurrent_runs"] == MAX_CONCURRENT_RUNS == 2
    assert limits["competitor_max_extra_queries"] == 5
    assert limits["competitor_results_per_query"] == 3
    assert limits["evidence_max_items"] == 12


def test_the_providers_say_configured_without_naming_a_key(meta: dict) -> None:
    providers = meta["providers"]

    assert providers["llm"] == {"name": "Gemini", "configured": True, "model": "test-model"}
    assert providers["search"] == {"name": "Tavily", "configured": True, "model": None}
    assert providers["fallback_llm"] == {"name": "Groq", "configured": False, "model": GROQ_MODEL}, (
        "the fallback is off in tests, and its model name is shown either way"
    )


def test_a_missing_key_is_reported_as_not_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY")
    monkeypatch.delenv("LLM_MODEL")

    providers = client.get(META).json()["providers"]

    assert providers["search"]["configured"] is False
    assert providers["llm"] == {"name": "Gemini", "configured": False, "model": None}


def test_a_configured_groq_key_is_reported_without_its_value(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_not_a_real_key_000000000000")

    body = client.get(META).text

    assert json.loads(body)["providers"]["fallback_llm"]["configured"] is True
    assert "gsk_not_a_real_key_000000000000" not in body


def test_no_key_or_credential_field_appears_anywhere(client: TestClient) -> None:
    body = client.get(META).text

    assert all(secret not in body for secret in SECRETS)
    for field in ("api_key", "apikey", "token", "authorization", "bearer", "secret", "password", "key_length"):
        assert field not in body.lower(), field


def test_the_reply_needs_no_run_history(client: TestClient) -> None:
    """/api/meta must answer even when the history file cannot be used."""
    client.app.state.run_manager = None
    assert client.get(META).status_code == 200

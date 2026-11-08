"""Milestone 2 settings, the new error, and .env.example (KIRO_PROMPT_M2.md Section 5.6)."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from config import (
    DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES,
    DEFAULT_COMPETITOR_RESULTS_PER_QUERY,
    DEFAULT_EVIDENCE_MAX_ITEMS,
    DEFAULT_PIPELINE_TIMEOUT_S,
    get_settings,
)
from tests.m2_fakes import M2_SETTINGS
from utils.errors import AppError, InsufficientEvidenceError

ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"
SECRET_PATTERN = re.compile(r"tvly-[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{20,}|AQ\.[A-Za-z0-9_-]{20,}")


@pytest.fixture(autouse=True)
def default_m2_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in M2_SETTINGS:
        monkeypatch.delenv(name, raising=False)


def test_new_settings_have_the_specified_defaults() -> None:
    settings = get_settings()
    assert settings.competitor_max_extra_queries == DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES == 5
    assert settings.competitor_results_per_query == DEFAULT_COMPETITOR_RESULTS_PER_QUERY == 3
    assert settings.evidence_max_items == DEFAULT_EVIDENCE_MAX_ITEMS == 12
    assert settings.pipeline_timeout_s == DEFAULT_PIPELINE_TIMEOUT_S == 180.0


def test_new_settings_read_custom_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETITOR_MAX_EXTRA_QUERIES", "2")
    monkeypatch.setenv("COMPETITOR_RESULTS_PER_QUERY", "4")
    monkeypatch.setenv("EVIDENCE_MAX_ITEMS", "20")
    monkeypatch.setenv("PIPELINE_TIMEOUT_S", "240.5")
    settings = get_settings()
    assert (settings.competitor_max_extra_queries, settings.competitor_results_per_query) == (2, 4)
    assert (settings.evidence_max_items, settings.pipeline_timeout_s) == (20, 240.5)


@pytest.mark.parametrize("raw", ["abc", "2.5", "0", "-3"])
def test_bad_whole_numbers_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("COMPETITOR_MAX_EXTRA_QUERIES", raw)
    monkeypatch.setenv("EVIDENCE_MAX_ITEMS", raw)
    settings = get_settings()
    assert settings.competitor_max_extra_queries == DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES
    assert settings.evidence_max_items == DEFAULT_EVIDENCE_MAX_ITEMS


@pytest.mark.parametrize("raw", ["slow", "0", "-10"])
def test_bad_pipeline_timeout_falls_back(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("PIPELINE_TIMEOUT_S", raw)
    assert get_settings().pipeline_timeout_s == DEFAULT_PIPELINE_TIMEOUT_S


def test_env_example_lists_every_new_setting_with_its_default() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    expected = {
        "COMPETITOR_MAX_EXTRA_QUERIES": "5",
        "COMPETITOR_RESULTS_PER_QUERY": "3",
        "EVIDENCE_MAX_ITEMS": "12",
        "PIPELINE_TIMEOUT_S": "180",
    }
    for name, value in expected.items():
        assert re.search(rf"^{name}={value}\s*$", text, re.MULTILINE), name


def test_env_example_holds_placeholders_only() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert not SECRET_PATTERN.search(text)
    keys = dict(line.split("=", 1) for line in text.splitlines() if re.match(r"^[A-Z_]+_API_KEY=", line))
    assert keys and all("your_" in value for value in keys.values())


def test_insufficient_evidence_error_is_an_app_error() -> None:
    error = InsufficientEvidenceError()
    assert isinstance(error, AppError)
    assert (error.code, error.status_code) == ("insufficient_evidence", 502)
    assert "Traceback" not in error.user_message and error.user_message.endswith(".")


def test_insufficient_evidence_error_reaches_the_user_as_error_json() -> None:
    app = create_app()

    @app.get("/raise-insufficient")
    def raise_insufficient() -> None:
        raise InsufficientEvidenceError()

    response = TestClient(app, raise_server_exceptions=False).get("/raise-insufficient")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "insufficient_evidence"

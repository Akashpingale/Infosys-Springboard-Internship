import pytest

from config import DEFAULT_BACKEND_URL, DEFAULT_TIMEOUT_S, get_settings


def test_reads_keys_from_environment() -> None:
    settings = get_settings()
    assert settings.tavily_api_key == "test-tavily-key"
    assert settings.llm_api_key == "test-llm-key"
    assert settings.llm_model == "test-model"


def test_defaults_for_optional_settings() -> None:
    settings = get_settings()
    assert settings.backend_url == DEFAULT_BACKEND_URL
    assert settings.llm_timeout_s == DEFAULT_TIMEOUT_S
    assert settings.search_timeout_s == DEFAULT_TIMEOUT_S


def test_blank_keys_are_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "   ")
    monkeypatch.delenv("TAVILY_API_KEY")
    settings = get_settings()
    assert settings.llm_api_key is None and settings.tavily_api_key is None


@pytest.mark.parametrize("raw", ["abc", "-5", "0"])
def test_bad_timeout_falls_back_to_default(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_S", raw)
    assert get_settings().llm_timeout_s == DEFAULT_TIMEOUT_S


def test_custom_values_and_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_URL", "http://127.0.0.1:9000/")
    monkeypatch.setenv("SEARCH_TIMEOUT_S", "12.5")
    settings = get_settings()
    assert settings.backend_url == "http://127.0.0.1:9000"
    assert settings.search_timeout_s == 12.5


def test_repr_never_shows_keys() -> None:
    text = repr(get_settings())
    assert "test-tavily-key" not in text and "test-llm-key" not in text

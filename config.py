import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger(__name__)

DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class Settings:
    tavily_api_key: str | None = field(repr=False)
    llm_api_key: str | None = field(repr=False)
    llm_model: str | None
    backend_url: str
    llm_timeout_s: float
    search_timeout_s: float


def _text_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("%s is not a number; using %s", name, default)
        return default
    if value <= 0:
        logger.warning("%s must be positive; using %s", name, default)
        return default
    return value


def get_settings() -> Settings:
    """Read settings at call time so tests can change them with monkeypatch."""
    return Settings(
        tavily_api_key=_text_env("TAVILY_API_KEY"),
        llm_api_key=_text_env("LLM_API_KEY"),
        llm_model=_text_env("LLM_MODEL"),
        backend_url=(_text_env("BACKEND_URL") or DEFAULT_BACKEND_URL).rstrip("/"),
        llm_timeout_s=_float_env("LLM_TIMEOUT_S", DEFAULT_TIMEOUT_S),
        search_timeout_s=_float_env("SEARCH_TIMEOUT_S", DEFAULT_TIMEOUT_S),
    )


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

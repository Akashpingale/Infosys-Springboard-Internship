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
DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES = 5
DEFAULT_COMPETITOR_RESULTS_PER_QUERY = 3
DEFAULT_EVIDENCE_MAX_ITEMS = 12
DEFAULT_PIPELINE_TIMEOUT_S = 180.0
# UI upgrade (KIRO_UI_UPGRADE_SPEC.md Section 10): the React dev server's origins, and where run
# history is kept.
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
DEFAULT_RUNS_DB_PATH = ROOT_DIR / "data" / "runs.db"
# Milestone 3 (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 12.6): defaults and the inclusive
# range each setting must fall in. A value outside its range falls back to the default.
DEFAULT_STRATEGY_TIME_LIMIT_S = 150.0
DEFAULT_STRATEGY_DIGEST_MAX_CHARS = 24000
DEFAULT_CHAT_MAX_USER_TURNS = 25
DEFAULT_CHAT_MAX_MESSAGE_CHARS = 1000
DEFAULT_CHAT_HISTORY_TURNS = 6
DEFAULT_CHAT_CONTEXT_MAX_CHARS = 30000
DEFAULT_CHAT_MAX_CONCURRENT = 2
DEFAULT_CHAT_COOLDOWN_S = 2.0
STRATEGY_TIME_LIMIT_S_RANGE = (30.0, 900.0)
STRATEGY_DIGEST_MAX_CHARS_RANGE = (4000, 100000)
CHAT_MAX_USER_TURNS_RANGE = (1, 100)
CHAT_MAX_MESSAGE_CHARS_RANGE = (100, 4000)
CHAT_HISTORY_TURNS_RANGE = (1, 20)
CHAT_CONTEXT_MAX_CHARS_RANGE = (4000, 120000)
CHAT_MAX_CONCURRENT_RANGE = (1, 8)
CHAT_COOLDOWN_S_RANGE = (0.0, 60.0)


@dataclass(frozen=True)
class Settings:
    tavily_api_key: str | None = field(repr=False)
    llm_api_key: str | None = field(repr=False)
    llm_model: str | None
    backend_url: str
    llm_timeout_s: float
    search_timeout_s: float
    competitor_max_extra_queries: int
    competitor_results_per_query: int
    evidence_max_items: int
    pipeline_timeout_s: float
    # Optional: the Groq fallback LLM (utils/groq_client.py). Unset means Gemini only.
    groq_api_key: str | None = field(default=None, repr=False)
    # UI upgrade: browser origins allowed to call the API (CORS_ORIGINS).
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    # Time limit of a background run (POST /api/runs). None keeps the existing rule, a share of
    # PIPELINE_TIMEOUT_S (orchestrator.analysis_time_limit_s).
    pipeline_time_limit_s: float | None = None
    # The SQLite file for run history (RUNS_DB_PATH); a relative path is read from the project root.
    runs_db_path: Path = DEFAULT_RUNS_DB_PATH
    # Milestone 3: the extra time of a run with strategy, the strategy digest cap, and the Advisor's
    # limits. Read here only; nothing uses them yet.
    strategy_time_limit_s: float = DEFAULT_STRATEGY_TIME_LIMIT_S
    strategy_digest_max_chars: int = DEFAULT_STRATEGY_DIGEST_MAX_CHARS
    chat_max_user_turns: int = DEFAULT_CHAT_MAX_USER_TURNS
    chat_max_message_chars: int = DEFAULT_CHAT_MAX_MESSAGE_CHARS
    chat_history_turns: int = DEFAULT_CHAT_HISTORY_TURNS
    chat_context_max_chars: int = DEFAULT_CHAT_CONTEXT_MAX_CHARS
    chat_max_concurrent: int = DEFAULT_CHAT_MAX_CONCURRENT
    chat_cooldown_s: float = DEFAULT_CHAT_COOLDOWN_S


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


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s is not a whole number; using %s", name, default)
        return default
    if value <= 0:
        logger.warning("%s must be positive; using %s", name, default)
        return default
    return value


def _optional_float_env(name: str) -> float | None:
    """A positive number, or None when unset or not usable (the caller's default rule applies)."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        logger.warning("%s is not a number; using the default", name)
        return None
    if value <= 0:
        logger.warning("%s must be positive; using the default", name)
        return None
    return value


def _bounded_float_env(name: str, default: float, bounds: tuple[float, float]) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("%s is not a number; using %s", name, default)
        return default
    if not bounds[0] <= value <= bounds[1]:
        logger.warning("%s must be between %s and %s; using %s", name, bounds[0], bounds[1], default)
        return default
    return value


def _bounded_int_env(name: str, default: int, bounds: tuple[int, int]) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s is not a whole number; using %s", name, default)
        return default
    if not bounds[0] <= value <= bounds[1]:
        logger.warning("%s must be between %s and %s; using %s", name, bounds[0], bounds[1], default)
        return default
    return value


def _origins_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Comma-separated http(s) origins. A wildcard is never accepted, so access stays narrow."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    origins = tuple(part.strip().rstrip("/") for part in raw.split(",") if part.strip())
    valid = tuple(origin for origin in origins if origin.startswith(("http://", "https://")) and "*" not in origin)
    if len(valid) != len(origins):
        logger.warning("%s holds entries that are not http(s) origins; they are ignored", name)
    if not valid:
        logger.warning("%s has no usable origin; using the default", name)
        return default
    return valid


def _path_env(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    path = Path(raw)
    return path if path.is_absolute() else ROOT_DIR / path


def get_settings() -> Settings:
    """Read settings at call time so tests can change them with monkeypatch."""
    return Settings(
        tavily_api_key=_text_env("TAVILY_API_KEY"),
        llm_api_key=_text_env("LLM_API_KEY"),
        llm_model=_text_env("LLM_MODEL"),
        backend_url=(_text_env("BACKEND_URL") or DEFAULT_BACKEND_URL).rstrip("/"),
        llm_timeout_s=_float_env("LLM_TIMEOUT_S", DEFAULT_TIMEOUT_S),
        search_timeout_s=_float_env("SEARCH_TIMEOUT_S", DEFAULT_TIMEOUT_S),
        competitor_max_extra_queries=_int_env(
            "COMPETITOR_MAX_EXTRA_QUERIES", DEFAULT_COMPETITOR_MAX_EXTRA_QUERIES
        ),
        competitor_results_per_query=_int_env(
            "COMPETITOR_RESULTS_PER_QUERY", DEFAULT_COMPETITOR_RESULTS_PER_QUERY
        ),
        evidence_max_items=_int_env("EVIDENCE_MAX_ITEMS", DEFAULT_EVIDENCE_MAX_ITEMS),
        pipeline_timeout_s=_float_env("PIPELINE_TIMEOUT_S", DEFAULT_PIPELINE_TIMEOUT_S),
        groq_api_key=_text_env("GROQ_API_KEY"),
        cors_origins=_origins_env("CORS_ORIGINS", DEFAULT_CORS_ORIGINS),
        pipeline_time_limit_s=_optional_float_env("PIPELINE_TIME_LIMIT_S"),
        runs_db_path=_path_env("RUNS_DB_PATH", DEFAULT_RUNS_DB_PATH),
        strategy_time_limit_s=_bounded_float_env(
            "STRATEGY_TIME_LIMIT_S", DEFAULT_STRATEGY_TIME_LIMIT_S, STRATEGY_TIME_LIMIT_S_RANGE
        ),
        strategy_digest_max_chars=_bounded_int_env(
            "STRATEGY_DIGEST_MAX_CHARS", DEFAULT_STRATEGY_DIGEST_MAX_CHARS, STRATEGY_DIGEST_MAX_CHARS_RANGE
        ),
        chat_max_user_turns=_bounded_int_env(
            "CHAT_MAX_USER_TURNS", DEFAULT_CHAT_MAX_USER_TURNS, CHAT_MAX_USER_TURNS_RANGE
        ),
        chat_max_message_chars=_bounded_int_env(
            "CHAT_MAX_MESSAGE_CHARS", DEFAULT_CHAT_MAX_MESSAGE_CHARS, CHAT_MAX_MESSAGE_CHARS_RANGE
        ),
        chat_history_turns=_bounded_int_env(
            "CHAT_HISTORY_TURNS", DEFAULT_CHAT_HISTORY_TURNS, CHAT_HISTORY_TURNS_RANGE
        ),
        chat_context_max_chars=_bounded_int_env(
            "CHAT_CONTEXT_MAX_CHARS", DEFAULT_CHAT_CONTEXT_MAX_CHARS, CHAT_CONTEXT_MAX_CHARS_RANGE
        ),
        chat_max_concurrent=_bounded_int_env(
            "CHAT_MAX_CONCURRENT", DEFAULT_CHAT_MAX_CONCURRENT, CHAT_MAX_CONCURRENT_RANGE
        ),
        chat_cooldown_s=_bounded_float_env("CHAT_COOLDOWN_S", DEFAULT_CHAT_COOLDOWN_S, CHAT_COOLDOWN_S_RANGE),
    )


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

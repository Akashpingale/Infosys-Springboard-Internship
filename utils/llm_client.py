"""Thin wrapper over the LLM provider (Gemini). The only module that imports the SDK."""

import logging
import time
from typing import Callable, NoReturn, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from config import Settings, get_settings
from utils.errors import LLMAPIError, LLMConfigError

logger = logging.getLogger(__name__)

T = TypeVar("T")

TEMPERATURE = 0.2
TEXT_GENERATION_ACTION = "generateContent"

TRANSIENT_STATUS_CODES = (500, 502, 503, 504)
RETRY_BACKOFF_S = (1.0, 3.0)

MSG_MODEL_NOT_FOUND = "The configured AI model was not found. Check LLM_MODEL in .env."
MSG_KEY_REJECTED = "The AI service rejected the API key. Check LLM_API_KEY in .env."
MSG_RATE_LIMIT = "The AI service rate limit or quota was reached. Please wait a minute and try again."
MSG_TIMEOUT = "The AI service took too long to reply. Please try again."
MSG_BUSY = "The AI service is busy right now. Please try again in a minute."
MSG_GENERIC = LLMAPIError.default_message


def _settings_or_raise() -> Settings:
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        raise LLMConfigError()
    return settings


def _make_client(settings: Settings) -> genai.Client:
    """Callers must keep the returned client in a variable and close it when done: if it
    is garbage-collected mid-request the SDK closes its connection and the call fails."""
    return genai.Client(
        api_key=settings.llm_api_key,
        http_options=types.HttpOptions(
            timeout=int(settings.llm_timeout_s * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def _close_quietly(client: genai.Client) -> None:
    close = getattr(client, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception as exc:
        logger.debug("closing the LLM client failed: %s", type(exc).__name__)


def _status_code(exc: Exception) -> int | None:
    return exc.code if isinstance(exc, genai_errors.APIError) else None


def _is_timeout(exc: Exception) -> bool:
    return "timeout" in type(exc).__name__.lower()


def _is_transient(exc: Exception) -> bool:
    """Only provider-side 5xx answers are retried. They fail fast, so a short backoff is
    cheap. Timeouts are not retried: each one would cost the full timeout budget again."""
    return _status_code(exc) in TRANSIENT_STATUS_CODES


def _is_key_error(exc: genai_errors.APIError) -> bool:
    """Gemini answers an invalid key with 400 API_KEY_INVALID as well as 401/403."""
    if exc.code in (401, 403):
        return True
    details = f"{exc.status or ''} {exc.message or ''}".lower()
    return exc.code == 400 and ("api key" in details or "api_key" in details)


def _raise_safe(exc: Exception) -> NoReturn:
    """Log the cause (class and HTTP status only) and raise a safe app error."""
    code = _status_code(exc)
    status = getattr(exc, "status", None) if isinstance(exc, genai_errors.APIError) else None
    logger.warning("LLM call failed: %s (HTTP %s, %s)", type(exc).__name__, code, status)

    if isinstance(exc, genai_errors.APIError):
        if code == 404:
            raise LLMConfigError(MSG_MODEL_NOT_FOUND) from None
        if _is_key_error(exc):
            raise LLMAPIError(MSG_KEY_REJECTED) from None
        if code == 429:
            raise LLMAPIError(MSG_RATE_LIMIT) from None
        if code in TRANSIENT_STATUS_CODES:
            raise LLMAPIError(MSG_BUSY) from None
    elif _is_timeout(exc):
        raise LLMAPIError(MSG_TIMEOUT) from None
    raise LLMAPIError(MSG_GENERIC) from None


def _call_provider(action: Callable[[genai.Client, Settings], T]) -> T:
    """Run `action` with a live client, retrying transient 5xx answers a bounded number
    of times. The client is closed after every attempt, successful or not.
    """
    settings = _settings_or_raise()
    attempts = len(RETRY_BACKOFF_S) + 1
    for attempt in range(1, attempts + 1):
        client = _make_client(settings)
        try:
            return action(client, settings)
        except Exception as exc:
            if attempt == attempts or not _is_transient(exc):
                _raise_safe(exc)
            wait = RETRY_BACKOFF_S[attempt - 1]
            logger.info(
                "transient LLM failure (HTTP %s), retry %d of %d in %.1fs",
                _status_code(exc),
                attempt,
                attempts - 1,
                wait,
            )
            time.sleep(wait)
        finally:
            _close_quietly(client)
    raise LLMAPIError(MSG_BUSY)  # not reached: the loop always returns or raises


def generate_json(system_prompt: str, user_prompt: str) -> str:
    """Ask the LLM for a JSON reply and return the raw text.

    Raises LLMConfigError when the key or model is missing or the model does not exist,
    and LLMAPIError for any other provider failure.
    """

    def action(client: genai.Client, settings: Settings) -> str:
        response = client.models.generate_content(
            model=settings.llm_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=TEMPERATURE,
                response_mime_type="application/json",
            ),
        )
        return response.text or ""

    return _call_provider(action)


def generate_text(prompt: str) -> str:
    """Plain-text call used by the connection check script."""

    def action(client: genai.Client, settings: Settings) -> str:
        response = client.models.generate_content(
            model=settings.llm_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0),
        )
        return response.text or ""

    return _call_provider(action)


def short_model_name(name: str) -> str:
    return name.removeprefix("models/")


def list_text_models() -> list[str]:
    """Names of models that support text generation, without the 'models/' prefix."""

    def action(client: genai.Client, settings: Settings) -> list[str]:
        return [
            short_model_name(model.name)
            for model in client.models.list()
            if model.name and TEXT_GENERATION_ACTION in (model.supported_actions or [])
        ]

    return _call_provider(action)


def model_exists(model_name: str) -> bool:
    """True only if the provider lists this exact model for text generation.

    Listing alone does not prove a model will answer; use generate_text for that.
    """
    return short_model_name(model_name) in list_text_models()

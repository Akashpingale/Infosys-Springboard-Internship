"""Thin wrapper over the LLM provider (Gemini). The only module that imports the SDK.

generate_json can fall back to Groq (utils/groq_client.py) when GROQ_API_KEY is set: once, after
a Gemini rate limit, quota error, temporary server error or timeout, under the same deadline rules.
"""

import logging
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Callable, NoReturn, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from config import Settings, get_settings
from utils import groq_client
from utils.deadline import call_timeout, raise_if_stopped, time_left
from utils.errors import LLMAPIError, LLMConfigError, LLMInvalidResponseError

logger = logging.getLogger(__name__)

T = TypeVar("T")

TEMPERATURE = 0.2
TEXT_GENERATION_ACTION = "generateContent"

TRANSIENT_STATUS_CODES = (500, 502, 503, 504)
RETRY_BACKOFF_S = (1.0, 3.0)

# The SDK sends HttpOptions.timeout to Gemini as the request deadline (X-Server-Timeout, in whole
# seconds, rounded up), and Gemini rejects a deadline under 10 s with 400 INVALID_ARGUMENT
# ("Minimum allowed deadline is 10s"). So no request is sent with less than this.
MIN_DEADLINE_S = 10.0

# The provider's own error message is logged for diagnosis: cut to this length, with anything
# that looks like a key or token removed first, and withheld if it repeats part of a prompt.
PROVIDER_MESSAGE_MAX = 200
PROMPT_ECHO_CHARS = 30
REDACTED = "[redacted]"
WITHHELD = "(withheld: it repeats part of the prompt)"
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_SECRET_PATTERN = re.compile(
    r"AIza[0-9A-Za-z_\-]{10,}"
    r"|AQ\.[0-9A-Za-z_\-]{10,}"
    r"|tvly-[0-9A-Za-z_\-]{6,}"
    r"|sk-[0-9A-Za-z_\-]{10,}"
    r"|\b(?i:bearer)\s+[^\s\"',;&]+"
    r"|\b(?i:x-goog-api-key|api[_-]?key|authorization|access[_-]?token|token|key)[\"']?\s*[=:]\s*[\"']?"
    r"(?:(?i:bearer|basic)\s+)?[^\s\"',;&]+"
)

MSG_MODEL_NOT_FOUND = "The configured AI model was not found. Check LLM_MODEL in .env."
MSG_KEY_REJECTED = "The AI service rejected the API key. Check LLM_API_KEY in .env."
MSG_RATE_LIMIT = "The AI service rate limit or quota was reached. Please wait a minute and try again."
MSG_TIMEOUT = "The AI service took too long to reply. Please try again."
MSG_BUSY = "The AI service is busy right now. Please try again in a minute."
MSG_GENERIC = LLMAPIError.default_message
MSG_TIME_LIMIT = "This AI step was not run because the request reached its time limit."
MSG_GROQ_KEY_REJECTED = "The fallback AI service rejected its API key. Check GROQ_API_KEY in .env."

# Gemini failures that the Groq fallback may answer, when GROQ_API_KEY is set: a rate limit or quota
# error, a temporary server error, or a timeout (_falls_back). An auth error, an invalid request, a
# missing model or key, a connection error or anything unexpected never falls back.
FALLBACK_STATUS_CODES = (429, *TRANSIENT_STATUS_CODES)

# What the user is told when the Groq attempt fails too. Other categories get MSG_GENERIC, and an
# invalid JSON reply is an LLMInvalidResponseError, as it is for Gemini.
@dataclass
class _StructuredCall:
    """One structured call (utils/structured.py): its first attempt and its one repair retry."""

    reply_model: type[BaseModel]
    gemini_failure: Exception | None = None


_structured_call: ContextVar[_StructuredCall | None] = ContextVar("structured_call", default=None)


@contextmanager
def structured_call(reply_model: type[BaseModel]) -> Iterator[None]:
    """Scope one structured call. Inside it, a Groq attempt is held to `reply_model`'s strict JSON
    schema, and once Gemini has failed with an error that falls back, the repair retry is sent to
    Groq only, instead of waiting for Gemini to fail again. The scope ends with the block."""
    token = _structured_call.set(_StructuredCall(reply_model))
    try:
        yield
    finally:
        _structured_call.reset(token)


GROQ_MESSAGES = {
    groq_client.RATE_LIMIT: MSG_RATE_LIMIT,
    groq_client.SERVER_ERROR: MSG_BUSY,
    groq_client.TIMEOUT: MSG_TIMEOUT,
    groq_client.AUTH: MSG_GROQ_KEY_REJECTED,
}


def _settings_or_raise() -> Settings:
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        raise LLMConfigError()
    return settings


def _make_client(settings: Settings, timeout_s: float) -> genai.Client:
    """Callers must keep the returned client in a variable and close it when done: if it
    is garbage-collected mid-request the SDK closes its connection and the call fails.

    The SDK takes the timeout in milliseconds, reads 0 as no timeout at all, and sends it to
    Gemini as the request deadline, so it is never below MIN_DEADLINE_S."""
    return genai.Client(
        api_key=settings.llm_api_key,
        http_options=types.HttpOptions(
            timeout=int(max(timeout_s, MIN_DEADLINE_S) * 1000),
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


def _repeats_prompt(text: str, prompts: tuple[str, ...]) -> bool:
    """True when `text` repeats PROMPT_ECHO_CHARS or more consecutive characters of a prompt."""
    flat = [" ".join(prompt.split()) for prompt in prompts if prompt]
    span = PROMPT_ECHO_CHARS
    return any(text[i : i + span] in prompt for prompt in flat for i in range(len(text) - span + 1))


def provider_message(
    exc: Exception, secrets: tuple[str | None, ...] = (), prompts: tuple[str, ...] = ()
) -> str:
    """The provider's own error message, safe to log: one line, every given secret and anything
    shaped like a key, token or authorization value replaced, withheld if it repeats part of a
    prompt, and at most PROVIDER_MESSAGE_MAX characters. Only the error's `message` field is
    read: never its full response body, the response headers or the request."""
    raw = exc.message if isinstance(exc, genai_errors.APIError) else None
    if not isinstance(raw, str) or not raw.strip():
        return ""
    text = " ".join(_CONTROL_CHARACTERS.sub(" ", raw).split())
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    text = _SECRET_PATTERN.sub(REDACTED, text)[: PROVIDER_MESSAGE_MAX + PROMPT_ECHO_CHARS]
    if _repeats_prompt(text, prompts):
        return WITHHELD
    if len(text) > PROVIDER_MESSAGE_MAX:
        text = text[: PROVIDER_MESSAGE_MAX - 3].rstrip() + "..."
    return text


def _raise_safe(
    exc: Exception, secrets: tuple[str | None, ...] = (), prompts: tuple[str, ...] = ()
) -> NoReturn:
    """Log the cause and raise a safe app error. The log carries the class, the HTTP status
    and the provider's sanitized message (provider_message), never a key, header or prompt."""
    code = _status_code(exc)
    status = getattr(exc, "status", None) if isinstance(exc, genai_errors.APIError) else None
    message = provider_message(exc, secrets, prompts)
    if message:
        logger.warning(
            "LLM call failed: %s (HTTP %s, %s): %s", type(exc).__name__, code, status, message
        )
    else:
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


def _falls_back(exc: Exception) -> bool:
    if isinstance(exc, genai_errors.APIError):
        return exc.code in FALLBACK_STATUS_CODES
    return _is_timeout(exc)


def _failure_category(exc: Exception) -> str:
    """The category logged for a Gemini failure that falls back (see _falls_back)."""
    code = _status_code(exc)
    if code == 429:
        return "rate_limit"
    return "server_error" if code in TRANSIENT_STATUS_CODES else "timeout"


def _groq_failure_note(exc: groq_client.GroqError) -> str:
    """Category, HTTP status, Groq's error code and the length of the text Groq could not use."""
    parts = [exc.category, f"HTTP {exc.status_code}"]
    if exc.code:
        parts.append(f"code {exc.code}")
    if exc.generated_chars is not None:
        parts.append(f"{exc.generated_chars} characters generated")
    return ", ".join(parts)


def _call_groq(primary: Exception, system_prompt: str, user_prompt: str, *, again: bool = False) -> str:
    """One Groq attempt after a Gemini failure that falls back, under the same deadline rules: it is
    sent only with MIN_DEADLINE_S or more left, and waits at most the time left. Without enough time
    the Gemini failure is reported, or, for a structured call's repair retry (`again`), the time
    limit. Inside a structured call the reply is held to the call's strict schema, and the Gemini
    failure is kept, so that the call's retry comes straight here (structured_call). Only the
    provider, the category, the HTTP status, Groq's error code and a length are logged, never a
    key, a prompt or a reply."""
    raise_if_stopped()
    settings = get_settings()
    secrets = (settings.llm_api_key, settings.tavily_api_key, settings.groq_api_key)
    scope = _structured_call.get()
    if scope is not None:
        scope.gemini_failure = primary
    left = time_left()
    if left is not None and left < MIN_DEADLINE_S:
        if again:
            logger.warning(
                "LLM call not sent: %.1fs left, below the %.0fs minimum deadline", max(left, 0.0), MIN_DEADLINE_S
            )
            raise LLMAPIError(MSG_TIME_LIMIT)
        logger.warning(
            "no Groq fallback: %.1fs left, below the %.0fs minimum deadline", max(left, 0.0), MIN_DEADLINE_S
        )
        _raise_safe(primary, secrets, (system_prompt, user_prompt))
    logger.warning(
        "Gemini failed%s (%s, HTTP %s); %s",
        " earlier in this call" if again else "",
        _failure_category(primary),
        _status_code(primary),
        "sending the retry to Groq only" if again else "trying the Groq fallback",
    )
    timeout_s = max(call_timeout(settings.llm_timeout_s), MIN_DEADLINE_S)
    try:
        return groq_client.generate_json(
            system_prompt,
            user_prompt,
            timeout_s=timeout_s,
            temperature=TEMPERATURE,
            reply_model=scope.reply_model if scope is not None else None,
        )
    except groq_client.GroqError as exc:
        logger.warning("Groq fallback failed (%s)", _groq_failure_note(exc))
        if exc.category == groq_client.INVALID_JSON:
            raise LLMInvalidResponseError() from None
        raise LLMAPIError(GROQ_MESSAGES.get(exc.category, MSG_GENERIC)) from None
    except Exception as exc:
        logger.warning("Groq fallback failed (unexpected, %s)", type(exc).__name__)
        raise LLMAPIError(MSG_GENERIC) from None


def _call_provider(
    action: Callable[[genai.Client, Settings], T],
    prompts: tuple[str, ...] = (),
    fallback: Callable[[Exception], T] | None = None,
) -> T:
    """Run `action` with a live client, retrying transient 5xx answers a bounded number
    of times. The client is closed after every attempt, successful or not.

    Every attempt waits at least MIN_DEADLINE_S, the shortest deadline Gemini accepts. Under a
    run's time limit (utils/deadline.py) each attempt also waits at most the time left, none is
    sent once less than MIN_DEADLINE_S is left, and no retry is made that would leave less.

    With a `fallback`, a failure that falls back (_falls_back) is not retried on Gemini: the
    fallback is called once with it instead, and its answer or error is the result.
    """
    settings = _settings_or_raise()
    secrets = (settings.llm_api_key, settings.tavily_api_key, settings.groq_api_key)
    attempts = len(RETRY_BACKOFF_S) + 1
    primary: Exception | None = None
    for attempt in range(1, attempts + 1):
        raise_if_stopped()
        left = time_left()
        if left is not None and left < MIN_DEADLINE_S:
            logger.warning(
                "LLM call not sent: %.1fs left, below the %.0fs minimum deadline",
                max(left, 0.0),
                MIN_DEADLINE_S,
            )
            raise LLMAPIError(MSG_TIME_LIMIT)
        client = _make_client(settings, call_timeout(settings.llm_timeout_s))
        try:
            return action(client, settings)
        except Exception as exc:
            if fallback is not None and _falls_back(exc):
                primary = exc
                break
            if attempt == attempts or not _is_transient(exc):
                _raise_safe(exc, secrets, prompts)
            wait = RETRY_BACKOFF_S[attempt - 1]
            left = time_left()
            if left is not None and left - wait < MIN_DEADLINE_S:
                logger.info(
                    "no LLM retry: %.1fs would be left after the %.1fs wait, below the %.0fs minimum",
                    max(left - wait, 0.0),
                    wait,
                    MIN_DEADLINE_S,
                )
                _raise_safe(exc, secrets, prompts)
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
    if primary is None or fallback is None:
        raise LLMAPIError(MSG_BUSY)  # not reached: the loop always returns, raises or falls back
    return fallback(primary)


def generate_json(system_prompt: str, user_prompt: str) -> str:
    """Ask the LLM for a JSON reply and return the raw text.

    Gemini is asked first. With GROQ_API_KEY set, a Gemini failure that falls back is answered by
    one Groq attempt (_call_groq); the caller validates either reply the same way. Within one
    structured call, the repair retry after such a failure goes to Groq only (structured_call).

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

    def groq(primary: Exception) -> str:
        return _call_groq(primary, system_prompt, user_prompt)

    scope = _structured_call.get()
    if scope is not None and scope.gemini_failure is not None and groq_client.is_configured():
        return _call_groq(scope.gemini_failure, system_prompt, user_prompt, again=True)
    fallback = groq if groq_client.is_configured() else None
    return _call_provider(action, (system_prompt, user_prompt), fallback)


def generate_text(prompt: str) -> str:
    """Plain-text call used by the connection check script."""

    def action(client: genai.Client, settings: Settings) -> str:
        response = client.models.generate_content(
            model=settings.llm_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0),
        )
        return response.text or ""

    return _call_provider(action, (prompt,))


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

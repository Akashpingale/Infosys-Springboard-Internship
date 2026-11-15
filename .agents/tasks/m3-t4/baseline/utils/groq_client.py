"""Thin wrapper over Groq's Chat Completions API, the fallback LLM provider (utils/llm_client.py).

The only module that calls Groq. It posts to the official OpenAI-compatible endpoint with `requests`,
which the project already uses for Tavily, so no SDK is added. The key is read at call time and sent
in a header, never in the URL or a log. A failure raises GroqError with its category, the HTTP status,
Groq's error code and the length of any text Groq could not use: no text from the request or the reply
body is kept, so none can reach a log or the user. llm_client decides when Groq is called, how long it
may take, and what the user is told.
"""

import copy
import logging
import re
import time
from functools import lru_cache
from typing import Any

import requests
from pydantic import BaseModel

from config import get_settings

logger = logging.getLogger(__name__)

API_URL = "https://api.groq.com/openai/v1/chat/completions"

# A production model on https://console.groq.com/docs/models (checked 2026-10-28), with a
# 131,072-token context and JSON object mode, and listed with rate limits for every plan. It reasons
# before it answers; reasoning is left out of the reply, so `content` holds the JSON alone.
MODEL = "openai/gpt-oss-120b"
REASONING_EFFORT = "low"
# Room for the longest analysis the live runs produced (about 3,400 tokens). The cap also keeps one
# request inside the base plan's 8,000 tokens per minute.
MAX_COMPLETION_TOKENS = 4096

# Failure categories. Only these, and the HTTP status, describe a failed call.
NOT_CONFIGURED = "not_configured"
AUTH = "auth"
RATE_LIMIT = "rate_limit"
SERVER_ERROR = "server_error"
TIMEOUT = "timeout"
CONNECTION = "connection"
INVALID_JSON = "invalid_json"
MODEL_UNAVAILABLE = "model_unavailable"
INVALID_REQUEST = "invalid_request"
BAD_REPLY = "bad_reply"

# Structured Outputs in strict mode (https://console.groq.com/docs/structured-outputs, which lists
# openai/gpt-oss-120b): constrained decoding makes the reply match the schema, so it is always valid
# JSON with the right keys, types and enum values. JSON object mode only asks for valid JSON. Strict
# mode needs every property required and additionalProperties false on every object, within the
# documented subset below. The schema is derived from the Pydantic model that validates the reply;
# a nullable field stays nullable, and the length and count limits outside the subset are left to
# that validation, which runs unchanged.
STRICT_KEYWORDS = frozenset(
    {"type", "properties", "required", "additionalProperties", "items", "enum", "anyOf", "$ref", "$defs"}
)
PYDANTIC_ONLY = frozenset({"title", "description", "default", "minLength", "maxLength", "minItems", "maxItems"})

# The only parts of an error body that are read: Groq's machine-readable `error.code`, and the
# length of `failed_generation`, the text Groq could not use. That text itself is never kept.
_IDENTIFIER = re.compile(r"[a-z0-9_]{1,64}")
_CODE_CATEGORIES = {
    "json_validate_failed": INVALID_JSON,
    "rate_limit_exceeded": RATE_LIMIT,
    "model_not_found": MODEL_UNAVAILABLE,
    "model_decommissioned": MODEL_UNAVAILABLE,
}
SERVER_STATUS_CODES = (498, 500, 502, 503, 504)  # 498: flex tier at capacity


class GroqError(Exception):
    """A failed Groq call, described by its category, its HTTP status, Groq's error code and the length
    of the text Groq could not use, and nothing else."""

    def __init__(
        self, category: str, status_code: int | None = None, *, code: str = "", generated_chars: int | None = None
    ) -> None:
        super().__init__(category if status_code is None else f"{category} (HTTP {status_code})")
        self.category = category
        self.status_code = status_code
        self.code = code
        self.generated_chars = generated_chars


def is_configured() -> bool:
    return bool(get_settings().groq_api_key)


def _strict(node: Any) -> Any:
    """One node of a Pydantic JSON schema, rewritten for strict mode (see STRICT_KEYWORDS)."""
    if isinstance(node, list):
        return [_strict(item) for item in node]
    if not isinstance(node, dict):
        return node
    unknown = set(node) - STRICT_KEYWORDS - PYDANTIC_ONLY - {"const"}
    if unknown or isinstance(node.get("additionalProperties"), dict):
        raise ValueError(f"no strict-mode form for {sorted(unknown) or ['additionalProperties schema']}")
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in PYDANTIC_ONLY:
            continue
        if key == "const":
            out["enum"] = [value]
        elif key in ("properties", "$defs"):
            out[key] = {name: _strict(sub) for name, sub in value.items()}
        elif key in ("items", "anyOf"):
            out[key] = _strict(value)
        else:
            out[key] = value
    if "properties" in out:
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    if "$ref" in out and len(out) > 1:
        raise ValueError("no strict-mode form for a $ref with other keywords")
    return out


@lru_cache(maxsize=None)
def _cached_strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    return _strict(model.model_json_schema())


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """The strict-mode JSON schema of `model`. Raises ValueError for a model it cannot express."""
    return copy.deepcopy(_cached_strict_schema(model))


def response_format(reply_model: type[BaseModel] | None) -> dict[str, Any]:
    """Strict Structured Outputs for `reply_model`; JSON object mode without one, or for a model
    whose schema strict mode cannot express."""
    if reply_model is None:
        return {"type": "json_object"}
    try:
        schema = strict_schema(reply_model)
    except ValueError as exc:
        logger.warning("no strict schema for %s (%s); using JSON object mode", reply_model.__name__, exc)
        return {"type": "json_object"}
    return {"type": "json_schema", "json_schema": {"name": reply_model.__name__, "strict": True, "schema": schema}}


def request_body(
    system_prompt: str, user_prompt: str, temperature: float, reply_model: type[BaseModel] | None = None
) -> dict[str, Any]:
    """The same system and user prompts as the Gemini call, with the reply held to `reply_model`."""
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "response_format": response_format(reply_model),
        "reasoning_effort": REASONING_EFFORT,
        "include_reasoning": False,
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
    }


def _error_details(response: requests.Response) -> tuple[str, int | None]:
    """Groq's error code, if it is a plain identifier, and the length of `failed_generation`."""
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return "", None
    if not isinstance(error, dict):
        return "", None
    code = error.get("code")
    failed = error.get("failed_generation")
    return (
        code if isinstance(code, str) and _IDENTIFIER.fullmatch(code) else "",
        len(failed) if isinstance(failed, str) else None,
    )


def _category(status_code: int, code: str) -> str:
    if code in _CODE_CATEGORIES:
        return _CODE_CATEGORIES[code]
    if status_code in (401, 403):
        return AUTH
    if status_code == 404:
        return MODEL_UNAVAILABLE
    if status_code == 429:
        return RATE_LIMIT
    if status_code in SERVER_STATUS_CODES or status_code >= 500:
        return SERVER_ERROR
    return INVALID_REQUEST


def _reply_text(response: requests.Response) -> tuple[str, dict]:
    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise GroqError(BAD_REPLY, response.status_code) from None
    if content is None:
        return "", body
    if not isinstance(content, str):
        raise GroqError(BAD_REPLY, response.status_code)
    return content, body


def _usage_note(body: dict) -> str:
    """Token counts and the finish reason of a reply, for the log. Numbers and identifiers only."""
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    details = usage.get("completion_tokens_details")
    reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
    choice = body["choices"][0]
    finish = choice.get("finish_reason") if isinstance(choice, dict) else None
    parts = []
    if isinstance(usage.get("prompt_tokens"), int) and isinstance(usage.get("completion_tokens"), int):
        parts.append(f"{usage['prompt_tokens']} prompt + {usage['completion_tokens']} completion tokens")
        if isinstance(reasoning, int):
            parts[-1] += f" ({reasoning} reasoning)"
    if isinstance(finish, str) and _IDENTIFIER.fullmatch(finish):
        parts.append(f"finish {finish}")
    return f": {', '.join(parts)}" if parts else ""


def generate_json(
    system_prompt: str,
    user_prompt: str,
    *,
    timeout_s: float,
    temperature: float,
    reply_model: type[BaseModel] | None = None,
) -> str:
    """One chat completion. Returns the reply text, as Gemini's generate_json does. With
    `reply_model`, the reply is held to that model's strict JSON schema; without it, to JSON object mode.

    Waits at most `timeout_s`: the caller applies the run's time limit. Never retries; the caller
    bounds the attempts. Raises GroqError without a key, and for any transport, status or reply problem.
    """
    settings = get_settings()
    if not settings.groq_api_key:
        raise GroqError(NOT_CONFIGURED)

    started = time.perf_counter()
    try:
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json=request_body(system_prompt, user_prompt, temperature, reply_model),
            timeout=timeout_s,
        )
    except requests.Timeout:
        raise GroqError(TIMEOUT) from None
    except requests.RequestException:
        raise GroqError(CONNECTION) from None

    if response.status_code >= 400:
        code, generated_chars = _error_details(response)
        raise GroqError(
            _category(response.status_code, code), response.status_code, code=code, generated_chars=generated_chars
        )
    text, body = _reply_text(response)
    logger.info("Groq answered in %.2fs (%s)%s", time.perf_counter() - started, MODEL, _usage_note(body))
    return text

"""One structured LLM call: ask for JSON, validate it, retry once. Shared by every agent."""

import logging
import re
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from utils import llm_client
from utils.errors import LLMInvalidResponseError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

RETRY_INSTRUCTION = (
    "Your previous reply could not be used because: {problem}\n"
    "Return only the corrected JSON object, with exactly the required keys."
)
# The provider rejected its own reply as invalid JSON (Groq's json_validate_failed), so there is no
# reply to describe.
PROBLEM_NOT_JSON = "reply: it was not valid JSON"

_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
_MAX_PROBLEM_CHARS = 500
_LOGGED_ISSUES_MAX = 8
_FIELD_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")


def strip_code_fences(reply: str) -> str:
    text = reply.strip()
    match = _FENCE_PATTERN.fullmatch(text)
    return match.group(1) if match else text


def describe_validation_error(exc: ValidationError) -> str:
    """Summarise what was wrong without echoing the reply's content."""
    parts = []
    for err in exc.errors(include_input=False):
        field = ".".join(str(p) for p in err["loc"]) or "reply"
        parts.append(f"{field}: {err['msg']}")
    return "; ".join(parts)[:_MAX_PROBLEM_CHARS]


def issue_locations(exc: ValidationError) -> str:
    """Where a reply broke the model, for the log: each issue's field path and Pydantic error type,
    never a value or a message. A path part that is not a plain field name or index is shown as ?."""
    issues = []
    for err in exc.errors(include_url=False, include_context=False, include_input=False):
        parts = [str(part) if isinstance(part, int) or _FIELD_NAME.fullmatch(str(part)) else "?" for part in err["loc"]]
        issues.append(f"{'.'.join(parts) or 'reply'} {err['type']}")
    shown = issues[:_LOGGED_ISSUES_MAX]
    more = f"; {len(issues) - len(shown)} more" if len(issues) > len(shown) else ""
    return "; ".join(shown) + more


def call_structured(
    system: str,
    user: str,
    model_cls: type[T],
    *,
    caller: Callable[[str, str], str] | None = None,
) -> T:
    """Call the LLM, validate the reply against `model_cls`, and retry exactly once.

    `caller` lets an agent pass its own module-level `generate_json` so existing
    monkeypatching keeps working. LLMConfigError and LLMAPIError are not retried. A reply the
    provider itself rejected as invalid JSON (LLMInvalidResponseError) gets the same one retry as a
    reply that fails validation. Both attempts run in one llm_client.structured_call scope, so a
    Groq fallback is held to `model_cls` and a retry after a Gemini failure goes to Groq only.
    """
    call = caller or llm_client.generate_json
    with llm_client.structured_call(model_cls):
        try:
            return model_cls.model_validate_json(strip_code_fences(call(system, user)))
        except ValidationError as exc:
            problem = describe_validation_error(exc)
            logger.info(
                "structured reply invalid (%d issues: %s), retrying once", exc.error_count(), issue_locations(exc)
            )
        except LLMInvalidResponseError:
            problem = PROBLEM_NOT_JSON
            logger.info("structured reply was rejected as invalid JSON, retrying once")
        retry_user = f"{user}\n\n{RETRY_INSTRUCTION.format(problem=problem)}"
        try:
            return model_cls.model_validate_json(strip_code_fences(call(system, retry_user)))
        except ValidationError as retry_exc:
            logger.warning(
                "structured reply failed after retry (%d issues: %s)",
                retry_exc.error_count(),
                issue_locations(retry_exc),
            )
            raise LLMInvalidResponseError() from None

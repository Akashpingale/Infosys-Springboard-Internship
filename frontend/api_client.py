"""Pure helpers for the Streamlit UI: form validation and the backend call.

No Streamlit import lives here, so every function can be unit tested.
"""

from dataclasses import dataclass

import requests
from pydantic import ValidationError

from config import get_settings
from models.schemas import (
    CUSTOMERS_MAX,
    CUSTOMERS_MIN,
    DETAILS_MAX,
    IDEA_MAX,
    IDEA_MIN,
    IDEA_MIN_WORDS,
    INDUSTRY_MAX,
    INDUSTRY_MIN,
    IdeaSubmission,
    PipelineResult,
)

VALIDATE_PATH = "/api/validate"
REQUEST_TIMEOUT_S = 90

OTHER_INDUSTRY = "Other"
INDUSTRY_OTHER_FIELD = "industry_other"

FIELD_LABELS = {
    "idea_description": "idea description",
    "industry": "industry",
    INDUSTRY_OTHER_FIELD: "industry",
    "target_customers": "target customers",
    "relevant_details": "extra details",
}
LENGTH_LIMITS = {
    "idea_description": (IDEA_MIN, IDEA_MAX),
    "industry": (INDUSTRY_MIN, INDUSTRY_MAX),
    "target_customers": (CUSTOMERS_MIN, CUSTOMERS_MAX),
    "relevant_details": (0, DETAILS_MAX),
}

MSG_OTHER_REQUIRED = "Please type the industry you mean."
MSG_BACKEND_DOWN = "Cannot reach the server. Start it with `python app.py` in the project folder."
MSG_TIMEOUT = "The server took too long to reply. Please try again."
MSG_BAD_REPLY = "The server sent a reply this app could not read. Please try again."
MSG_UNEXPECTED = "Something went wrong on the server. Please try again."
MSG_REJECTED = "The server rejected the form."


class BackendError(Exception):
    """Carries a message that is always safe to show to the user."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class FormValues:
    """Exactly what the form collected, before any cleaning."""

    idea_description: str = ""
    industry: str = ""
    industry_other: str = ""
    target_customers: str = ""
    relevant_details: str = ""


def resolve_industry(industry: str, industry_other: str) -> str:
    """'Other' means the free-text box decides the industry sent to the backend."""
    if industry == OTHER_INDUSTRY:
        return industry_other.strip()
    return industry.strip()


def _friendly(field: str, error: dict, value: str) -> str:
    label = FIELD_LABELS.get(field, field)
    kind = str(error.get("type", ""))
    minimum, maximum = LENGTH_LIMITS.get(field, (0, 0))

    if not value.strip() and kind in ("string_too_short", "missing"):
        return f"Please enter your {label}."
    if kind == "string_too_short":
        return f"Please use at least {minimum} characters for the {label}."
    if kind == "string_too_long":
        return f"Please keep the {label} to {maximum} characters or fewer."
    if kind == "value_error":
        return str(error.get("msg", "")).removeprefix("Value error, ")
    return f"Please check the {label}."


def validate_submission(values: FormValues) -> tuple[IdeaSubmission | None, dict[str, str]]:
    """Build the shared IdeaSubmission, or return a message per offending field.

    The limits come from models.schemas, so the UI never repeats a number.
    """
    errors: dict[str, str] = {}
    if values.industry == OTHER_INDUSTRY and not values.industry_other.strip():
        errors[INDUSTRY_OTHER_FIELD] = MSG_OTHER_REQUIRED

    cleaned = {
        "idea_description": values.idea_description.strip(),
        "industry": resolve_industry(values.industry, values.industry_other),
        "target_customers": values.target_customers.strip(),
        "relevant_details": values.relevant_details.strip() or None,
    }

    try:
        submission = IdeaSubmission(**cleaned)
    except ValidationError as exc:
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else "idea_description"
            if field == "industry" and INDUSTRY_OTHER_FIELD in errors:
                continue
            errors.setdefault(field, _friendly(field, error, str(cleaned.get(field) or "")))
        return None, errors

    return (None, errors) if errors else (submission, {})


def backend_url() -> str:
    return get_settings().backend_url


def _error_message(status_code: int, body: object) -> str:
    message = ""
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        message = str(body["error"].get("message") or "")
    if status_code == 422:
        return f"{MSG_REJECTED} {message}".strip() if message else MSG_REJECTED
    return message or MSG_UNEXPECTED


def validate_idea(
    submission: IdeaSubmission, *, url: str | None = None, timeout: float = REQUEST_TIMEOUT_S
) -> PipelineResult:
    """Send the submission to the backend pipeline and return the parsed result.

    Raises BackendError with a plain-English message for every failure, so the UI
    never has to interpret an exception or show a stack trace.
    """
    target = f"{url or backend_url()}{VALIDATE_PATH}"
    try:
        response = requests.post(target, json=submission.model_dump(mode="json"), timeout=timeout)
    except requests.Timeout:
        raise BackendError(MSG_TIMEOUT) from None
    except requests.ConnectionError:
        raise BackendError(MSG_BACKEND_DOWN) from None
    except requests.RequestException:
        raise BackendError(MSG_UNEXPECTED) from None

    try:
        body = response.json()
    except ValueError:
        raise BackendError(MSG_BAD_REPLY) from None

    if response.status_code != 200:
        raise BackendError(_error_message(response.status_code, body))

    try:
        return PipelineResult.model_validate(body)
    except ValidationError:
        raise BackendError(MSG_BAD_REPLY) from None


def character_hint(field: str) -> str:
    """Short caption showing the shared limits instead of hard-coded numbers."""
    minimum, maximum = LENGTH_LIMITS[field]
    if field == "idea_description":
        return f"{minimum} to {maximum} characters, at least {IDEA_MIN_WORDS} words."
    if minimum:
        return f"{minimum} to {maximum} characters."
    return f"Optional, up to {maximum} characters."

class AppError(Exception):
    """Base error. `user_message` is safe to show; it never contains keys or raw replies."""

    code = "internal_error"
    status_code = 500
    default_message = "Something went wrong. Please try again."

    def __init__(self, user_message: str | None = None) -> None:
        self.user_message = user_message or self.default_message
        super().__init__(self.user_message)


class InputValidationError(AppError):
    code = "invalid_input"
    status_code = 422
    default_message = "Some of the information you entered is not valid."


class LLMConfigError(AppError):
    code = "llm_not_configured"
    status_code = 503
    default_message = "The AI service is not configured."


class LLMAPIError(AppError):
    code = "llm_api_error"
    status_code = 502
    default_message = "The AI service is not responding. Please try again."


class LLMInvalidResponseError(AppError):
    code = "llm_invalid_response"
    status_code = 502
    default_message = "Could not understand the AI reply. Please try again."


class SearchError(AppError):
    """Parent of all web search errors (kept from Week 1 naming)."""

    code = "search_error"
    status_code = 502
    default_message = "Web search failed. Please try again."


class SearchConfigError(SearchError):
    code = "search_not_configured"
    status_code = 503
    default_message = "Web search is not configured: TAVILY_API_KEY is not set."


class SearchAPIError(SearchError):
    code = "search_api_error"
    status_code = 502
    default_message = "The web search service is not responding. Please try again."


class InsufficientEvidenceError(AppError):
    code = "insufficient_evidence"
    status_code = 502
    default_message = (
        "Not enough reliable information was found online to analyse this idea. "
        "Please try again later."
    )


# --- UI upgrade (KIRO_UI_UPGRADE_SPEC.md Section 10): background runs and their history ---------


class RunNotFoundError(AppError):
    code = "run_not_found"
    status_code = 404
    default_message = "This validation could not be found. It may have been deleted."


class RunLimitError(AppError):
    code = "run_limit_reached"
    status_code = 409
    default_message = "A validation is already running. Try again when it has finished."


class RunActiveError(AppError):
    code = "run_active"
    status_code = 409
    default_message = "This validation is still running. Cancel it first, then try again."


class ReportNotReadyError(AppError):
    code = "report_not_ready"
    status_code = 409
    default_message = "The report is not ready yet. Try again when the validation has finished."


class RunCancelledError(AppError):
    """Raised before an outside call once the run was cancelled. It becomes a stage error."""

    code = "run_cancelled"
    status_code = 409
    default_message = "The run was cancelled before this step finished."


class HistoryUnavailableError(AppError):
    code = "history_unavailable"
    status_code = 503
    default_message = (
        "Saved validations are not available right now. Check that the data folder can be written, "
        "then restart the server."
    )

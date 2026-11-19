from config import DEFAULT_CHAT_MAX_MESSAGE_CHARS


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


# --- Milestone 3 (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 12.4): strategy and Advisor --


class RunNotFinishedError(AppError):
    code = "run_not_finished"
    status_code = 409
    default_message = "This validation is still running."


class StrategyNotReadyError(AppError):
    code = "strategy_not_ready"
    status_code = 409
    default_message = "There is no market or competitor analysis to build a strategy on."


class StrategyAlreadyCompleteError(AppError):
    code = "strategy_already_complete"
    status_code = 409
    default_message = "This validation already has a strategy."


class ChatUnavailableError(AppError):
    code = "chat_unavailable"
    status_code = 409
    default_message = "Questions open once the validation has finished."


class ChatLimitError(AppError):
    code = "chat_limit_reached"
    status_code = 409
    default_message = "This conversation is full. Clear it to start again."


class ChatBusyError(AppError):
    code = "chat_busy"
    status_code = 409
    default_message = "Wait for the current answer first."


class ChatCooldownError(AppError):
    code = "chat_cooldown"
    status_code = 429
    default_message = "Wait a moment before the next question."


class ChatMessageInvalidError(AppError):
    code = "chat_message_invalid"
    status_code = 422
    message_template = "Write a question of up to {n} characters."
    default_message = message_template.format(n=DEFAULT_CHAT_MAX_MESSAGE_CHARS)

    def __init__(self, max_chars: int = DEFAULT_CHAT_MAX_MESSAGE_CHARS) -> None:
        super().__init__(self.message_template.format(n=max_chars))


class ReportUnavailableError(AppError):
    code = "report_unavailable"
    status_code = 409
    default_message = "A report can be made once the validation has finished with results."


class ReportNotFoundError(AppError):
    code = "report_not_found"
    status_code = 404
    default_message = "Generate the report first."


class ReportBusyError(AppError):
    code = "report_busy"
    status_code = 409
    default_message = "The report for this validation is already being written. Wait for it to finish."


class ReportRenderError(AppError):
    code = "report_render_failed"
    status_code = 500
    default_message = "The report fonts are not installed. See the setup guide."


class ReportTooLargeError(AppError):
    code = "report_too_large"
    status_code = 422
    default_message = "The report is too large to download as a file."

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

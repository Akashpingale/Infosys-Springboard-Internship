import pytest

from utils.errors import (
    AppError,
    InputValidationError,
    LLMAPIError,
    LLMConfigError,
    LLMInvalidResponseError,
    SearchAPIError,
    SearchConfigError,
    SearchError,
)


@pytest.mark.parametrize(
    ("error_class", "status"),
    [
        (InputValidationError, 422),
        (LLMConfigError, 503),
        (LLMAPIError, 502),
        (LLMInvalidResponseError, 502),
        (SearchConfigError, 503),
        (SearchAPIError, 502),
    ],
)
def test_status_codes_and_unique_codes(error_class: type[AppError], status: int) -> None:
    error = error_class()
    assert isinstance(error, AppError)
    assert error.status_code == status
    assert error.user_message == error_class.default_message


def test_search_errors_share_week1_parent() -> None:
    assert issubclass(SearchConfigError, SearchError)
    assert issubclass(SearchAPIError, SearchError)


def test_custom_message_overrides_default() -> None:
    error = LLMAPIError("The AI service rejected the API key.")
    assert str(error) == error.user_message == "The AI service rejected the API key."


def test_matrix_messages() -> None:
    assert LLMConfigError().user_message == "The AI service is not configured."
    assert "TAVILY_API_KEY is not set" in SearchConfigError().user_message
    assert LLMInvalidResponseError().user_message.startswith("Could not understand the AI reply")

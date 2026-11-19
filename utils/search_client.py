"""Thin wrapper over the Tavily search API. The only module that calls Tavily directly."""

import logging
from typing import Any

import requests

from config import get_settings
from utils.deadline import call_timeout, raise_if_stopped
from utils.errors import SearchAPIError, SearchConfigError
from utils.usage import count_search_call

logger = logging.getLogger(__name__)

API_URL = "https://api.tavily.com/search"
DEFAULT_MAX_RESULTS = 3
DEFAULT_DEPTH = "basic"

MSG_KEY_REJECTED = "The web search service rejected the API key. Check TAVILY_API_KEY in .env."
MSG_RATE_LIMIT = "The web search rate or credit limit was reached. Please try again later."
MSG_TIMEOUT = "The web search service took too long to reply. Please try again."
MSG_UNREACHABLE = "Could not reach the web search service. Check your internet connection."
MSG_BAD_REPLY = "The web search service sent a reply that could not be read."
MSG_BUSY = "The web search service is busy right now. Please try again in a minute."
MSG_REJECTED_QUERY = "The web search service rejected this query."
MSG_TIME_LIMIT = "This web search was not run because the request reached its time limit."


def _message_for_status(status_code: int) -> str:
    if status_code in (401, 403):
        return MSG_KEY_REJECTED
    if status_code == 429:
        return MSG_RATE_LIMIT
    if status_code >= 500:
        return MSG_BUSY
    return MSG_REJECTED_QUERY


def search(
    query: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    depth: str = DEFAULT_DEPTH,
    include_answer: bool = True,
    topic: str | None = None,
    time_range: str | None = None,
) -> dict[str, Any]:
    """Run one Tavily search and return the parsed JSON body.

    The key is read at call time and sent in a header, never in the URL or a log.
    Raises SearchConfigError when the key is missing and SearchAPIError for any
    transport, status or body problem, or when the run's time limit has passed
    (utils/deadline.py), in which case nothing is sent.
    """
    settings = get_settings()
    if not settings.tavily_api_key:
        raise SearchConfigError()
    raise_if_stopped()
    timeout = call_timeout(settings.search_timeout_s)
    if timeout <= 0:
        logger.warning("Tavily request not sent: the time limit was reached")
        raise SearchAPIError(MSG_TIME_LIMIT)

    payload = {
        "query": query,
        "search_depth": depth,
        "max_results": max_results,
        "include_answer": include_answer,
    }
    payload.update({name: value for name, value in (("topic", topic), ("time_range", time_range)) if value})
    count_search_call()
    try:
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
            json=payload,
            timeout=timeout,
        )
    except requests.Timeout:
        logger.warning("Tavily request timed out")
        raise SearchAPIError(MSG_TIMEOUT) from None
    except requests.RequestException as exc:
        logger.warning("Tavily request failed (%s)", type(exc).__name__)
        raise SearchAPIError(MSG_UNREACHABLE) from None

    if response.status_code >= 400:
        logger.warning("Tavily returned HTTP %s", response.status_code)
        raise SearchAPIError(_message_for_status(response.status_code)) from None

    try:
        body = response.json()
    except ValueError:
        logger.warning("Tavily reply was not JSON (HTTP %s)", response.status_code)
        raise SearchAPIError(MSG_BAD_REPLY) from None

    if not isinstance(body, dict):
        logger.warning("Tavily reply was not an object")
        raise SearchAPIError(MSG_BAD_REPLY) from None
    return body

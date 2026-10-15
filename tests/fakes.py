"""Fake LLM replies, fake Tavily responses and helpers for simulating failures."""

import json
from typing import Any, Callable

import requests

VALID_EXTRACTION = {
    "idea_title": "CropScan: AI crop disease detection",
    "problem": "Small farmers in India lose crops because diseases are spotted too late.",
    "solution": "A phone app that detects crop diseases from a photo and suggests treatment.",
    "target_customers": ["Small farmers in India", "Agricultural cooperatives"],
    "industry": "Agriculture / AgriTech",
    "key_features": ["Photo-based diagnosis", "Treatment advice", "Local language support"],
}

LLM_REPLY_OK = json.dumps(VALID_EXTRACTION)
LLM_REPLY_FENCED = f"```json\n{LLM_REPLY_OK}\n```"
LLM_REPLY_NOT_JSON = "Sure! Here is the idea: CropScan helps farmers."
LLM_REPLY_EMPTY = ""
LLM_REPLY_MISSING_FIELD = json.dumps({k: v for k, v in VALID_EXTRACTION.items() if k != "problem"})
LLM_REPLY_EMPTY_LIST = json.dumps({**VALID_EXTRACTION, "key_features": []})
LLM_REPLY_EXTRA_KEY = json.dumps({**VALID_EXTRACTION, "market_size": "USD 5 billion"})

TAVILY_OK_RESPONSE = {
    "query": "agritech crop disease detection market size growth trends",
    "answer": "The crop disease detection market is growing as smartphone use rises in rural areas.",
    "results": [
        {
            "title": "Plant disease detection market report",
            "url": "https://example.com/market-report",
            "content": "The market for AI plant disease detection is expanding in Asia.",
            "score": 0.91,
        },
        {
            "title": "Startups helping farmers with AI",
            "url": "https://example.com/agritech-startups",
            "content": "Several startups offer photo-based crop diagnosis for farmers.",
            "score": 0.84,
        },
    ],
}
TAVILY_EMPTY_RESPONSE = {"query": "nothing", "answer": None, "results": []}


class FakeHTTPResponse:
    """Stands in for requests.Response in tests."""

    def __init__(self, status_code: int = 200, json_data: Any = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text if text or json_data is None else json.dumps(json_data)

    def json(self) -> Any:
        if self._json_data is None:
            raise ValueError("Response body is not JSON")
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


def tavily_ok() -> FakeHTTPResponse:
    return FakeHTTPResponse(200, TAVILY_OK_RESPONSE)


def tavily_status(status_code: int) -> FakeHTTPResponse:
    return FakeHTTPResponse(status_code, {"detail": {"error": f"HTTP {status_code}"}})


def tavily_not_json() -> FakeHTTPResponse:
    return FakeHTTPResponse(200, None, "<html>Service unavailable</html>")


def tavily_empty() -> FakeHTTPResponse:
    return FakeHTTPResponse(200, TAVILY_EMPTY_RESPONSE)


def make_sequence(*outcomes: Any) -> Callable[..., Any]:
    """Return a fake callable that yields `outcomes` in order (the last one repeats).

    Exception instances are raised instead of returned. Calls are recorded in `.calls`.
    """
    if not outcomes:
        raise ValueError("make_sequence needs at least one outcome")
    calls: list[tuple[tuple, dict]] = []

    def fake(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        outcome = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    fake.calls = calls  # type: ignore[attr-defined]
    return fake


TAVILY_TIMEOUT = requests.Timeout("Tavily timed out")
TAVILY_CONNECTION_ERROR = requests.ConnectionError("Cannot reach Tavily")

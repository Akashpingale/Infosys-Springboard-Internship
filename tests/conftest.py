import socket
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from app import create_app
from tests.fakes import LLM_REPLY_OK, make_sequence, tavily_ok

FAKE_ENV = {
    "TAVILY_API_KEY": "test-tavily-key",
    "LLM_API_KEY": "test-llm-key",
    "LLM_MODEL": "test-model",
}
OPTIONAL_ENV = ("BACKEND_URL", "LLM_TIMEOUT_S", "SEARCH_TIMEOUT_S")
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def fake_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace real keys loaded from .env with fake ones for every test."""
    for name, value in FAKE_ENV.items():
        monkeypatch.setenv(name, value)
    for name in OPTIONAL_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that tries to open a non-local connection."""
    real_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else address
        if host not in LOCAL_HOSTS:
            raise RuntimeError(f"Network access is blocked in tests (tried {host})")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def fake_llm_ok() -> Callable[..., str]:
    """Fake `generate_json(system_prompt, user_prompt)` returning a valid extraction."""
    return make_sequence(LLM_REPLY_OK)


@pytest.fixture
def fake_tavily_ok() -> Callable[..., Any]:
    """Fake `requests.post` returning a realistic Tavily response."""
    return make_sequence(tavily_ok())

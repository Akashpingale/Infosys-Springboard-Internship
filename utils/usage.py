import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar


class UsageCounter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._llm_calls = 0
        self._search_calls = 0

    def add_llm_call(self) -> None:
        with self._lock:
            self._llm_calls += 1

    def add_search_call(self) -> None:
        with self._lock:
            self._search_calls += 1

    def totals(self) -> tuple[int, int]:
        with self._lock:
            return self._llm_calls, self._search_calls


_counter: ContextVar[UsageCounter | None] = ContextVar("usage_counter", default=None)


@contextmanager
def counting(counter: UsageCounter | None) -> Iterator[None]:
    token = _counter.set(counter)
    try:
        yield
    finally:
        _counter.reset(token)


def count_llm_call() -> None:
    counter = _counter.get()
    if counter is not None:
        counter.add_llm_call()


def count_search_call() -> None:
    counter = _counter.get()
    if counter is not None:
        counter.add_search_call()

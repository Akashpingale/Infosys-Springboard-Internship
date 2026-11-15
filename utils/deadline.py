"""The time limit of one pipeline run, shared with the LLM and search clients.

The orchestrator sets it for a full run. While it is set, every outside call waits at most the
time that is left, and no call starts once it has passed. Without a limit, as in a Milestone 1
run, every call keeps its configured timeout.
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from utils.errors import RunCancelledError

# Read at call time, so tests can move time forward without waiting.
clock = time.monotonic

_deadline: ContextVar[float | None] = ContextVar("pipeline_deadline", default=None)
# A background run's cancel check (utils/run_manager.py). While it is set, the clients ask it before
# every outside call and send nothing once it says stop. None, the default, never stops anything.
_stop_check: ContextVar[Callable[[], bool] | None] = ContextVar("pipeline_stop_check", default=None)


@contextmanager
def time_limit(seconds: float | None) -> Iterator[None]:
    """Limit the outside calls inside the block to `seconds` from now (None: no limit). The
    previous limit is restored on exit, also when the block raises."""
    token = _deadline.set(None if seconds is None else clock() + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)


@contextmanager
def extra_time(seconds: float | None) -> Iterator[None]:
    """Move the current limit `seconds` later inside the block, for the strategy stages of a run
    with strategy (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md D-11). Without a limit, or with None,
    nothing changes. The previous limit is restored on exit, also when the block raises."""
    deadline = _deadline.get()
    token = _deadline.set(deadline if deadline is None or seconds is None else deadline + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)


def time_left() -> float | None:
    """Seconds until the current limit (zero or less once it has passed); None without one."""
    deadline = _deadline.get()
    return None if deadline is None else deadline - clock()


def call_timeout(configured: float) -> float:
    """The timeout for the next outside call: `configured`, cut to the time left (0 if none)."""
    left = time_left()
    return configured if left is None else max(0.0, min(configured, left))


@contextmanager
def stop_check(check: Callable[[], bool] | None) -> Iterator[None]:
    """Use `check` as the cancel check inside the block (None: never stop). The previous check is
    restored on exit, also when the block raises."""
    token = _stop_check.set(check)
    try:
        yield
    finally:
        _stop_check.reset(token)


def stop_requested() -> bool:
    check = _stop_check.get()
    return check is not None and bool(check())


def raise_if_stopped() -> None:
    """Raise RunCancelledError when the current run was cancelled, so the next call is not sent.
    A call that is already in flight is not interrupted: cancelling is cooperative."""
    if stop_requested():
        raise RunCancelledError()

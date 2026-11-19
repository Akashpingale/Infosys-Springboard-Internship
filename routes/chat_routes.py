import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from agents import advisor_agent
from config import get_settings
from models.api import ErrorResponse, RunDetail
from models.chat import ChatLimits, ChatReply, ChatRequest, ChatThread
from routes.meta_routes import chat_limits
from routes.run_routes import get_manager
from utils.chat_store import ChatStore
from utils.errors import (
    ChatBusyError,
    ChatCooldownError,
    ChatLimitError,
    ChatMessageInvalidError,
    ChatUnavailableError,
    LLMInvalidResponseError,
    RunNotFoundError,
)
from utils.run_manager import RunManager

logger = logging.getLogger(__name__)

AVAILABLE_STATE = "done"
AVAILABLE_STATUSES = ("complete", "partial")
MSG_REPHRASE = "Try rephrasing the question."
ERRORS = {code: {"model": ErrorResponse} for code in (404, 409, 503)}
ASK_ERRORS = {**ERRORS, **{code: {"model": ErrorResponse} for code in (422, 429, 502)}}

clock = time.monotonic


class ChatRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        handler = super().get_route_handler()

        async def route_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                raise ChatMessageInvalidError(get_settings().chat_max_message_chars) from None

        return route_handler


class ChatGate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy: set[str] = set()
        self._asked: dict[str, float] = {}
        self._slots = threading.BoundedSemaphore(get_settings().chat_max_concurrent)

    def ensure_idle(self, run_id: str) -> None:
        with self._lock:
            if run_id in self._busy:
                raise ChatBusyError()

    @contextmanager
    def turn(self, run_id: str) -> Iterator[None]:
        with self._lock:
            if run_id in self._busy:
                raise ChatBusyError()
            now = clock()
            asked = self._asked.get(run_id)
            if asked is not None and now - asked < get_settings().chat_cooldown_s:
                raise ChatCooldownError()
            self._busy.add(run_id)
            self._asked[run_id] = now
        try:
            with self._slots:
                yield
        finally:
            with self._lock:
                self._busy.discard(run_id)

    @contextmanager
    def slot(self) -> Iterator[None]:
        with self._slots:
            yield


router = APIRouter(prefix="/api/runs", tags=["chat"], route_class=ChatRoute)


def get_gate(request: Request) -> ChatGate:
    return request.app.state.chat_gate


def _chats(manager: RunManager) -> ChatStore:
    return ChatStore(manager._store)


def _available(manager: RunManager, run_id: str) -> RunDetail:
    run = manager.get(run_id)
    if run.state != AVAILABLE_STATE or run.result is None or run.result.status not in AVAILABLE_STATUSES:
        raise ChatUnavailableError()
    return run


def _remaining(chats: ChatStore, run_id: str) -> int:
    return max(get_settings().chat_max_user_turns - chats.count(run_id, "user"), 0)


@router.get("/{run_id}/chat", response_model=ChatThread, responses=ERRORS)
def read_chat(run_id: str, manager: RunManager = Depends(get_manager)) -> ChatThread:
    run = _available(manager, run_id)
    chats = _chats(manager)
    return ChatThread(
        messages=chats.list(run_id),
        suggestions=advisor_agent.suggestions(run.result),
        available_sections=advisor_agent.available_sections(run.result),
        remaining_turns=_remaining(chats, run_id),
        limits=ChatLimits.model_validate(chat_limits().model_dump()),
    )


@router.post("/{run_id}/chat", response_model=ChatReply, responses=ASK_ERRORS)
def ask(
    run_id: str,
    body: ChatRequest,
    manager: RunManager = Depends(get_manager),
    gate: ChatGate = Depends(get_gate),
) -> ChatReply:
    run = _available(manager, run_id)
    chats = _chats(manager)
    if _remaining(chats, run_id) == 0:
        raise ChatLimitError()
    with gate.turn(run_id):
        question = advisor_agent.user_message(body.message)
        logger.info("chat on run %s: question of %d characters", run_id, len(body.message))
        try:
            reply = advisor_agent.answer(run.result, body.message, chats.list(run_id))
        except LLMInvalidResponseError as exc:
            logger.warning("chat on run %s: no answer (%s)", run_id, type(exc).__name__)
            raise LLMInvalidResponseError(f"{exc.user_message} {MSG_REPHRASE}") from None
        except Exception as exc:
            logger.warning("chat on run %s: no answer (%s)", run_id, type(exc).__name__)
            raise
        if not chats.append(run_id, question, reply):
            raise RunNotFoundError()
    return ChatReply(message=reply, remaining_turns=_remaining(chats, run_id))


@router.delete("/{run_id}/chat", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def clear_chat(
    run_id: str,
    manager: RunManager = Depends(get_manager),
    gate: ChatGate = Depends(get_gate),
) -> Response:
    manager.get(run_id)
    gate.ensure_idle(run_id)
    cleared = _chats(manager).clear(run_id)
    logger.info("chat on run %s cleared (%d messages)", run_id, cleared)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

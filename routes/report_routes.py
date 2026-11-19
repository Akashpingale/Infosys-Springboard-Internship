import logging
import re
import threading
import time
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response, status

from agents.report_agent import build_report, report_fingerprint, report_source
from models.api import ErrorResponse, ReportRequest
from models.report import ReportDocument, ReportVersionError
from routes.chat_routes import ChatGate, get_gate
from routes.run_routes import get_manager
from utils.errors import ReportBusyError, ReportNotFoundError
from utils.report_render_md import render_report_md
from utils.report_render_pdf import render_report_pdf
from utils.run_manager import RunManager, report_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["report"])

FILE_PREFIX = "startup-validation"
SLUG_MAX = 40
SLUG_FALLBACK = "idea"
PDF_TYPE = "application/pdf"
MARKDOWN_TYPE = "text/markdown; charset=utf-8"
_NOT_SLUG = re.compile(r"[^a-z0-9]+")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _errors(*codes: int) -> dict[int | str, dict]:
    return {code: {"model": ErrorResponse} for code in codes}


class ReportGate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy: set[str] = set()

    def ensure_idle(self, run_id: str) -> None:
        with self._lock:
            if run_id in self._busy:
                raise ReportBusyError()

    @contextmanager
    def writing(self, run_id: str) -> Iterator[None]:
        with self._lock:
            if run_id in self._busy:
                raise ReportBusyError()
            self._busy.add(run_id)
        try:
            yield
        finally:
            with self._lock:
                self._busy.discard(run_id)


def get_report_gate(request: Request) -> ReportGate:
    return request.app.state.report_gate


def file_slug(title: str) -> str:
    text = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode("ascii").lower()
    slug = _NOT_SLUG.sub("-", text).strip("-")[:SLUG_MAX].strip("-")
    return slug or SLUG_FALLBACK


def file_date(generated_at: str) -> str:
    match = _DATE.match(generated_at or "")
    return match.group(0) if match else datetime.now(timezone.utc).date().isoformat()


def report_file_name(document: ReportDocument, extension: str) -> str:
    return f"{FILE_PREFIX}_{file_slug(document.meta.idea_title)}_{file_date(document.meta.generated_at)}.{extension}"


def _attachment(document: ReportDocument, extension: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{report_file_name(document, extension)}"'}


def _readable(row: dict) -> ReportDocument | None:
    try:
        return report_document(row)
    except ReportVersionError:
        return None


def _stored(manager: RunManager, run_id: str) -> ReportDocument:
    try:
        document = report_document(manager.report_row(run_id))
    except ReportVersionError as exc:
        raise ReportNotFoundError(str(exc)) from None
    if document is None:
        raise ReportNotFoundError()
    return document


@router.post("/{run_id}/report", response_model=ReportDocument, responses=_errors(404, 409, 422, 503))
def generate_report(
    run_id: str,
    body: ReportRequest | None = None,
    manager: RunManager = Depends(get_manager),
    gate: ReportGate = Depends(get_report_gate),
    chat_gate: ChatGate = Depends(get_gate),
) -> ReportDocument:
    options = body or ReportRequest()
    with gate.writing(run_id):
        run = manager.get(run_id)
        result = report_source(run)
        row = manager.report_row(run_id)
        if not options.force:
            current = _readable(row)
            if current is not None and row.get("report_fingerprint") == report_fingerprint(result, run.constraints):
                logger.info("report for run %s is current, so it was returned as stored", run_id)
                return current
        started = time.perf_counter()
        if options.narrative:
            with chat_gate.slot():
                document = build_report(run, narrative=True)
        else:
            document = build_report(run, narrative=False)
        manager.save_report(run_id, document)
        logger.info(
            "report for run %s written in %.2fs (narrative %s)",
            run_id,
            time.perf_counter() - started,
            document.meta.narrative_status,
        )
        return _stored(manager, run_id)


@router.get("/{run_id}/report", response_model=ReportDocument, responses=_errors(404, 503))
def read_report(run_id: str, manager: RunManager = Depends(get_manager)) -> ReportDocument:
    return _stored(manager, run_id)


@router.get(
    "/{run_id}/report/pdf",
    response_class=Response,
    responses={200: {"content": {PDF_TYPE: {}}}, **_errors(404, 422, 500, 503)},
)
def report_pdf(run_id: str, manager: RunManager = Depends(get_manager)) -> Response:
    document = _stored(manager, run_id)
    return Response(render_report_pdf(document), media_type=PDF_TYPE, headers=_attachment(document, "pdf"))


@router.get(
    "/{run_id}/report/markdown",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}}}, **_errors(404, 503)},
)
def report_markdown_file(run_id: str, manager: RunManager = Depends(get_manager)) -> Response:
    document = _stored(manager, run_id)
    return Response(render_report_md(document), media_type=MARKDOWN_TYPE, headers=_attachment(document, "md"))


@router.delete("/{run_id}/report", status_code=status.HTTP_204_NO_CONTENT, responses=_errors(404, 409, 503))
def delete_report(
    run_id: str,
    manager: RunManager = Depends(get_manager),
    gate: ReportGate = Depends(get_report_gate),
) -> Response:
    gate.ensure_idle(run_id)
    manager.clear_report(run_id)
    logger.info("report for run %s removed", run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

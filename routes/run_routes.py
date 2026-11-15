"""Background runs and their history (KIRO_UI_UPGRADE_SPEC.md Section 10.1).

POST /api/runs starts the full pipeline in the background and answers at once with a run id; the
interface then polls GET /api/runs/{id}. The existing POST /api/validate is untouched, so the
Streamlit UI and every Milestone 1 and 2 client keep working exactly as before.

The run manager lives on the application (app.state.run_manager), so tests can install their own.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import PlainTextResponse

from frontend.analysis_views import report_file_name, report_markdown
from models.api import ErrorResponse, RunDetail, RunList, RunRename, RunRequest, RunStarted, RunSummary
from utils.errors import ReportNotReadyError
from utils.run_manager import RunManager, default_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["runs"])

NOT_FOUND = {404: {"model": ErrorResponse}}
HISTORY = {503: {"model": ErrorResponse}}
MSG_NO_RESULT = "This validation produced no report."


def get_manager(request: Request) -> RunManager:
    """The application's run manager. Tests set `app.state.run_manager` to their own; otherwise the
    process-wide one is built on first use, so no database file appears until a run is started."""
    installed = getattr(request.app.state, "run_manager", None)
    return installed if installed is not None else default_manager()


@router.post(
    "",
    response_model=RunStarted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={409: {"model": ErrorResponse}, **HISTORY},
)
def start_run(body: RunRequest, manager: RunManager = Depends(get_manager)) -> RunStarted:
    """Start a run and answer immediately. With `idea_override`, the idea the founder reviewed is
    used and the extraction stage is not run again. With `include_strategy` (Milestone 3) the three
    strategy stages follow, using `constraints`. A third concurrent run is refused with 409."""
    run = manager.start(
        body.submission, body.idea_override, include_strategy=body.include_strategy, constraints=body.constraints
    )
    return RunStarted(run_id=run.id, state=run.state)


@router.get("", response_model=RunList, responses=HISTORY)
def list_runs(manager: RunManager = Depends(get_manager)) -> RunList:
    """Saved validations, newest first."""
    return RunList(runs=manager.list())


@router.get("/{run_id}", response_model=RunDetail, responses={**NOT_FOUND, **HISTORY})
def get_run(run_id: str, manager: RunManager = Depends(get_manager)) -> RunDetail:
    """A run's state, its stages and, once a stage has finished, the result so far."""
    return manager.get(run_id)


@router.post("/{run_id}/cancel", response_model=RunDetail, responses={**NOT_FOUND, **HISTORY})
def cancel_run(run_id: str, manager: RunManager = Depends(get_manager)) -> RunDetail:
    """Ask a run to stop. Cancelling is cooperative: the pipeline stops before its next stage or
    outside call, so a call already in flight finishes first and the state becomes `cancelled`
    only once the work has actually stopped."""
    return manager.cancel(run_id)


@router.patch("/{run_id}", response_model=RunSummary, responses={**NOT_FOUND, **HISTORY})
def rename_run(run_id: str, body: RunRename, manager: RunManager = Depends(get_manager)) -> RunSummary:
    """Rename a saved validation."""
    return manager.rename(run_id, body.title)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT, responses={**NOT_FOUND, **HISTORY,
                                                                              409: {"model": ErrorResponse}})
def delete_run(run_id: str, manager: RunManager = Depends(get_manager)) -> Response:
    """Delete a saved validation. A run that is still going must be cancelled first."""
    manager.delete(run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{run_id}/report.md",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/markdown": {}}}, 409: {"model": ErrorResponse}, **NOT_FOUND, **HISTORY},
)
def run_report(run_id: str, manager: RunManager = Depends(get_manager)) -> PlainTextResponse:
    """The Markdown report of a finished run, as a download. It is the full report even when both
    analyses are missing, so a partial or failed run still explains itself."""
    run = manager.get(run_id)
    if run.result is None:
        raise ReportNotReadyError()
    text = report_markdown(run.result, full=True)
    if not text.strip():
        raise ReportNotReadyError(MSG_NO_RESULT)
    return PlainTextResponse(
        text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{report_file_name(run.result)}"'},
    )

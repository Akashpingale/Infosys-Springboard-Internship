from fastapi import APIRouter, Depends, status

from models.api import ErrorResponse, RunStarted, StrategyRequest
from routes.run_routes import get_manager
from utils.run_manager import RunManager

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post(
    "/{run_id}/strategy",
    response_model=RunStarted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def start_strategy(run_id: str, body: StrategyRequest, manager: RunManager = Depends(get_manager)) -> RunStarted:
    run = manager.start_strategy(run_id, body.constraints, mode=body.mode)
    return RunStarted(run_id=run.id, state=run.state)

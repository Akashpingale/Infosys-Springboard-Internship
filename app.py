import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import setup_logging
from routes.health_routes import router as health_router
from routes.idea_routes import router as idea_router
from utils.errors import AppError, InputValidationError

logger = logging.getLogger(__name__)


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _describe_validation_errors(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err.get("loc", []) if p != "body") or "request"
        message = str(err.get("msg", "is not valid")).removeprefix("Value error, ")
        parts.append(f"{field}: {message}")
    return "; ".join(parts) or InputValidationError.default_message


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("%s on %s: %s", exc.code, request.url.path, exc.user_message)
    return JSONResponse(error_body(exc.code, exc.user_message), status_code=exc.status_code)


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.info("invalid input on %s (%d errors)", request.url.path, len(exc.errors()))
    return JSONResponse(
        error_body(InputValidationError.code, _describe_validation_errors(exc)),
        status_code=InputValidationError.status_code,
    )


async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        error_body(f"http_{exc.status_code}", str(exc.detail)), status_code=exc.status_code
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unexpected error on %s", request.url.path)
    return JSONResponse(
        error_body(AppError.code, AppError.default_message), status_code=AppError.status_code
    )


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="AI Startup Idea Validator", version="0.1.0")
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
    app.include_router(health_router)
    app.include_router(idea_router)
    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000)

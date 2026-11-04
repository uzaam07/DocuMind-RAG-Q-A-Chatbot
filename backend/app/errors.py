"""Application error types and the JSON error envelope."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_setup import get_logger

log = get_logger(__name__)

_STATUS_CODES = {
    400: "validation_error",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "not_found",
    409: "conflict",
    413: "validation_error",
    422: "validation_error",
    429: "rate_limited",
    503: "upstream_unavailable",
}


class AppError(Exception):
    """An error that maps to a specific HTTP status and envelope code."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class UpstreamError(AppError):
    """The model provider failed or is unreachable."""

    def __init__(self, message: str, status: int = 503, code: str = "upstream_unavailable") -> None:
        super().__init__(status, code, message)


def not_found(what: str) -> AppError:
    return AppError(404, "not_found", f"{what} was not found.")


def envelope(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def install_error_handlers(app: FastAPI) -> None:
    """Register handlers so every error uses the same JSON shape."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(envelope(exc.code, exc.message), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = str(first.get("msg", "Invalid request.")).removeprefix("Value error, ")
        text = f"{loc}: {msg}" if loc else msg
        return JSONResponse(envelope("validation_error", text), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "internal_error")
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        if exc.status_code == 404 and detail == "Not Found":
            detail = "That route does not exist."
        return JSONResponse(envelope(code, detail), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error: %s", type(exc).__name__)
        return JSONResponse(
            envelope("internal_error", "Something went wrong on the server. Try again."),
            status_code=500,
        )

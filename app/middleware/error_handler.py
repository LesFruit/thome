"""Unified error handler — consistent error envelopes, no traceback leakage."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
}


def _error_envelope(status_code: int, message: str, details: dict | None = None) -> dict:
    code = _STATUS_CODES.get(status_code, "error")
    envelope = {"error": {"code": code, "message": message}}
    if details:
        envelope["error"]["details"] = details
    return envelope


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(exc.status_code, str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        safe_errors = []
        for err in exc.errors():
            safe_errors.append(
                {
                    "field": ".".join(str(loc) for loc in err.get("loc", [])),
                    "message": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
            )
        return JSONResponse(
            status_code=422,
            content=_error_envelope(422, "Validation failed", {"fields": safe_errors}),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content=_error_envelope(500, "Internal server error"),
        )

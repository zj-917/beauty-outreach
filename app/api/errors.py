"""Exception handlers producing the unified error envelope."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, error_body
from app.core.logging import request_id_var

logger = logging.getLogger(__name__)

_HTTP_CODE_MAP = {
    401: "UNAUTHORIZED",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
}


def _validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        details.append(
            {
                "loc": list(error.get("loc", ())),
                "msg": error.get("msg", ""),
                "type": error.get("type", ""),
            }
        )
    return details


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_var.get() or ""


def _error_response(
    request: Request,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    response = JSONResponse(
        error_body(code, message, request_id, details),
        status_code=status_code,
    )
    response.headers["X-Request-ID"] = request_id
    return response


def register_exception_handlers(app: FastAPI) -> None:
    """Register handlers for business, validation, HTTP and unexpected errors."""

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(
            request, exc.code, exc.message, exc.status_code, exc.details
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request,
            "VALIDATION_ERROR",
            "Request validation failed",
            422,
            {"errors": _validation_details(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODE_MAP.get(exc.status_code, "INTERNAL_ERROR")
        return _error_response(request, code, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception")
        return _error_response(request, "INTERNAL_ERROR", "Internal server error", 500)

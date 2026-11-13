"""Unified application error types and the HTTP error envelope."""

from __future__ import annotations

from typing import Any

ERROR_HTTP_STATUS: dict[str, int] = {
    "VALIDATION_ERROR": 422,
    "UNAUTHORIZED": 401,
    "SIGNATURE_INVALID": 401,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "CAMPAIGN_INVALID_STATE": 409,
    "CAMPAIGN_EMPTY_TARGET": 422,
    "TEMPLATE_NOT_APPROVED": 422,
    "TEMPLATE_IMMUTABLE": 409,
    "TEMPLATE_UNKNOWN_VARIABLE": 422,
    "COMP_UNSUBSCRIBE_IMMUTABLE": 409,
    "CFG_LAST_RATE_RULE": 422,
    "LEAD_IMPORT_TOO_LARGE": 413,
    "PROVIDER_NOT_ENABLED": 501,
    "INTERNAL_ERROR": 500,
}


class AppError(Exception):
    """Business error carrying a stable code and HTTP status."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message or code
        self.status_code = ERROR_HTTP_STATUS.get(code, 500)
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource does not exist."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__("NOT_FOUND", message)


class UnauthorizedError(AppError):
    """Caller is not authenticated."""

    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__("UNAUTHORIZED", message)


class ConflictError(AppError):
    """Request conflicts with the current state."""

    def __init__(self, message: str = "Conflict") -> None:
        super().__init__("CONFLICT", message)


def error_body(
    code: str,
    message: str,
    request_id: str | None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the unified error envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id or "",
            "details": details or {},
        }
    }

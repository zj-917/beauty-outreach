"""Shared FastAPI dependencies."""

from __future__ import annotations

import re
from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.services.audit_service import AuditService

_OPERATOR_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,40}$")


def get_session(request: Request) -> Iterator[Session]:
    """Yield a session bound to the application engine."""
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_audit_service(request: Request) -> AuditService:
    """Return the application-wide audit service."""
    return request.app.state.audit_service


def get_operator(request: Request) -> str:
    """Return the validated X-Operator header, defaulting to admin."""
    value = request.headers.get("x-operator", "admin")
    if not _OPERATOR_RE.fullmatch(value):
        raise AppError(
            "VALIDATION_ERROR",
            "Invalid X-Operator header",
            details={"header": "X-Operator"},
        )
    return value

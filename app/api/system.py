"""System endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import APP_VERSION

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/healthz")
def healthz(request: Request) -> JSONResponse:
    """Report database, worker and version health."""
    db_status = "ok"
    try:
        with request.app.state.session_factory() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
        logger.warning("healthz database check failed")
    worker = getattr(request.app.state, "worker_status", "disabled")
    status = "ok" if db_status == "ok" else "error"
    return JSONResponse(
        {"status": status, "db": db_status, "worker": worker, "version": APP_VERSION},
        status_code=200 if db_status == "ok" else 503,
    )

"""Send log query endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_audit_service, get_session
from app.schemas.send_log import SendLogPage, SendLogView
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/send-logs", tags=["logs"])


@router.get("", response_model=SendLogPage)
def list_send_logs(
    session: Annotated[Session, Depends(get_session)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    task_id: int | None = None,
    item_id: int | None = None,
    phase: str | None = None,
    outcome: str | None = None,
    reason_code: str | None = None,
    from_ts: Annotated[datetime | None, Query(alias="from")] = None,
    to_ts: Annotated[datetime | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SendLogPage:
    """List send log rows with filters and pagination, newest first."""
    entries, total = audit.list_send_logs(
        session,
        task_id=task_id,
        item_id=item_id,
        phase=phase,
        outcome=outcome,
        reason_code=reason_code,
        from_ts=from_ts,
        to_ts=to_ts,
        page=page,
        page_size=page_size,
    )
    return SendLogPage(
        items=[SendLogView.model_validate(entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
    )

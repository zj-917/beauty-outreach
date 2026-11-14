"""Audit log query and verification endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_audit_service, get_session
from app.schemas.audit import AuditLogView, AuditPage, ChainVerification
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])


@router.get("", response_model=AuditPage)
def list_audit_logs(
    session: Annotated[Session, Depends(get_session)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    actor: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    from_ts: Annotated[datetime | None, Query(alias="from")] = None,
    to_ts: Annotated[datetime | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuditPage:
    """List audit records with filters and pagination, newest first."""
    entries, total = audit.list_logs(
        session,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        from_ts=from_ts,
        to_ts=to_ts,
        page=page,
        page_size=page_size,
    )
    return AuditPage(
        items=[AuditLogView.model_validate(entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/verify", response_model=ChainVerification, response_model_exclude_none=True)
def verify_audit_logs(
    session: Annotated[Session, Depends(get_session)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> ChainVerification:
    """Verify the audit hash chain and report the first broken row."""
    result = audit.verify_chain(session)
    return ChainVerification(
        ok=result.ok,
        count=result.count,
        first_broken_id=result.first_broken_id,
    )

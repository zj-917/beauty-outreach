"""Consent and suppression endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_operator, get_session
from app.schemas.compliance import (
    ConsentUpsert,
    ConsentView,
    SuppressionCreate,
    SuppressionView,
)
from app.services.compliance_service import ComplianceService

router = APIRouter(prefix="/api/v1", tags=["compliance"])


def _service(request: Request) -> ComplianceService:
    return ComplianceService(
        request.app.state.clock,
        request.app.state.phone_cipher,
        request.app.state.audit_service,
    )


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/consents", response_model=list[ConsentView])
def list_consents(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> list[ConsentView]:
    """Return all consent records with masked phone numbers."""
    entries = _service(request).list_consents(session)
    return [ConsentView.model_validate(entry) for entry in entries]


@router.put("/consents", response_model=ConsentView)
def upsert_consent(
    request: Request,
    payload: ConsentUpsert,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> ConsentView:
    """Insert or update consent for one phone number."""
    entry = _service(request).upsert_consent(
        session,
        phone=payload.phone,
        status=payload.status,
        source=payload.source,
        evidence_ref=payload.evidence_ref,
        operator=operator,
        request_id=_request_id(request),
    )
    return ConsentView.model_validate(entry)


@router.get("/suppressions", response_model=list[SuppressionView])
def list_suppressions(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    type: Literal["BLACKLIST", "UNSUBSCRIBE"] | None = None,
) -> list[SuppressionView]:
    """Return suppression entries, optionally filtered by type."""
    entries = _service(request).list_suppressions(session, type=type)
    return [SuppressionView.model_validate(entry) for entry in entries]


@router.post("/suppressions", response_model=SuppressionView, status_code=201)
def add_suppression(
    request: Request,
    payload: SuppressionCreate,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> SuppressionView:
    """Add a blacklist or unsubscribe entry; duplicates are idempotent."""
    entry = _service(request).add_suppression(
        session,
        type=payload.type,
        phone=payload.phone,
        username=payload.username,
        reason=payload.reason,
        source="MANUAL",
        operator=operator,
        request_id=_request_id(request),
    )
    return SuppressionView.model_validate(entry)


@router.delete("/suppressions/{suppression_id}", status_code=204)
def remove_suppression(
    request: Request,
    suppression_id: int,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> Response:
    """Delete a blacklist entry; unsubscribe entries cannot be removed."""
    _service(request).remove_suppression(
        session,
        suppression_id,
        operator=operator,
        request_id=_request_id(request),
    )
    return Response(status_code=204)

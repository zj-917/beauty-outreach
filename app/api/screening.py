"""Screening endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_operator, get_session
from app.schemas.screening import ScreeningRequest, ScreeningResult
from app.services.screening_service import ScreeningService

router = APIRouter(prefix="/api/v1", tags=["screening"])


@router.post("/leads/screen", response_model=ScreeningResult)
def screen_leads(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
    payload: ScreeningRequest | None = None,
) -> ScreeningResult:
    """Score and decide leads, optionally scoped to a batch or explicit ids."""
    report = ScreeningService(request.app.state.clock).run(
        session,
        batch_id=payload.batch_id if payload else None,
        lead_ids=payload.lead_ids if payload else None,
        operator=operator,
        request_id=getattr(request.state, "request_id", None),
    )
    return ScreeningResult(
        processed=report.processed,
        approved=report.approved,
        pending_review=report.pending_review,
        discarded=report.discarded,
        unchanged=report.unchanged,
        warning=report.warning,
    )

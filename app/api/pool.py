"""Goal pool and manual review endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_operator, get_session
from app.schemas.lead import LeadView
from app.schemas.pool import (
    BulkReviewError,
    BulkReviewItemResult,
    BulkReviewRequest,
    BulkReviewResponse,
    PoolPage,
    ReviewRequest,
)
from app.services.pool_service import PoolService, ReviewCommand

router = APIRouter(prefix="/api/v1", tags=["pool"])


def _service(request: Request) -> PoolService:
    return PoolService(request.app.state.clock, request.app.state.audit_service)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/pool", response_model=PoolPage)
def list_pool(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PoolPage:
    """Return one page of approved leads, highest score first."""
    entries, total = _service(request).list_pool(
        session, page=page, page_size=page_size
    )
    return PoolPage(
        items=[LeadView.model_validate(entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/leads/{lead_id}/review", response_model=LeadView)
def review_lead(
    request: Request,
    lead_id: int,
    payload: ReviewRequest,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> LeadView:
    """Apply one manual approve or reject decision."""
    lead = _service(request).review(
        session,
        lead_id,
        decision=payload.decision,
        note=payload.note,
        operator=operator,
        request_id=_request_id(request),
    )
    return LeadView.model_validate(lead)


@router.post(
    "/leads/review-bulk",
    response_model=BulkReviewResponse,
    response_model_exclude_none=True,
)
def review_lead_bulk(
    request: Request,
    payload: BulkReviewRequest,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> BulkReviewResponse:
    """Apply up to 200 independent decisions and report each outcome."""
    outcomes = _service(request).review_bulk(
        session,
        [
            ReviewCommand(
                lead_id=item.lead_id, decision=item.decision, note=item.note
            )
            for item in payload.reviews
        ],
        operator=operator,
        request_id=_request_id(request),
    )
    results = []
    for outcome in outcomes:
        error = None
        if outcome.error_code is not None:
            error = BulkReviewError(
                code=outcome.error_code, message=outcome.error_message or ""
            )
        results.append(
            BulkReviewItemResult(
                lead_id=outcome.lead_id, ok=outcome.ok, error=error
            )
        )
    return BulkReviewResponse(results=results)

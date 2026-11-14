"""Lead batch import and lead query endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_operator, get_session
from app.core.errors import AppError
from app.schemas.lead import BatchPage, BatchView, LeadPage, LeadView
from app.services.lead_service import LeadService

router = APIRouter(prefix="/api/v1", tags=["leads"])


def _service(request: Request) -> LeadService:
    return LeadService(
        request.app.state.clock,
        request.app.state.phone_cipher,
        request.app.state.audit_service,
    )


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def _source_from_request(request: Request):
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise AppError("VALIDATION_ERROR", "multipart upload requires a file field")
        content = await upload.read()
        return LeadService.source_from_upload(upload.filename or "upload", content)
    try:
        body: Any = await request.json()
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", "request body must be JSON") from exc
    source_name = body.get("source") if isinstance(body, dict) else None
    return LeadService.source_by_name(source_name)


@router.post("/lead-batches/import", response_model=BatchView, status_code=201)
async def import_lead_batch(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> BatchView:
    """Import leads from the mock dataset or an uploaded CSV/JSON file."""
    source = await _source_from_request(request)
    batch = _service(request).import_batch(
        session, source, operator=operator, request_id=_request_id(request)
    )
    return BatchView.model_validate(batch)


@router.get("/lead-batches", response_model=BatchPage)
def list_lead_batches(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BatchPage:
    """List import batches, newest first."""
    entries, total = _service(request).list_batches(
        session, page=page, page_size=page_size
    )
    return BatchPage(
        items=[BatchView.model_validate(entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/lead-batches/{batch_id}", response_model=BatchView)
def get_lead_batch(
    request: Request,
    batch_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> BatchView:
    """Return one batch with its full import report."""
    return BatchView.model_validate(_service(request).get_batch(session, batch_id))


@router.get("/leads", response_model=LeadPage)
def list_leads(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    status: str | None = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    batch_id: int | None = None,
    q: str | None = None,
    region: str | None = None,
    language: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LeadPage:
    """List leads with optional filters and pagination."""
    entries, total = _service(request).list_leads(
        session,
        status=status,
        min_score=min_score,
        batch_id=batch_id,
        q=q,
        region=region,
        language=language,
        page=page,
        page_size=page_size,
    )
    return LeadPage(
        items=[LeadView.model_validate(entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/leads/{lead_id}", response_model=LeadView)
def get_lead(
    request: Request,
    lead_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> LeadView:
    """Return one lead with its masked phone only."""
    return LeadView.model_validate(_service(request).get_lead(session, lead_id))

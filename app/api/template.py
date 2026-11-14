"""Template management, versioning, approval and preview endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_operator, get_session
from app.schemas.template import (
    TemplateCreate,
    TemplateNewVersion,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateUpdate,
    TemplateView,
)
from app.services.template_service import TemplateService

router = APIRouter(prefix="/api/v1", tags=["templates"])


def _service(request: Request) -> TemplateService:
    return TemplateService(request.app.state.clock, request.app.state.audit_service)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/templates", response_model=list[TemplateView])
def list_templates(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> list[TemplateView]:
    """Return all template versions."""
    entries = _service(request).list_templates(session)
    return [TemplateView.model_validate(entry) for entry in entries]


@router.post("/templates", response_model=TemplateView, status_code=201)
def create_template(
    request: Request,
    payload: TemplateCreate,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> TemplateView:
    """Create version 1 of a template in DRAFT."""
    entry = _service(request).create(
        session,
        name=payload.name,
        body=payload.body,
        language=payload.language,
        operator=operator,
        request_id=_request_id(request),
    )
    return TemplateView.model_validate(entry)


@router.post("/templates/preview", response_model=TemplatePreviewResponse)
def preview_template(
    request: Request,
    payload: TemplatePreviewRequest,
    session: Annotated[Session, Depends(get_session)],
) -> TemplatePreviewResponse:
    """Render a body or stored template without side effects."""
    rendered = _service(request).preview(
        session,
        body=payload.body,
        template_id=payload.template_id,
        lead_id=payload.lead_id,
    )
    return TemplatePreviewResponse(rendered=rendered)


@router.get("/templates/{template_id}", response_model=TemplateView)
def get_template(
    request: Request,
    template_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> TemplateView:
    """Return one template version."""
    return TemplateView.model_validate(_service(request).get_template(session, template_id))


@router.patch("/templates/{template_id}", response_model=TemplateView)
def update_template(
    request: Request,
    template_id: int,
    payload: TemplateUpdate,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> TemplateView:
    """Edit a DRAFT template; approved and disabled templates are immutable."""
    entry = _service(request).update(
        session,
        template_id,
        body=payload.body,
        language=payload.language,
        operator=operator,
        request_id=_request_id(request),
    )
    return TemplateView.model_validate(entry)


@router.post(
    "/templates/{template_id}/new-version",
    response_model=TemplateView,
    status_code=201,
)
def create_new_version(
    request: Request,
    template_id: int,
    payload: TemplateNewVersion,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> TemplateView:
    """Create a DRAFT version+1 from an existing template."""
    entry = _service(request).new_version(
        session,
        template_id,
        body=payload.body,
        operator=operator,
        request_id=_request_id(request),
    )
    return TemplateView.model_validate(entry)


@router.post("/templates/{template_id}/approve", response_model=TemplateView)
def approve_template(
    request: Request,
    template_id: int,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> TemplateView:
    """Approve a DRAFT template."""
    entry = _service(request).approve(
        session,
        template_id,
        operator=operator,
        request_id=_request_id(request),
    )
    return TemplateView.model_validate(entry)


@router.post("/templates/{template_id}/disable", response_model=TemplateView)
def disable_template(
    request: Request,
    template_id: int,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> TemplateView:
    """Disable a template; repeating the call is a no-op."""
    entry = _service(request).disable(
        session,
        template_id,
        operator=operator,
        request_id=_request_id(request),
    )
    return TemplateView.model_validate(entry)

"""Campaign creation, control and query endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_operator, get_session
from app.schemas.campaign import (
    CampaignControlResponse,
    CampaignCounts,
    CampaignCreate,
    CampaignItemPage,
    CampaignItemView,
    CampaignPage,
    CampaignPreviewResponse,
    CampaignTimelineResponse,
    CampaignView,
    TimelineEvent,
)
from app.services.campaign_service import CampaignReport, CampaignService

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


def _service(request: Request) -> CampaignService:
    return CampaignService(
        request.app.state.clock,
        request.app.state.phone_cipher,
        request.app.state.audit_service,
    )


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _view(report: CampaignReport) -> CampaignView:
    campaign = report.campaign
    return CampaignView(
        id=campaign.id,
        name=campaign.name,
        template_id=campaign.template_id,
        status=campaign.status,
        selection=campaign.selection,
        total_items=campaign.total_items,
        pause_reason=campaign.pause_reason,
        consecutive_failures=campaign.consecutive_failures,
        created_by=campaign.created_by,
        created_at=campaign.created_at,
        started_at=campaign.started_at,
        paused_at=campaign.paused_at,
        finished_at=campaign.finished_at,
        counts=CampaignCounts(**report.counts),
    )


@router.post("", response_model=CampaignView, status_code=201)
def create_campaign(
    request: Request,
    payload: CampaignCreate,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> CampaignView:
    """Create a DRAFT campaign and snapshot its targets from the pool."""
    report = _service(request).create(
        session,
        name=payload.name,
        template_id=payload.template_id,
        min_score=payload.selection.min_score,
        batch_id=payload.selection.batch_id,
        lead_ids=payload.selection.lead_ids,
        operator=operator,
        request_id=_request_id(request),
    )
    return _view(report)


@router.get("", response_model=CampaignPage)
def list_campaigns(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CampaignPage:
    """Return one page of campaigns with summary counts, newest first."""
    reports, total = _service(request).list_campaigns(
        session, page=page, page_size=page_size
    )
    return CampaignPage(
        items=[_view(report) for report in reports],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{campaign_id}", response_model=CampaignView)
def get_campaign(
    request: Request,
    campaign_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> CampaignView:
    """Return one campaign with its summary counts."""
    return _view(_service(request).get_campaign(session, campaign_id))


@router.get("/{campaign_id}/timeline", response_model=CampaignTimelineResponse)
def campaign_timeline(
    request: Request,
    campaign_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> CampaignTimelineResponse:
    """Return the campaign's lifecycle events in ascending time order."""
    entries = _service(request).timeline(session, campaign_id)
    return CampaignTimelineResponse(
        task_id=campaign_id,
        events=[
            TimelineEvent(
                id=entry.id,
                ts=entry.ts,
                event=entry.action.removeprefix("CAMPAIGN_"),
                actor=entry.actor,
                request_id=entry.request_id,
                before=entry.before,
                after=entry.after,
            )
            for entry in entries
        ],
    )


@router.get("/{campaign_id}/items", response_model=CampaignItemPage)
def list_campaign_items(
    request: Request,
    campaign_id: int,
    session: Annotated[Session, Depends(get_session)],
    status: str | None = None,
    reason_code: str | None = None,
    q: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CampaignItemPage:
    """Return one page of task items with status, reason and text filters."""
    items, total = _service(request).list_items(
        session,
        campaign_id,
        status=status,
        reason_code=reason_code,
        q=q,
        page=page,
        page_size=page_size,
    )
    return CampaignItemPage(
        items=[CampaignItemView.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{campaign_id}/preview", response_model=CampaignPreviewResponse)
def preview_campaign(
    request: Request,
    campaign_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> CampaignPreviewResponse:
    """Dry-run gates 1-7 without writing logs, changing items or calling the provider."""
    report = _service(request).preview(session, campaign_id)
    return CampaignPreviewResponse(
        task_id=report.task_id,
        total_items=report.total_items,
        will_attempt=report.will_attempt,
        will_release=report.will_release,
        will_skip=report.will_skip,
    )


@router.post("/{campaign_id}/start", response_model=CampaignControlResponse)
def start_campaign(
    request: Request,
    campaign_id: int,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> CampaignControlResponse:
    """Start a draft campaign after the template, item and provider prechecks."""
    campaign = _service(request).start(
        session,
        campaign_id,
        operator=operator,
        provider_available=request.app.state.settings.messenger_provider == "mock",
        request_id=_request_id(request),
    )
    return CampaignControlResponse(id=campaign.id, status=campaign.status)


@router.post("/{campaign_id}/pause", response_model=CampaignControlResponse)
def pause_campaign(
    request: Request,
    campaign_id: int,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> CampaignControlResponse:
    """Pause a running campaign."""
    campaign = _service(request).pause(
        session, campaign_id, operator=operator, request_id=_request_id(request)
    )
    return CampaignControlResponse(id=campaign.id, status=campaign.status)


@router.post("/{campaign_id}/resume", response_model=CampaignControlResponse)
def resume_campaign(
    request: Request,
    campaign_id: int,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> CampaignControlResponse:
    """Resume a paused campaign and reset its failure streak."""
    campaign = _service(request).resume(
        session, campaign_id, operator=operator, request_id=_request_id(request)
    )
    return CampaignControlResponse(id=campaign.id, status=campaign.status)


@router.post("/{campaign_id}/cancel", response_model=CampaignControlResponse)
def cancel_campaign(
    request: Request,
    campaign_id: int,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> CampaignControlResponse:
    """Cancel a non-terminal campaign and skip its open items."""
    campaign = _service(request).cancel(
        session, campaign_id, operator=operator, request_id=_request_id(request)
    )
    return CampaignControlResponse(id=campaign.id, status=campaign.status)

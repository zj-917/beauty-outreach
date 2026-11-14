"""Global statistics endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas.stats import OverviewView
from app.services.stats_service import StatsService

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("/overview", response_model=OverviewView)
def stats_overview(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> OverviewView:
    """Return live system-wide counts computed in one read transaction."""
    overview = StatsService(request.app.state.clock).overview(session)
    return OverviewView.model_validate(overview)

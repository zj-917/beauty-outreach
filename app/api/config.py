"""Configuration management endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_operator, get_session
from app.schemas.config import (
    KeywordCreate,
    KeywordUpdate,
    KeywordView,
    RateRuleCreate,
    RateRuleUpdate,
    RateRuleView,
    SettingsUpdate,
)
from app.services.config_service import ConfigService

router = APIRouter(prefix="/api/v1", tags=["config"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/keywords", response_model=list[KeywordView])
def list_keywords(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> list[KeywordView]:
    """Return all keywords."""
    entries = ConfigService(request.app.state.clock).list_keywords(session)
    return [KeywordView.model_validate(entry) for entry in entries]


@router.post("/keywords", response_model=KeywordView, status_code=201)
def create_keyword(
    request: Request,
    payload: KeywordCreate,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> KeywordView:
    """Create a keyword after normalization."""
    entry = ConfigService(request.app.state.clock).create_keyword(
        session,
        term=payload.term,
        kind=payload.kind,
        weight=payload.weight,
        enabled=payload.enabled,
        actor=operator,
        request_id=_request_id(request),
    )
    return KeywordView.model_validate(entry)


@router.patch("/keywords/{keyword_id}", response_model=KeywordView)
def update_keyword(
    request: Request,
    keyword_id: int,
    payload: KeywordUpdate,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> KeywordView:
    """Update a keyword's weight or enabled state."""
    entry = ConfigService(request.app.state.clock).update_keyword(
        session,
        keyword_id,
        weight=payload.weight,
        enabled=payload.enabled,
        actor=operator,
        request_id=_request_id(request),
    )
    return KeywordView.model_validate(entry)


@router.delete("/keywords/{keyword_id}", status_code=204)
def delete_keyword(
    request: Request,
    keyword_id: int,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> Response:
    """Delete a keyword."""
    ConfigService(request.app.state.clock).delete_keyword(
        session,
        keyword_id,
        actor=operator,
        request_id=_request_id(request),
    )
    return Response(status_code=204)


@router.get("/rate-rules", response_model=list[RateRuleView])
def list_rate_rules(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> list[RateRuleView]:
    """Return all rate rules."""
    entries = ConfigService(request.app.state.clock).list_rate_rules(session)
    return [RateRuleView.model_validate(entry) for entry in entries]


@router.post("/rate-rules", response_model=RateRuleView, status_code=201)
def create_rate_rule(
    request: Request,
    payload: RateRuleCreate,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> RateRuleView:
    """Create a rate rule."""
    entry = ConfigService(request.app.state.clock).create_rate_rule(
        session,
        name=payload.name,
        scope=payload.scope,
        window_seconds=payload.window_seconds,
        max_count=payload.max_count,
        enabled=payload.enabled,
        actor=operator,
        request_id=_request_id(request),
    )
    return RateRuleView.model_validate(entry)


@router.patch("/rate-rules/{rule_id}", response_model=RateRuleView)
def update_rate_rule(
    request: Request,
    rule_id: int,
    payload: RateRuleUpdate,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> RateRuleView:
    """Update a rate rule."""
    entry = ConfigService(request.app.state.clock).update_rate_rule(
        session,
        rule_id,
        name=payload.name,
        scope=payload.scope,
        window_seconds=payload.window_seconds,
        max_count=payload.max_count,
        enabled=payload.enabled,
        actor=operator,
        request_id=_request_id(request),
    )
    return RateRuleView.model_validate(entry)


@router.delete("/rate-rules/{rule_id}", status_code=204)
def delete_rate_rule(
    request: Request,
    rule_id: int,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> Response:
    """Delete a rate rule unless it is the last enabled one in its scope."""
    ConfigService(request.app.state.clock).delete_rate_rule(
        session,
        rule_id,
        actor=operator,
        request_id=_request_id(request),
    )
    return Response(status_code=204)


@router.get("/settings")
def get_settings(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, Any]:
    """Return all runtime settings merged with registry defaults."""
    return ConfigService(request.app.state.clock).get_settings(session)


@router.put("/settings")
def update_settings(
    request: Request,
    payload: SettingsUpdate,
    session: Annotated[Session, Depends(get_session)],
    operator: Annotated[str, Depends(get_operator)],
) -> dict[str, Any]:
    """Apply a partial runtime settings update atomically."""
    return ConfigService(request.app.state.clock).update_settings(
        session,
        payload.root,
        actor=operator,
        request_id=_request_id(request),
    )

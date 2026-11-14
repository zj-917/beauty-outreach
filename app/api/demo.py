"""Demo-only helper endpoints (AC-SYS-012)."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.api.webhook import process_inbound
from app.core.errors import AppError
from app.core.security import sign_webhook_payload, verify_admin_token
from app.schemas.common import iso_z
from app.schemas.webhook import (
    DemoFlushResponse,
    DemoInboundStopRequest,
    DemoResetResponse,
    InboundWebhookResponse,
)
from app.services.demo_service import DemoService
from app.services.receipt_service import ReceiptService

router = APIRouter(prefix="/demo", tags=["demo"])


def _require_token(request: Request) -> None:
    settings = request.app.state.settings
    provided = request.headers.get("x-admin-token")
    if not verify_admin_token(provided, settings.admin_token):
        raise AppError("UNAUTHORIZED", "Invalid or missing admin token")


@router.post("/inbound-stop", response_model=InboundWebhookResponse)
def demo_inbound_stop(
    request: Request,
    payload: DemoInboundStopRequest,
    session: Annotated[Session, Depends(get_session)],
) -> InboundWebhookResponse:
    """Sign an inbound STOP server-side and run the real webhook path."""
    _require_token(request)
    clock = request.app.state.clock
    raw = json.dumps(
        {
            "from": payload.phone,
            "text": payload.text,
            "timestamp": iso_z(clock.now()),
        }
    ).encode()
    signature = sign_webhook_payload(
        request.app.state.settings.webhook_secret, raw
    )
    action = process_inbound(
        request,
        session,
        raw=raw,
        signature=signature,
        request_id=getattr(request.state, "request_id", None),
    )
    return InboundWebhookResponse(action=action)


@router.post("/flush-receipts", response_model=DemoFlushResponse)
def demo_flush_receipts(request: Request) -> DemoFlushResponse:
    """Apply every queued mock receipt immediately."""
    _require_token(request)
    messenger = request.app.state.messenger
    if messenger is None:
        return DemoFlushResponse(applied=0)
    service = ReceiptService(
        request.app.state.clock,
        messenger=messenger,
        session_factory=request.app.state.session_factory,
    )
    return DemoFlushResponse(applied=service.flush_and_apply())


@router.post("/reset", response_model=DemoResetResponse)
def demo_reset(request: Request) -> DemoResetResponse:
    """Drop every table, recreate the schema and reseed the defaults."""
    _require_token(request)
    counts = DemoService(request.app.state.clock).reset(
        request.app.state.engine, request.app.state.session_factory
    )
    return DemoResetResponse(status="reset", counts=counts)

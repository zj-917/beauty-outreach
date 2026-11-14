"""Signed provider webhooks for delivery receipts and inbound messages."""

from __future__ import annotations

import logging
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.errors import AppError
from app.core.security import verify_webhook_signature
from app.schemas.webhook import (
    InboundPayload,
    InboundWebhookResponse,
    StatusReceiptPayload,
    StatusWebhookResponse,
)
from app.services.compliance_service import ComplianceService
from app.services.receipt_service import ReceiptService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

ModelT = TypeVar("ModelT", bound=BaseModel)


def _require_signature(secret: str, raw: bytes, signature: str | None) -> None:
    if not verify_webhook_signature(secret, raw, signature):
        raise AppError("SIGNATURE_INVALID", "Invalid or missing webhook signature")


def _parse(model: type[ModelT], raw: bytes) -> ModelT:
    try:
        return model.model_validate_json(raw)
    except ValidationError as exc:
        details = [
            {
                "loc": list(error.get("loc", ())),
                "msg": error.get("msg", ""),
                "type": error.get("type", ""),
            }
            for error in exc.errors(include_url=False)
        ]
        raise AppError(
            "VALIDATION_ERROR",
            "Webhook payload validation failed",
            details={"errors": details},
        ) from exc


def process_inbound(
    request: Request,
    session: Session,
    *,
    raw: bytes,
    signature: str | None,
    request_id: str | None,
) -> str:
    """Verify, parse and handle one inbound payload; shared with the demo endpoint."""
    app = request.app
    _require_signature(app.state.settings.webhook_secret, raw, signature)
    payload = _parse(InboundPayload, raw)
    service = ComplianceService(
        app.state.clock, app.state.phone_cipher, app.state.audit_service
    )
    return service.handle_inbound(
        session,
        from_phone=payload.from_phone,
        text=payload.text,
        request_id=request_id,
    )


@router.post("/whatsapp/status", response_model=StatusWebhookResponse)
async def whatsapp_status(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> StatusWebhookResponse:
    """Apply one delivery receipt after verifying the signature."""
    raw = await request.body()
    _require_signature(
        request.app.state.settings.webhook_secret,
        raw,
        request.headers.get("x-hub-signature-256"),
    )
    payload = _parse(StatusReceiptPayload, raw)
    receipt_service = ReceiptService(request.app.state.clock)
    applied = receipt_service.apply(
        session,
        provider_message_id=payload.provider_message_id,
        status=payload.status,
        error_code=payload.error.code if payload.error else None,
        error_message=payload.error.message if payload.error else None,
        timestamp=payload.timestamp,
    )
    return StatusWebhookResponse(applied=applied)


@router.post("/whatsapp/inbound", response_model=InboundWebhookResponse)
async def whatsapp_inbound(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> InboundWebhookResponse:
    """Handle one inbound message and detect stop keywords."""
    raw = await request.body()
    action = process_inbound(
        request,
        session,
        raw=raw,
        signature=request.headers.get("x-hub-signature-256"),
        request_id=getattr(request.state, "request_id", None),
    )
    return InboundWebhookResponse(action=action)

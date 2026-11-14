"""Payloads and responses for signed webhooks and demo helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReceiptError(BaseModel):
    """Provider error block inside a failed status receipt."""

    model_config = ConfigDict(extra="ignore")

    code: str | None = None
    message: str | None = None


class StatusReceiptPayload(BaseModel):
    """One delivery status callback from the provider."""

    model_config = ConfigDict(extra="ignore")

    provider_message_id: str
    status: Literal["delivered", "read", "failed"]
    timestamp: datetime | None = None
    error: ReceiptError | None = None


class StatusWebhookResponse(BaseModel):
    """Whether the receipt changed the item."""

    applied: bool


class InboundPayload(BaseModel):
    """One inbound message callback from the provider."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    from_phone: str = Field(alias="from")
    text: str
    timestamp: datetime | None = None


class InboundWebhookResponse(BaseModel):
    """Result of stop-keyword detection."""

    action: Literal["UNSUBSCRIBED", "IGNORED"]


class DemoInboundStopRequest(BaseModel):
    """Server-side signed inbound STOP for the demo endpoints."""

    model_config = ConfigDict(extra="forbid")

    phone: str
    text: str = "STOP"


class DemoFlushResponse(BaseModel):
    """Number of queued receipts that were applied."""

    applied: int


class DemoResetResponse(BaseModel):
    """Result of clearing and reseeding the demo database."""

    status: str
    counts: dict[str, int]

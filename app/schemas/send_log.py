"""API schemas for send log queries."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UtcDatetime


class SendLogView(BaseModel):
    """One send log row; only the masked phone is exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    item_id: int
    phase: str
    outcome: str
    reason_code: str | None = None
    attempt_no: int | None = None
    provider_message_id: str | None = None
    latency_ms: int | None = None
    detail: dict[str, Any] | None = None
    phone_masked: str | None = None
    created_at: UtcDatetime


class SendLogPage(BaseModel):
    """Paginated send log response, newest first."""

    items: list[SendLogView]
    total: int
    page: int
    page_size: int

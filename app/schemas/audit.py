"""API schemas for audit log queries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer

from app.schemas.common import iso_z


class AuditLogView(BaseModel):
    """One audit record with a Z-suffixed timestamp."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    actor: str
    action: str
    entity_type: str
    entity_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    request_id: str | None = None

    @field_serializer("ts")
    def serialize_ts(self, value: datetime) -> str:
        return iso_z(value)


class AuditPage(BaseModel):
    """Paginated audit log response."""

    items: list[AuditLogView]
    total: int
    page: int
    page_size: int


class ChainVerification(BaseModel):
    """Result of GET /audit-logs/verify."""

    ok: bool
    count: int | None = None
    first_broken_id: int | None = None

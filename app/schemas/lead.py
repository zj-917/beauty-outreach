"""API schemas for lead batches and leads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UtcDatetime


class BatchView(BaseModel):
    """One import batch and its report."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    source_name: str
    total_rows: int
    imported: int
    duplicates: int
    invalid: int
    warnings: int
    errors: list[dict[str, Any]]
    created_by: str
    created_at: UtcDatetime


class BatchPage(BaseModel):
    """Paginated import batch list."""

    items: list[BatchView]
    total: int
    page: int
    page_size: int


class LeadView(BaseModel):
    """Lead exposed to the API; only the masked phone is returned."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    username: str
    display_name: str | None = None
    bio: str | None = None
    region: str | None = None
    language: str | None = None
    source_url: str | None = None
    phone_masked: str | None = None
    status: str
    score: int | None = None
    score_reasons: list[Any] | None = None
    top_keyword: str | None = None
    decision_source: str | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class LeadPage(BaseModel):
    """Paginated lead list."""

    items: list[LeadView]
    total: int
    page: int
    page_size: int

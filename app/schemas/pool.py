"""API schemas for the goal pool and manual reviews."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.schemas.lead import LeadView


class ReviewRequest(BaseModel):
    """Decision and optional note for one lead review."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["APPROVE", "REJECT"]
    note: str | None = None


class BulkReviewItem(BaseModel):
    """One per-lead decision inside a bulk review."""

    model_config = ConfigDict(extra="forbid")

    lead_id: StrictInt
    decision: Literal["APPROVE", "REJECT"]
    note: str | None = None


class BulkReviewRequest(BaseModel):
    """Up to 200 independent lead reviews."""

    model_config = ConfigDict(extra="forbid")

    reviews: list[BulkReviewItem] = Field(max_length=200)


class BulkReviewError(BaseModel):
    """Why one bulk review item failed."""

    code: str
    message: str


class BulkReviewItemResult(BaseModel):
    """Outcome of one bulk review item."""

    lead_id: int
    ok: bool
    error: BulkReviewError | None = None


class BulkReviewResponse(BaseModel):
    """Per-item outcomes of a bulk review."""

    results: list[BulkReviewItemResult]


class PoolPage(BaseModel):
    """Paginated approved-lead pool."""

    items: list[LeadView]
    total: int
    page: int
    page_size: int

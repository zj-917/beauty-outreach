"""Request and response schemas for campaign endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.schemas.common import UtcDatetime


class Selection(BaseModel):
    """Target-pool filters; conditions are intersected."""

    model_config = ConfigDict(extra="forbid")

    min_score: StrictInt | None = Field(default=None, ge=0, le=100)
    batch_id: StrictInt | None = None
    lead_ids: list[StrictInt] | None = Field(default=None, max_length=500)


class CampaignCreate(BaseModel):
    """Create a campaign and snapshot its targets from the pool."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    template_id: StrictInt
    selection: Selection = Field(default_factory=Selection)


class CampaignCounts(BaseModel):
    """Item status summary for one campaign."""

    total: int
    success: int
    failed: int
    skipped: int
    in_progress: int
    by_status: dict[str, int]


class CampaignView(BaseModel):
    """Campaign task with its summary counts."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    template_id: int
    status: str
    selection: dict[str, Any]
    total_items: int
    pause_reason: str | None = None
    consecutive_failures: int
    created_by: str
    created_at: UtcDatetime
    started_at: UtcDatetime | None = None
    paused_at: UtcDatetime | None = None
    finished_at: UtcDatetime | None = None
    counts: CampaignCounts


class CampaignPage(BaseModel):
    """Paginated campaign list, newest first."""

    items: list[CampaignView]
    total: int
    page: int
    page_size: int


class CampaignControlResponse(BaseModel):
    """Result of one state transition."""

    id: int
    status: str


class CampaignPreviewResponse(BaseModel):
    """Dry-run distribution of gates 1-7 over the open items."""

    task_id: int
    total_items: int
    will_attempt: int
    will_release: int
    will_skip: dict[str, int]
    note: str = "Rate-limit deferrals and quiet hours are not simulated"


class TimelineEvent(BaseModel):
    """One CAMPAIGN_* audit event with the action prefix removed."""

    id: int
    ts: UtcDatetime
    event: str
    actor: str
    request_id: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class CampaignTimelineResponse(BaseModel):
    """Campaign lifecycle events in ascending time order."""

    task_id: int
    events: list[TimelineEvent]


class CampaignItemView(BaseModel):
    """One task item; the full phone and rendered body are never exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    lead_id: int
    lead_username: str | None = None
    phone_masked: str | None = None
    status: str
    reason_code: str | None = None
    attempts: int
    next_attempt_at: UtcDatetime | None = None
    provider_message_id: str | None = None
    last_error_code: str | None = None
    sent_at: UtcDatetime | None = None
    delivered_at: UtcDatetime | None = None
    read_at: UtcDatetime | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class CampaignItemPage(BaseModel):
    """Paginated task item list."""

    items: list[CampaignItemView]
    total: int
    page: int
    page_size: int

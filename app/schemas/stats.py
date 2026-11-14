"""Response schemas for the statistics endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UtcDatetime


class TaskStatsView(BaseModel):
    """Result statistics of one campaign (§7 of the config-stats spec)."""

    model_config = ConfigDict(from_attributes=True)

    task_id: int
    status: str
    total: int
    by_status: dict[str, int]
    success: int
    failed: int
    skipped: int
    in_progress: int
    success_rate: float | None = None
    skip_reasons: dict[str, int]
    failure_reasons: dict[str, int]
    attempts_histogram: dict[int, int]
    retry_total: int
    started_at: UtcDatetime | None = None
    finished_at: UtcDatetime | None = None
    elapsed_seconds: float | None = None


class OverviewView(BaseModel):
    """Global dashboard counts."""

    model_config = ConfigDict(from_attributes=True)

    leads_by_status: dict[str, int]
    pool_size: int
    campaigns_by_status: dict[str, int]
    accepted_last_24h: int
    suppressions_by_type: dict[str, int]
    consents_by_status: dict[str, int]

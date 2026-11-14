"""API schemas for screening runs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, StrictInt


class ScreeningRequest(BaseModel):
    """Optional scope of a screening run."""

    model_config = ConfigDict(extra="forbid")

    batch_id: StrictInt | None = None
    lead_ids: list[StrictInt] | None = None


class ScreeningResult(BaseModel):
    """Counters and warnings returned by POST /leads/screen."""

    processed: int
    approved: int
    pending_review: int
    discarded: int
    unchanged: int
    warning: str | None = None

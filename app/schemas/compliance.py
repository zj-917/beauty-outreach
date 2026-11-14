"""Request and response schemas for consent and suppression endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UtcDatetime


class ConsentUpsert(BaseModel):
    """Upsert consent for one phone number."""

    model_config = ConfigDict(extra="forbid")

    phone: str
    status: Literal["GRANTED", "REVOKED"]
    source: str = Field(min_length=1, max_length=80)
    evidence_ref: str | None = Field(default=None, max_length=200)


class ConsentView(BaseModel):
    """Consent response; the phone is masked and its hash is never exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    phone_masked: str
    status: str
    source: str
    evidence_ref: str | None = None
    granted_at: UtcDatetime | None = None
    updated_at: UtcDatetime
    updated_by: str


class SuppressionCreate(BaseModel):
    """Add a blacklist or unsubscribe entry by phone, username or both."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["BLACKLIST", "UNSUBSCRIBE"]
    phone: str | None = None
    username: str | None = None
    reason: str = Field(min_length=1, max_length=200)


class SuppressionView(BaseModel):
    """Suppression response with masked phone and no phone hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    phone_masked: str | None = None
    username: str | None = None
    reason: str
    source: str
    created_at: UtcDatetime
    created_by: str

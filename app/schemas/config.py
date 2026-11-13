"""Request and response schemas for configuration endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, RootModel

from app.schemas.common import UtcDatetime


class KeywordCreate(BaseModel):
    """Create a keyword."""

    model_config = ConfigDict(extra="forbid")

    term: str
    kind: Literal["POSITIVE", "NEGATIVE"]
    weight: int
    enabled: bool = True


class KeywordUpdate(BaseModel):
    """Update weight or enabled state; term changes require a new keyword."""

    model_config = ConfigDict(extra="forbid")

    weight: int | None = None
    enabled: bool | None = None


class KeywordView(BaseModel):
    """Keyword response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    term: str
    kind: str
    weight: int
    enabled: bool
    created_at: UtcDatetime
    updated_at: UtcDatetime


class RateRuleCreate(BaseModel):
    """Create a rate rule."""

    model_config = ConfigDict(extra="forbid")

    name: str
    scope: Literal["GLOBAL", "PER_RECIPIENT"]
    window_seconds: int
    max_count: int
    enabled: bool = True


class RateRuleUpdate(BaseModel):
    """Update any mutable rate rule field."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    scope: Literal["GLOBAL", "PER_RECIPIENT"] | None = None
    window_seconds: int | None = None
    max_count: int | None = None
    enabled: bool | None = None


class RateRuleView(BaseModel):
    """Rate rule response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope: str
    window_seconds: int
    max_count: int
    enabled: bool
    created_at: UtcDatetime
    updated_at: UtcDatetime


class SettingsUpdate(RootModel[dict[str, Any]]):
    """Arbitrary partial settings payload validated by the registry."""

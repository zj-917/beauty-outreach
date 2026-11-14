"""Request and response schemas for template endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.schemas.common import UtcDatetime


class TemplateCreate(BaseModel):
    """Create version 1 of a template."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=800)
    language: str


class TemplateUpdate(BaseModel):
    """Edit a draft template; approved templates reject body changes."""

    model_config = ConfigDict(extra="forbid")

    body: str | None = Field(default=None, max_length=800)
    language: str | None = None


class TemplateNewVersion(BaseModel):
    """Create the next draft version from an existing template."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=800)


class TemplateView(BaseModel):
    """Template response, including the template definition body."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: int
    language: str
    body: str
    status: str
    created_by: str
    approved_by: str | None = None
    approved_at: UtcDatetime | None = None
    created_at: UtcDatetime


class TemplatePreviewRequest(BaseModel):
    """Preview a supplied body or a stored template against a lead."""

    model_config = ConfigDict(extra="forbid")

    body: str | None = Field(default=None, max_length=800)
    template_id: StrictInt | None = None
    lead_id: StrictInt | None = None


class TemplatePreviewResponse(BaseModel):
    """Rendered preview text."""

    rendered: str

"""Persistence for versioned message templates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Template


@dataclass(frozen=True)
class TemplateEntry:
    """Detached template row."""

    id: int
    name: str
    version: int
    language: str
    body: str
    status: str
    created_by: str
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime


def find_template(session: Session, name: str, version: int) -> TemplateEntry | None:
    """Return a template by name and version."""
    row = session.scalar(
        select(Template).where(Template.name == name, Template.version == version)
    )
    return _to_template(row) if row is not None else None


def get_template(session: Session, template_id: int) -> TemplateEntry | None:
    """Return one template by id."""
    row = session.get(Template, template_id)
    return _to_template(row) if row is not None else None


def list_templates(session: Session) -> list[TemplateEntry]:
    """Return all template versions, grouped by name with newest first."""
    rows = session.scalars(
        select(Template).order_by(Template.name, Template.version.desc())
    ).all()
    return [_to_template(row) for row in rows]


def create_template(
    session: Session,
    *,
    name: str,
    version: int,
    language: str,
    body: str,
    status: str,
    created_by: str,
    approved_by: str | None,
    approved_at: datetime | None,
    created_at: datetime,
) -> TemplateEntry:
    """Insert a template row and flush it."""
    row = Template(
        name=name,
        version=version,
        language=language,
        body=body,
        status=status,
        created_by=created_by,
        approved_by=approved_by,
        approved_at=approved_at,
        created_at=created_at,
    )
    session.add(row)
    session.flush()
    return _to_template(row)


def update_template(
    session: Session,
    template_id: int,
    *,
    body: str,
    language: str,
) -> TemplateEntry | None:
    """Update the body and language of a draft template."""
    row = session.get(Template, template_id)
    if row is None:
        return None
    row.body = body
    row.language = language
    session.flush()
    return _to_template(row)


def approve_template(
    session: Session,
    template_id: int,
    *,
    approved_by: str,
    approved_at: datetime,
) -> TemplateEntry | None:
    """Mark a template as approved and record the reviewer metadata."""
    row = session.get(Template, template_id)
    if row is None:
        return None
    row.status = "APPROVED"
    row.approved_by = approved_by
    row.approved_at = approved_at
    session.flush()
    return _to_template(row)


def disable_template(session: Session, template_id: int) -> TemplateEntry | None:
    """Mark a template as disabled."""
    row = session.get(Template, template_id)
    if row is None:
        return None
    row.status = "DISABLED"
    session.flush()
    return _to_template(row)


def _to_template(row: Template) -> TemplateEntry:
    return TemplateEntry(
        id=row.id,
        name=row.name,
        version=row.version,
        language=row.language,
        body=row.body,
        status=row.status,
        created_by=row.created_by,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        created_at=row.created_at,
    )

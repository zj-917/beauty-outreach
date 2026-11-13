"""Persistence for message templates (seed support)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Template


def find_template(session: Session, name: str, version: int) -> Template | None:
    """Return a template row by name and version."""
    return session.scalar(
        select(Template).where(Template.name == name, Template.version == version)
    )


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
) -> None:
    """Insert a template row and flush it."""
    session.add(
        Template(
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
    )
    session.flush()

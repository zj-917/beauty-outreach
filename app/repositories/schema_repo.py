"""Schema drop/recreate used by the demo reset endpoint."""

from __future__ import annotations

from sqlalchemy import Engine

from app.models import Base, create_schema


def reset_schema(engine: Engine) -> None:
    """Drop every table and recreate the full schema."""
    Base.metadata.drop_all(engine)
    create_schema(engine)

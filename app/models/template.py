"""Versioned message template model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UtcDateTime


class Template(Base):
    """Immutable once approved; edits create a new version row."""

    __tablename__ = "template"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_template_name_version"),
        CheckConstraint("version >= 1", name="ck_template_version"),
        CheckConstraint("status IN ('DRAFT', 'APPROVED', 'DISABLED')", name="ck_template_status"),
        CheckConstraint("length(body) <= 800", name="ck_template_body_length"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="DRAFT")
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

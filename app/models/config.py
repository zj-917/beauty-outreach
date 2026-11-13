"""Runtime configuration models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UtcDateTime


class RateRule(Base):
    """A global or per-recipient rate limit window."""

    __tablename__ = "rate_rule"
    __table_args__ = (
        CheckConstraint("scope IN ('GLOBAL', 'PER_RECIPIENT')", name="ck_rate_rule_scope"),
        CheckConstraint("window_seconds >= 1", name="ck_rate_rule_window"),
        CheckConstraint("max_count >= 1", name="ck_rate_rule_max_count"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    max_count: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)


class SystemSetting(Base):
    """Key/value runtime setting validated against the settings registry."""

    __tablename__ = "system_setting"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)

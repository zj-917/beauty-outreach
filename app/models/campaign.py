"""Campaign task and per-item state models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UtcDateTime


class CampaignTask(Base):
    """A batch outreach task with a snapshot target list."""

    __tablename__ = "campaign_task"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'RUNNING', 'PAUSED', 'COMPLETED', 'CANCELLED')",
            name="ck_campaign_status",
        ),
        CheckConstraint(
            "pause_reason IS NULL OR pause_reason IN ('MANUAL', 'CIRCUIT_OPEN')",
            name="ck_campaign_pause_reason",
        ),
        CheckConstraint(
            "consecutive_failures >= 0", name="ck_campaign_consecutive_failures"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[int] = mapped_column(ForeignKey("template.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="DRAFT")
    selection: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pause_reason: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    paused_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)


class TaskItem(Base):
    """One recipient within a campaign; the unit of the sending state machine."""

    __tablename__ = "task_item"
    __table_args__ = (
        UniqueConstraint("task_id", "lead_id", name="uq_task_item_task_lead"),
        CheckConstraint(
            "status IN ('PENDING', 'SENDING', 'RETRY_WAIT', 'SENT', "
            "'DELIVERED', 'READ', 'FAILED', 'SKIPPED')",
            name="ck_task_item_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_task_item_attempts"),
        Index("ix_task_item_task_status", "task_id", "status"),
        Index("ix_task_item_status_next", "status", "next_attempt_at"),
        Index("ix_task_item_phone_hash", "phone_hash"),
        Index("ix_task_item_provider_message_id", "provider_message_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("campaign_task.id"), nullable=False)
    lead_id: Mapped[int] = mapped_column(ForeignKey("lead.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    phone_hash: Mapped[str | None] = mapped_column(Text)
    phone_masked: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    reason_code: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    locked_by: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    rendered_body: Mapped[str | None] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    last_error_code: Mapped[str | None] = mapped_column(Text)
    last_error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

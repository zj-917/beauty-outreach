"""Append-only send log and audit log models."""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UtcDateTime


class SendLog(Base):
    """One gate decision, provider call or receipt for a task item."""

    __tablename__ = "send_log"
    __table_args__ = (
        CheckConstraint(
            "(phase = 'GATE' AND outcome IN ('BLOCKED', 'DEFERRED')) "
            "OR (phase = 'PROVIDER' AND outcome IN "
            "('ACCEPTED', 'RETRYABLE_ERROR', 'PERMANENT_ERROR')) "
            "OR (phase = 'RECEIPT' AND outcome IN "
            "('DELIVERED', 'READ', 'DELIVERY_FAILED'))",
            name="ck_send_log_phase_outcome",
        ),
        Index("ix_send_log_item_id", "item_id"),
        Index("ix_send_log_task_created", "task_id", "created_at"),
        Index(
            "ix_send_log_phone_phase_outcome_created",
            "phone_hash",
            "phase",
            "outcome",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("campaign_task.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("task_item.id"), nullable=False)
    phone_hash: Mapped[str | None] = mapped_column(Text)
    phone_masked: Mapped[str | None] = mapped_column(Text)
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(Text)
    attempt_no: Mapped[int | None] = mapped_column(Integer)
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)


class AuditLog(Base):
    """Tamper-evident audit record; protected by append-only triggers."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_ts", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    request_id: Mapped[str | None] = mapped_column(Text)
    prev_hash: Mapped[str | None] = mapped_column(Text)
    hash: Mapped[str | None] = mapped_column(Text)

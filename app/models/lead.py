"""Lead ingestion and compliance models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UtcDateTime


class Keyword(Base):
    """Positive or negative screening keyword."""

    __tablename__ = "keyword"
    __table_args__ = (
        UniqueConstraint("term", "kind", name="uq_keyword_term_kind"),
        CheckConstraint("kind IN ('POSITIVE', 'NEGATIVE')", name="ck_keyword_kind"),
        CheckConstraint("weight BETWEEN 1 AND 50", name="ck_keyword_weight"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)


class LeadBatch(Base):
    """One import run and its report counters."""

    __tablename__ = "lead_batch"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('MOCK', 'CSV', 'JSON', 'INSTAGRAM_API')",
            name="ck_lead_batch_source_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)


class Lead(Base):
    """Normalized Instagram lead with encrypted phone and screening result."""

    __tablename__ = "lead"
    __table_args__ = (
        CheckConstraint(
            "status IN ('NEW', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', 'DISCARDED')",
            name="ck_lead_status",
        ),
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="ck_lead_score"),
        CheckConstraint(
            "decision_source IS NULL OR decision_source IN ('AUTO', 'MANUAL')",
            name="ck_lead_decision_source",
        ),
        Index("ix_lead_status_score", "status", "score"),
        Index("ix_lead_batch_id", "batch_id"),
        Index(
            "uq_lead_phone_hash",
            "phone_hash",
            unique=True,
            sqlite_where=text("phone_hash IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("lead_batch.id"), nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    phone_enc: Mapped[str | None] = mapped_column(Text)
    phone_hash: Mapped[str | None] = mapped_column(Text)
    phone_masked: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="NEW")
    score: Mapped[int | None] = mapped_column(Integer)
    score_reasons: Mapped[list[Any] | None] = mapped_column(JSON)
    top_keyword: Mapped[str | None] = mapped_column(Text)
    decision_source: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)


class ContactConsent(Base):
    """Marketing consent for one phone hash."""

    __tablename__ = "contact_consent"
    __table_args__ = (
        CheckConstraint("status IN ('GRANTED', 'REVOKED')", name="ck_consent_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    phone_masked: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ref: Mapped[str | None] = mapped_column(Text)
    granted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)


class Suppression(Base):
    """Blacklist or unsubscribe entry, matched by phone hash or username."""

    __tablename__ = "suppression"
    __table_args__ = (
        CheckConstraint("type IN ('BLACKLIST', 'UNSUBSCRIBE')", name="ck_suppression_type"),
        CheckConstraint(
            "source IN ('MANUAL', 'INBOUND_STOP', 'IMPORT')", name="ck_suppression_source"
        ),
        CheckConstraint(
            "phone_hash IS NOT NULL OR username IS NOT NULL",
            name="ck_suppression_identifier",
        ),
        Index(
            "uq_suppression_type_phone",
            "type",
            "phone_hash",
            unique=True,
            sqlite_where=text("phone_hash IS NOT NULL"),
        ),
        Index(
            "uq_suppression_type_username",
            "type",
            "username",
            unique=True,
            sqlite_where=text("username IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    phone_hash: Mapped[str | None] = mapped_column(Text)
    phone_masked: Mapped[str | None] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

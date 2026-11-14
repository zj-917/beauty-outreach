"""Append-only send log writes and the queries sent gates need."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CampaignTask, SendLog, Template


@dataclass(frozen=True)
class SendLogEntry:
    """Detached send log row."""

    id: int
    task_id: int
    item_id: int
    phone_hash: str | None
    phone_masked: str | None
    phase: str
    outcome: str
    reason_code: str | None
    attempt_no: int | None
    provider_message_id: str | None
    latency_ms: int | None
    detail: dict[str, Any] | None
    created_at: datetime


def insert(
    session: Session,
    *,
    task_id: int,
    item_id: int,
    phone_hash: str | None,
    phone_masked: str | None,
    phase: str,
    outcome: str,
    reason_code: str | None = None,
    attempt_no: int | None = None,
    provider_message_id: str | None = None,
    latency_ms: int | None = None,
    detail: dict[str, Any] | None = None,
    created_at: datetime,
) -> int:
    """Append one send log row and flush it."""
    row = SendLog(
        task_id=task_id,
        item_id=item_id,
        phone_hash=phone_hash,
        phone_masked=phone_masked,
        phase=phase,
        outcome=outcome,
        reason_code=reason_code,
        attempt_no=attempt_no,
        provider_message_id=provider_message_id,
        latency_ms=latency_ms,
        detail=detail,
        created_at=created_at,
    )
    session.add(row)
    session.flush()
    return row.id


def has_accepted_for_template(
    session: Session,
    *,
    phone_hash: str,
    template_name: str,
    exclude_item_id: int,
) -> bool:
    """Return whether this phone was already accepted for the template name."""
    count = session.scalar(
        select(func.count())
        .select_from(SendLog)
        .join(CampaignTask, CampaignTask.id == SendLog.task_id)
        .join(Template, Template.id == CampaignTask.template_id)
        .where(
            SendLog.phone_hash == phone_hash,
            SendLog.phase == "PROVIDER",
            SendLog.outcome == "ACCEPTED",
            Template.name == template_name,
            SendLog.item_id != exclude_item_id,
        )
    )
    return bool(count)


def recipient_accepted_count(
    session: Session,
    *,
    phone_hash: str,
    window_seconds: int,
    now: datetime,
    exclude_item_id: int,
) -> int:
    """Count accepted provider calls to one phone inside the sliding window."""
    since = now - timedelta(seconds=window_seconds)
    count = session.scalar(
        select(func.count())
        .select_from(SendLog)
        .where(
            SendLog.phone_hash == phone_hash,
            SendLog.phase == "PROVIDER",
            SendLog.outcome == "ACCEPTED",
            SendLog.created_at >= since,
            SendLog.item_id != exclude_item_id,
        )
    )
    return int(count or 0)


def provider_window_stats(
    session: Session, *, window_seconds: int, now: datetime
) -> tuple[int, datetime | None]:
    """Return the provider call count and earliest call inside the window."""
    since = now - timedelta(seconds=window_seconds)
    count, earliest = session.execute(
        select(func.count(), func.min(SendLog.created_at)).where(
            SendLog.phase == "PROVIDER", SendLog.created_at >= since
        )
    ).one()
    return int(count or 0), earliest


def list_for_task(session: Session, task_id: int) -> list[SendLogEntry]:
    """Return every send log row of one task in insertion order."""
    rows = session.scalars(
        select(SendLog).where(SendLog.task_id == task_id).order_by(SendLog.id)
    ).all()
    return [_to_entry(row) for row in rows]


def _to_entry(row: SendLog) -> SendLogEntry:
    return SendLogEntry(
        id=row.id,
        task_id=row.task_id,
        item_id=row.item_id,
        phone_hash=row.phone_hash,
        phone_masked=row.phone_masked,
        phase=row.phase,
        outcome=row.outcome,
        reason_code=row.reason_code,
        attempt_no=row.attempt_no,
        provider_message_id=row.provider_message_id,
        latency_ms=row.latency_ms,
        detail=dict(row.detail) if row.detail is not None else None,
        created_at=row.created_at,
    )

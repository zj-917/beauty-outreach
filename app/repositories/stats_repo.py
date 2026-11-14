"""Read-only aggregate queries behind the stats endpoints."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CampaignTask, ContactConsent, Lead, SendLog, Suppression, TaskItem


def reason_counts(session: Session, task_id: int, status: str) -> dict[str, int]:
    """Group one task's items of a status by reason code."""
    rows = session.execute(
        select(TaskItem.reason_code, func.count())
        .where(
            TaskItem.task_id == task_id,
            TaskItem.status == status,
            TaskItem.reason_code.is_not(None),
        )
        .group_by(TaskItem.reason_code)
    ).all()
    return {code: count for code, count in rows}


def attempts_histogram(session: Session, task_id: int) -> dict[int, int]:
    """Count one task's items by their attempt counter."""
    rows = session.execute(
        select(TaskItem.attempts, func.count())
        .where(TaskItem.task_id == task_id)
        .group_by(TaskItem.attempts)
    ).all()
    return {attempts: count for attempts, count in rows}


def lead_status_counts(session: Session) -> dict[str, int]:
    """Count leads by status."""
    rows = session.execute(
        select(Lead.status, func.count()).group_by(Lead.status)
    ).all()
    return {status: count for status, count in rows}


def campaign_status_counts(session: Session) -> dict[str, int]:
    """Count campaign tasks by status."""
    rows = session.execute(
        select(CampaignTask.status, func.count()).group_by(CampaignTask.status)
    ).all()
    return {status: count for status, count in rows}


def suppression_type_counts(session: Session) -> dict[str, int]:
    """Count suppression entries by type."""
    rows = session.execute(
        select(Suppression.type, func.count()).group_by(Suppression.type)
    ).all()
    return {entry_type: count for entry_type, count in rows}


def consent_status_counts(session: Session) -> dict[str, int]:
    """Count contact consents by status."""
    rows = session.execute(
        select(ContactConsent.status, func.count()).group_by(ContactConsent.status)
    ).all()
    return {status: count for status, count in rows}


def accepted_count_since(session: Session, since: datetime) -> int:
    """Count provider calls accepted at or after the given instant."""
    count = session.scalar(
        select(func.count())
        .select_from(SendLog)
        .where(
            SendLog.phase == "PROVIDER",
            SendLog.outcome == "ACCEPTED",
            SendLog.created_at >= since,
        )
    )
    return int(count or 0)

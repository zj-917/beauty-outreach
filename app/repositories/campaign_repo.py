"""Persistence for campaign tasks and their snapshot items."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import CampaignTask, Lead, TaskItem

ITEM_STATUSES = (
    "PENDING",
    "SENDING",
    "RETRY_WAIT",
    "SENT",
    "DELIVERED",
    "READ",
    "FAILED",
    "SKIPPED",
)
NON_TERMINAL_STATUSES = ("PENDING", "SENDING", "RETRY_WAIT")
LEASED_STATUS = "SENDING"


@dataclass(frozen=True)
class CampaignEntry:
    """Detached campaign task row."""

    id: int
    name: str
    template_id: int
    status: str
    selection: dict[str, Any]
    total_items: int
    pause_reason: str | None
    consecutive_failures: int
    created_by: str
    created_at: datetime
    started_at: datetime | None
    paused_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True)
class ItemEntry:
    """Detached task item row with the joined lead username only."""

    id: int
    task_id: int
    lead_id: int
    lead_username: str | None
    idempotency_key: str
    phone_hash: str | None
    phone_masked: str | None
    status: str
    reason_code: str | None
    attempts: int
    next_attempt_at: datetime | None
    provider_message_id: str | None
    last_error_code: str | None
    last_error_message: str | None
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime
    updated_at: datetime


def create_campaign(
    session: Session,
    *,
    name: str,
    template_id: int,
    selection: dict[str, Any],
    total_items: int,
    created_by: str,
    created_at: datetime,
) -> CampaignEntry:
    """Insert a DRAFT campaign row and flush it."""
    row = CampaignTask(
        name=name,
        template_id=template_id,
        status="DRAFT",
        selection=selection,
        total_items=total_items,
        consecutive_failures=0,
        created_by=created_by,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(row)
    session.flush()
    return _to_campaign(row)


def insert_item(
    session: Session,
    *,
    task_id: int,
    lead_id: int,
    idempotency_key: str,
    phone_hash: str | None,
    phone_masked: str | None,
    created_at: datetime,
    updated_at: datetime,
) -> int:
    """Insert one PENDING item; a duplicate key rolls back and raises CONFLICT."""
    row = TaskItem(
        task_id=task_id,
        lead_id=lead_id,
        idempotency_key=idempotency_key,
        phone_hash=phone_hash,
        phone_masked=phone_masked,
        status="PENDING",
        attempts=0,
        created_at=created_at,
        updated_at=updated_at,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "CONFLICT",
            "Duplicate campaign item",
            details={"field": "idempotency_key"},
        ) from exc
    return row.id


def get_campaign(session: Session, campaign_id: int) -> CampaignEntry | None:
    """Return one campaign by id."""
    row = session.get(CampaignTask, campaign_id)
    return _to_campaign(row) if row is not None else None


def list_campaigns(
    session: Session, *, offset: int, limit: int
) -> tuple[list[CampaignEntry], int]:
    """Return one page of campaigns, newest first."""
    total = session.scalar(select(func.count()).select_from(CampaignTask)) or 0
    rows = session.scalars(
        select(CampaignTask)
        .order_by(CampaignTask.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [_to_campaign(row) for row in rows], total


def update_campaign(session: Session, campaign_id: int, **fields: Any) -> None:
    """Apply the given column changes to one campaign row."""
    row = session.get(CampaignTask, campaign_id)
    if row is None:
        return
    for name, value in fields.items():
        setattr(row, name, value)
    session.flush()


def counts_for_tasks(
    session: Session, task_ids: list[int]
) -> dict[int, dict[str, int]]:
    """Return per-task item counts for every status, zero-filled."""
    counts = {
        task_id: {status: 0 for status in ITEM_STATUSES} for task_id in task_ids
    }
    if not task_ids:
        return counts
    rows = session.execute(
        select(TaskItem.task_id, TaskItem.status, func.count())
        .where(TaskItem.task_id.in_(task_ids))
        .group_by(TaskItem.task_id, TaskItem.status)
    ).all()
    for task_id, status, count in rows:
        if task_id in counts and status in counts[task_id]:
            counts[task_id][status] = count
    return counts


def has_open_items(session: Session, campaign_id: int) -> bool:
    """Return whether any item is still PENDING, SENDING or RETRY_WAIT."""
    count = session.scalar(
        select(func.count())
        .select_from(TaskItem)
        .where(
            TaskItem.task_id == campaign_id,
            TaskItem.status.in_(NON_TERMINAL_STATUSES),
        )
    )
    return bool(count)


def skip_open_items(
    session: Session, campaign_id: int, *, reason_code: str, updated_at: datetime
) -> int:
    """Mark every PENDING/RETRY_WAIT item SKIPPED and return how many changed."""
    result = session.execute(
        update(TaskItem)
        .where(
            TaskItem.task_id == campaign_id,
            TaskItem.status.in_(("PENDING", "RETRY_WAIT")),
        )
        .values(
            status="SKIPPED",
            reason_code=reason_code,
            locked_by=None,
            locked_at=None,
            updated_at=updated_at,
        )
    )
    return int(result.rowcount or 0)


def recover_expired_leases(
    session: Session, *, now: datetime, lease_seconds: int
) -> int:
    """Return expired SENDING items to RETRY_WAIT and report how many changed."""
    stale = now - timedelta(seconds=lease_seconds)
    result = session.execute(
        update(TaskItem)
        .where(TaskItem.status == "SENDING", TaskItem.locked_at < stale)
        .values(
            status="RETRY_WAIT",
            next_attempt_at=now,
            locked_by=None,
            locked_at=None,
            updated_at=now,
        )
    )
    return int(result.rowcount or 0)


def list_running_task_ids(session: Session) -> list[int]:
    """Return ids of every RUNNING campaign."""
    return list(
        session.scalars(
            select(CampaignTask.id)
            .where(CampaignTask.status == "RUNNING")
            .order_by(CampaignTask.id)
        ).all()
    )


def claim_items(
    session: Session,
    *,
    task_id: int,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
    limit: int,
) -> list[int]:
    """Lease up to `limit` claimable items of a RUNNING task atomically."""
    stale = now - timedelta(seconds=lease_seconds)
    rows = session.scalars(
        select(TaskItem)
        .join(CampaignTask, CampaignTask.id == TaskItem.task_id)
        .where(
            TaskItem.task_id == task_id,
            CampaignTask.status == "RUNNING",
            TaskItem.status.in_(("PENDING", "RETRY_WAIT")),
            or_(TaskItem.next_attempt_at.is_(None), TaskItem.next_attempt_at <= now),
            or_(TaskItem.locked_at.is_(None), TaskItem.locked_at < stale),
        )
        .order_by(TaskItem.id)
        .limit(limit)
    ).all()
    for row in rows:
        row.locked_by = worker_id
        row.locked_at = now
    session.flush()
    return [row.id for row in rows]


def get_item(session: Session, item_id: int) -> ItemEntry | None:
    """Return one item with its lead username."""
    row = session.execute(
        select(TaskItem, Lead.username)
        .join(Lead, Lead.id == TaskItem.lead_id)
        .where(TaskItem.id == item_id)
    ).first()
    if row is None:
        return None
    return _to_item(row[0], row[1])


def update_item(session: Session, item_id: int, **fields: Any) -> None:
    """Apply the given column changes to one item row."""
    row = session.get(TaskItem, item_id)
    if row is None:
        return
    for name, value in fields.items():
        setattr(row, name, value)
    session.flush()


def list_items(
    session: Session,
    campaign_id: int,
    *,
    status: str | None,
    reason_code: str | None,
    q: str | None,
    offset: int,
    limit: int,
) -> tuple[list[ItemEntry], int]:
    """Return one page of items ordered by id, with all filters applied."""
    conditions = [TaskItem.task_id == campaign_id]
    if status:
        conditions.append(TaskItem.status == status)
    if reason_code:
        conditions.append(TaskItem.reason_code == reason_code)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(
                Lead.username.ilike(pattern, escape="\\"),
                Lead.display_name.ilike(pattern, escape="\\"),
            )
        )
    base = select(TaskItem, Lead.username).join(Lead, Lead.id == TaskItem.lead_id)
    total = session.scalar(
        select(func.count())
        .select_from(TaskItem)
        .join(Lead, Lead.id == TaskItem.lead_id)
        .where(*conditions)
    ) or 0
    rows = session.execute(
        base.where(*conditions).order_by(TaskItem.id).offset(offset).limit(limit)
    ).all()
    return [_to_item(row, username) for row, username in rows], total


def _to_campaign(row: CampaignTask) -> CampaignEntry:
    return CampaignEntry(
        id=row.id,
        name=row.name,
        template_id=row.template_id,
        status=row.status,
        selection=dict(row.selection or {}),
        total_items=row.total_items,
        pause_reason=row.pause_reason,
        consecutive_failures=row.consecutive_failures,
        created_by=row.created_by,
        created_at=row.created_at,
        started_at=row.started_at,
        paused_at=row.paused_at,
        finished_at=row.finished_at,
        updated_at=row.updated_at,
    )


def _to_item(row: TaskItem, lead_username: str | None) -> ItemEntry:
    return ItemEntry(
        id=row.id,
        task_id=row.task_id,
        lead_id=row.lead_id,
        lead_username=lead_username,
        idempotency_key=row.idempotency_key,
        phone_hash=row.phone_hash,
        phone_masked=row.phone_masked,
        status=row.status,
        reason_code=row.reason_code,
        attempts=row.attempts,
        next_attempt_at=row.next_attempt_at,
        provider_message_id=row.provider_message_id,
        last_error_code=row.last_error_code,
        last_error_message=row.last_error_message,
        sent_at=row.sent_at,
        delivered_at=row.delivered_at,
        read_at=row.read_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

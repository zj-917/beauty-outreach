"""Persistence for the append-only audit log."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.logs import AuditLog


@dataclass(frozen=True)
class AuditEntry:
    """Detached audit row consumed by services and API schemas."""

    id: int
    ts: datetime
    actor: str
    action: str
    entity_type: str
    entity_id: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    request_id: str | None
    prev_hash: str | None
    hash: str | None


def last_hash(session: Session) -> str | None:
    """Return the hash of the most recent audit row."""
    return session.scalar(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1))


def append(
    session: Session,
    *,
    ts: datetime,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    request_id: str | None,
    prev_hash: str,
    hash_value: str,
) -> None:
    """Insert an audit row in the caller's transaction and flush it."""
    session.add(
        AuditLog(
            ts=ts,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            request_id=request_id,
            prev_hash=prev_hash,
            hash=hash_value,
        )
    )
    session.flush()


def list_entries(
    session: Session,
    *,
    actor: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[AuditEntry], int]:
    """Return a page of audit rows matching the filters, newest first."""
    conditions: list[Any] = []
    if actor is not None:
        conditions.append(AuditLog.actor == actor)
    if action is not None:
        conditions.append(AuditLog.action == action)
    if entity_type is not None:
        conditions.append(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        conditions.append(AuditLog.entity_id == entity_id)
    if from_ts is not None:
        conditions.append(AuditLog.ts >= from_ts)
    if to_ts is not None:
        conditions.append(AuditLog.ts <= to_ts)

    total_statement = select(func.count()).select_from(AuditLog)
    page_statement = select(AuditLog)
    if conditions:
        total_statement = total_statement.where(*conditions)
        page_statement = page_statement.where(*conditions)
    total = session.scalar(total_statement) or 0
    rows = session.scalars(
        page_statement.order_by(AuditLog.ts.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [_to_entry(row) for row in rows], total


def all_entries(session: Session) -> list[AuditEntry]:
    """Return every audit row in append order for chain verification."""
    rows = session.scalars(select(AuditLog).order_by(AuditLog.id.asc())).all()
    return [_to_entry(row) for row in rows]


def _to_entry(row: AuditLog) -> AuditEntry:
    return AuditEntry(
        id=row.id,
        ts=row.ts,
        actor=row.actor,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        before=row.before,
        after=row.after,
        request_id=row.request_id,
        prev_hash=row.prev_hash,
        hash=row.hash,
    )

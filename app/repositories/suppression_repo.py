"""Persistence for blacklist and unsubscribe entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Suppression


@dataclass(frozen=True)
class SuppressionEntry:
    """Detached suppression row."""

    id: int
    type: str
    phone_hash: str | None
    phone_masked: str | None
    username: str | None
    reason: str
    source: str
    created_at: datetime
    created_by: str


def list_suppressions(
    session: Session, *, type: str | None = None
) -> list[SuppressionEntry]:
    """Return suppression entries, newest first, optionally filtered by type."""
    statement = select(Suppression)
    if type is not None:
        statement = statement.where(Suppression.type == type)
    rows = session.scalars(statement.order_by(Suppression.id.desc())).all()
    return [_to_suppression(row) for row in rows]


def get_suppression(
    session: Session, suppression_id: int
) -> SuppressionEntry | None:
    """Return one suppression entry by id."""
    row = session.get(Suppression, suppression_id)
    return _to_suppression(row) if row is not None else None


def find_by_phone(
    session: Session, *, type: str, phone_hash: str
) -> SuppressionEntry | None:
    """Return a suppression entry by type and phone hash."""
    row = session.scalar(
        select(Suppression).where(
            Suppression.type == type, Suppression.phone_hash == phone_hash
        )
    )
    return _to_suppression(row) if row is not None else None


def find_by_username(
    session: Session, *, type: str, username: str
) -> SuppressionEntry | None:
    """Return a suppression entry by type and username."""
    row = session.scalar(
        select(Suppression).where(
            Suppression.type == type, Suppression.username == username
        )
    )
    return _to_suppression(row) if row is not None else None


def find_types(
    session: Session, *, phone_hash: str | None, username: str | None
) -> set[str]:
    """Return every suppression type matching the phone hash or username."""
    conditions = []
    if phone_hash is not None:
        conditions.append(Suppression.phone_hash == phone_hash)
    if username is not None:
        conditions.append(Suppression.username == username)
    if not conditions:
        return set()
    rows = session.scalars(select(Suppression.type).where(or_(*conditions))).all()
    return set(rows)


def create_suppression(
    session: Session,
    *,
    type: str,
    phone_hash: str | None,
    phone_masked: str | None,
    username: str | None,
    reason: str,
    source: str,
    created_at: datetime,
    created_by: str,
) -> SuppressionEntry:
    """Insert a suppression entry and flush it."""
    row = Suppression(
        type=type,
        phone_hash=phone_hash,
        phone_masked=phone_masked,
        username=username,
        reason=reason,
        source=source,
        created_at=created_at,
        created_by=created_by,
    )
    session.add(row)
    session.flush()
    return _to_suppression(row)


def delete_suppression(
    session: Session, suppression_id: int
) -> SuppressionEntry | None:
    """Delete a suppression entry and return its previous state."""
    row = session.get(Suppression, suppression_id)
    if row is None:
        return None
    entry = _to_suppression(row)
    session.delete(row)
    session.flush()
    return entry


def _to_suppression(row: Suppression) -> SuppressionEntry:
    return SuppressionEntry(
        id=row.id,
        type=row.type,
        phone_hash=row.phone_hash,
        phone_masked=row.phone_masked,
        username=row.username,
        reason=row.reason,
        source=row.source,
        created_at=row.created_at,
        created_by=row.created_by,
    )

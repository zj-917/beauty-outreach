"""Audit rows share the caller's transaction."""

from __future__ import annotations

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import AuditLog
from app.services.audit_service import AuditService


def _count(db: Engine) -> int:
    with Session(db) as session:
        return session.scalar(select(func.count()).select_from(AuditLog)) or 0


def test_AC_AUD_002_record_does_not_commit(db: Engine, clock: FakeClock) -> None:
    """Given a recorded audit, when the caller rolls back, then no row remains."""
    service = AuditService(clock)
    with Session(db) as session:
        service.record(session, actor="admin", action="A", entity_type="lead", entity_id="1")
        assert session.in_transaction()
        session.rollback()
    assert _count(db) == 0


def test_AC_AUD_002_record_commits_with_caller(db: Engine, clock: FakeClock) -> None:
    """Given a recorded audit, when the caller commits, then the row is visible."""
    service = AuditService(clock)
    with Session(db) as session:
        service.record(session, actor="admin", action="A", entity_type="lead", entity_id="1")
        session.commit()
    assert _count(db) == 1

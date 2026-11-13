"""Audit hash chain and verification tests."""

from __future__ import annotations

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import AuditLog
from app.services.audit_service import AuditService


def _record_three(db: Engine, clock: FakeClock) -> None:
    service = AuditService(clock)
    with Session(db) as session:
        for index in range(3):
            service.record(
                session,
                actor="admin",
                action=f"ACTION_{index}",
                entity_type="lead",
                entity_id=str(index + 1),
            )
            clock.advance(60)
        session.commit()


def test_AC_AUD_004_chain_verifies_and_links_hashes(db: Engine, clock: FakeClock) -> None:
    """Given a chain of records, when verified, then ok and each prev_hash links."""
    _record_three(db, clock)
    with Session(db) as session:
        rows = session.scalars(select(AuditLog).order_by(AuditLog.id)).all()
        assert [row.prev_hash for row in rows] == ["GENESIS", rows[0].hash, rows[1].hash]
        result = AuditService(clock).verify_chain(session)
    assert result.ok is True
    assert result.count == 3


def test_AC_AUD_004_tampering_is_detected(db: Engine, clock: FakeClock) -> None:
    """Given a tampered row with the trigger dropped, when verified, then its id is reported."""
    _record_three(db, clock)
    with db.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER audit_log_no_update")
        connection.exec_driver_sql("UPDATE audit_log SET actor = 'mallory' WHERE id = 2")
    with Session(db) as session:
        result = AuditService(clock).verify_chain(session)
    assert result.ok is False
    assert result.first_broken_id == 2

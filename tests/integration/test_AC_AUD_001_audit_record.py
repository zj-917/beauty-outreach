"""Audit record field tests."""

from __future__ import annotations

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import AuditLog
from app.services.audit_service import AuditService


def test_AC_AUD_001_record_contains_all_fields(db: Engine, clock: FakeClock) -> None:
    """Given a recorded audit, when read, then all fields and the genesis hash exist."""
    service = AuditService(clock)
    with Session(db) as session:
        service.record(
            session,
            actor="system:worker",
            action="TEST_ACTION",
            entity_type="lead",
            entity_id="7",
            before={"status": "NEW"},
            after={"status": "APPROVED"},
            request_id="req-1",
        )
        session.commit()
    with Session(db) as session:
        row = session.scalar(select(AuditLog))
    assert row is not None
    assert row.ts == clock.now()
    assert row.actor == "system:worker"
    assert row.action == "TEST_ACTION"
    assert row.entity_type == "lead"
    assert row.entity_id == "7"
    assert row.before == {"status": "NEW"}
    assert row.after == {"status": "APPROVED"}
    assert row.request_id == "req-1"
    assert row.prev_hash == "GENESIS"
    assert row.hash is not None

"""Audit log append-only trigger tests."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

TS = "2026-11-14 09:00:00"


def _insert_audit(db: Engine) -> int:
    with db.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO audit_log "
            "(ts, actor, action, entity_type, entity_id, before, after, request_id, "
            "prev_hash, hash) "
            "VALUES (?, 'admin', 'TEST_ACTION', 'lead', '1', NULL, NULL, NULL, NULL, NULL)",
            (TS,),
        )
        return connection.exec_driver_sql("SELECT id FROM audit_log").scalar_one()


def test_AC_AUD_003_update_is_rejected(db: Engine) -> None:
    """Given an audit row, when updated with raw SQL, then the trigger aborts and it is intact."""
    audit_id = _insert_audit(db)
    with pytest.raises(IntegrityError, match="append-only"), db.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE audit_log SET actor = 'mallory' WHERE id = ?", (audit_id,)
        )
    with db.connect() as connection:
        actor = connection.exec_driver_sql(
            "SELECT actor FROM audit_log WHERE id = ?", (audit_id,)
        ).scalar_one()
    assert actor == "admin"


def test_AC_AUD_003_delete_is_rejected(db: Engine) -> None:
    """Given an audit row, when deleted with raw SQL, then the trigger aborts and it remains."""
    audit_id = _insert_audit(db)
    with pytest.raises(IntegrityError, match="append-only"), db.begin() as connection:
        connection.exec_driver_sql("DELETE FROM audit_log WHERE id = ?", (audit_id,))
    with db.connect() as connection:
        count = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM audit_log WHERE id = ?", (audit_id,)
        ).scalar_one()
    assert count == 1

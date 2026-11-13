"""Audit snapshot redaction tests."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.services.audit_service import AuditService


def test_AC_AUD_011_snapshots_are_redacted_in_db_and_api(
    app: FastAPI, clock: FakeClock, client: TestClient
) -> None:
    """Given secrets and phones in before/after, when stored and read, then nothing leaks."""
    service = AuditService(clock)
    session = app.state.session_factory()
    try:
        service.record(
            session,
            actor="admin",
            action="LEAD_REVIEWED",
            entity_type="lead",
            entity_id="1",
            before={
                "phone": "+15555550101",
                "body": "hello",
                "token": "t0ken",
                "reviewed_at": "2026-11-14T09:00:00Z",
            },
            after={
                "phone_masked": "+155****0101",
                "note": "call +15555550101",
                "secret": "s",
                "password": "p",
                "key": "k",
            },
        )
        session.commit()
    finally:
        session.close()

    with app.state.engine.connect() as connection:
        before_raw, after_raw = connection.exec_driver_sql(
            "SELECT before, after FROM audit_log"
        ).one()
    before_data = json.loads(before_raw)
    after_data = json.loads(after_raw)
    assert set(before_data) == {"phone", "reviewed_at"}
    assert before_data["phone"] == "+155****0101"
    assert before_data["reviewed_at"] == "2026-11-14T09:00:00Z"
    assert set(after_data) == {"phone_masked", "note"}
    assert after_data["note"] == "call +155****0101"

    response = client.get("/api/v1/audit-logs")
    assert "+15555550101" not in response.text
    assert "hello" not in response.text
    assert "t0ken" not in response.text
    assert "+155****0101" in response.text

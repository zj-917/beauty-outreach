"""Unsubscribe persistence tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.domain.gates import Skip, evaluate
from app.services.compliance_service import ComplianceService


def test_AC_COMP_009_unsubscribe_survives_later_grant(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given an unsubscribe entry, when consent is later granted, then the gate still blocks."""
    phone = "+15555556101"
    unsubscribed = client.post(
        "/api/v1/suppressions",
        json={"type": "UNSUBSCRIBE", "phone": phone, "reason": "user stop"},
    )
    assert unsubscribed.status_code == 201
    granted = client.put(
        "/api/v1/consents",
        json={
            "phone": phone,
            "status": "GRANTED",
            "source": "web_form",
            "evidence_ref": "form-1",
        },
    )
    assert granted.status_code == 200

    cipher = client.app.state.phone_cipher
    compliance = ComplianceService(clock, cipher, client.app.state.audit_service)
    with Session(db) as session:
        snapshot = compliance.snapshot(
            session,
            phone_hash=cipher.hash_phone(phone),
            username=None,
            has_phone=True,
            phone_valid=True,
        )

    assert evaluate(snapshot) == Skip("UNSUBSCRIBED")

"""Signed webhook authentication (AC-SYS-009)."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import AuditLog, SendLog, Suppression
from app.services.seed_service import seed_defaults

SECRET = "test-webhook-secret"


def _raw(payload: dict) -> bytes:
    return json.dumps(payload).encode()


def _counts(db: Engine) -> tuple[int, int, int]:
    with Session(db) as session:
        audits = len(session.scalars(select(AuditLog)).all())
        logs = len(session.scalars(select(SendLog)).all())
        suppressions = len(session.scalars(select(Suppression)).all())
    return audits, logs, suppressions


def test_AC_SYS_009_missing_signature_is_rejected_without_writes(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given no signature, when a webhook arrives, then 401 and nothing is written."""
    with Session(db) as session:
        seed_defaults(session, clock)
    body = _raw({"from": "+15555550301", "text": "STOP"})
    before = _counts(db)

    response = client.post(
        "/api/v1/webhooks/whatsapp/inbound",
        content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SIGNATURE_INVALID"
    assert _counts(db) == before


def test_AC_SYS_009_wrong_signature_is_rejected_without_writes(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a signature from a different secret, when it arrives, then 401 and no writes."""
    with Session(db) as session:
        seed_defaults(session, clock)
    body = _raw(
        {"provider_message_id": "mock-msg-x", "status": "delivered"}
    )
    wrong = "sha256=" + hmac.new(b"other-secret", body, hashlib.sha256).hexdigest()
    before = _counts(db)

    response = client.post(
        "/api/v1/webhooks/whatsapp/status",
        content=body,
        headers={
            "X-Hub-Signature-256": wrong,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SIGNATURE_INVALID"
    assert _counts(db) == before


def test_AC_SYS_009_correct_signature_processes_the_webhook(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given the right signature, when the inbound STOP arrives, then it is processed."""
    with Session(db) as session:
        seed_defaults(session, clock)
    body = _raw({"from": "+15555550302", "text": "STOP"})
    signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

    response = client.post(
        "/api/v1/webhooks/whatsapp/inbound",
        content=body,
        headers={
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"action": "UNSUBSCRIBED"}
    audits, _, suppressions = _counts(db)
    assert audits == 1
    assert suppressions == 1

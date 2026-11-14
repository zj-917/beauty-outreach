"""Inbound STOP processing through the signed webhook (AC-COMP-006)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.services.seed_service import seed_defaults

SECRET = "test-webhook-secret"


def _seed(db: Engine, clock: FakeClock) -> None:
    with Session(db) as session:
        seed_defaults(session, clock)


def _inbound(client: TestClient, *, phone: str, text: str):
    raw = json.dumps({"from": phone, "text": text}).encode()
    signature = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        "/api/v1/webhooks/whatsapp/inbound",
        content=raw,
        headers={
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json",
        },
    )


@pytest.mark.parametrize("text", ["STOP", " stop. ", "退订"])
def test_AC_COMP_006_stop_variants_unsubscribe_and_revoke_consent(
    text: str,
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    make_lead,
) -> None:
    """Given a STOP variant, when the webhook runs, then suppression and consent update."""
    _seed(db, clock)
    make_lead(username="stopper", phone="+15555550201")

    response = _inbound(client, phone="+15555550201", text=text)

    assert response.status_code == 200
    assert response.json() == {"action": "UNSUBSCRIBED"}
    suppressions = client.get(
        "/api/v1/suppressions", params={"type": "UNSUBSCRIBE"}
    ).json()
    assert len(suppressions) == 1
    assert suppressions[0]["phone_masked"] == "+155****0201"
    consents = client.get("/api/v1/consents").json()
    assert consents[0]["status"] == "REVOKED"
    audit = client.get(
        "/api/v1/audit-logs", params={"action": "INBOUND_STOP_PROCESSED"}
    ).json()
    assert audit["total"] == 1
    assert audit["items"][0]["actor"] == "system:webhook"


@pytest.mark.parametrize("text", ["please don't stop", "stopping"])
def test_AC_COMP_006_non_stop_texts_are_ignored(
    text: str,
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    make_lead,
) -> None:
    """Given a text that is not exactly a stop keyword, then nothing changes."""
    _seed(db, clock)
    make_lead(username="not_stopping", phone="+15555550202")

    response = _inbound(client, phone="+15555550202", text=text)

    assert response.status_code == 200
    assert response.json() == {"action": "IGNORED"}
    assert client.get("/api/v1/suppressions").json() == []
    assert client.get("/api/v1/consents").json()[0]["status"] == "GRANTED"
    audit = client.get(
        "/api/v1/audit-logs", params={"action": "INBOUND_STOP_PROCESSED"}
    ).json()
    assert audit["total"] == 0


def test_AC_COMP_006_repeated_stop_is_idempotent(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given a STOP already processed, when it repeats, then no duplicates appear."""
    _seed(db, clock)
    make_lead(username="repeat_stop", phone="+15555550203")

    assert _inbound(client, phone="+15555550203", text="STOP").json() == {
        "action": "UNSUBSCRIBED"
    }
    assert _inbound(client, phone="+15555550203", text="stop").json() == {
        "action": "UNSUBSCRIBED"
    }

    assert len(client.get("/api/v1/suppressions").json()) == 1
    audit = client.get(
        "/api/v1/audit-logs", params={"action": "INBOUND_STOP_PROCESSED"}
    ).json()
    assert audit["total"] == 1


def test_AC_COMP_006_unknown_number_is_still_registered(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a STOP from a number without a lead, then the suppression is created."""
    _seed(db, clock)

    response = _inbound(client, phone="+15555550299", text="STOP")

    assert response.json() == {"action": "UNSUBSCRIBED"}
    suppressions = client.get("/api/v1/suppressions").json()
    assert len(suppressions) == 1
    assert (suppressions[0]["type"], suppressions[0]["source"]) == (
        "UNSUBSCRIBE",
        "INBOUND_STOP",
    )
    assert client.get("/api/v1/consents").json() == []


def test_AC_COMP_006_invalid_phone_is_ignored(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a malformed inbound number, then the message is ignored without writes."""
    _seed(db, clock)

    response = _inbound(client, phone="not-a-phone", text="STOP")

    assert response.json() == {"action": "IGNORED"}
    assert client.get("/api/v1/suppressions").json() == []
    audit = client.get("/api/v1/audit-logs").json()
    assert audit["total"] == 0

"""Failed delivery receipts (AC-CAMP-021)."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.worker import Worker
from app.providers.messenger.mock import MockMessenger
from app.services.seed_service import seed_defaults

SECRET = "test-webhook-secret"


def _seed(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _signed_post(client: TestClient, payload: dict):
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        "/api/v1/webhooks/whatsapp/status",
        content=raw,
        headers={
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json",
        },
    )


def _sent_item(client: TestClient, db: Engine, clock: FakeClock, worker: Worker, make_lead) -> dict:
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="failed_receipt", phone="+15555550103")
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "failed receipts",
            "template_id": template_id,
            "selection": {"lead_ids": [lead_id]},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    worker.tick()
    item = client.get(f"/api/v1/campaigns/{campaign_id}/items").json()["items"][0]
    assert item["status"] == "SENT"
    return item


def test_AC_CAMP_021_failed_receipt_after_sent_fails_without_retry(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given a SENT item, when a failed receipt arrives, then it fails and never retries."""
    item = _sent_item(client, db, clock, worker, make_lead)
    calls_after_send = messenger.calls

    response = _signed_post(
        client,
        {
            "provider_message_id": item["provider_message_id"],
            "status": "failed",
            "error": {"code": "131026", "message": "undeliverable"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {"applied": True}
    body = client.get(
        f"/api/v1/campaigns/{item['task_id']}/items"
    ).json()["items"][0]
    assert (body["status"], body["reason_code"]) == ("FAILED", "DELIVERY_FAILED")
    assert body["last_error_code"] == "131026"
    assert body["next_attempt_at"] is None

    clock.advance(60)
    worker.tick()
    assert messenger.calls == calls_after_send


def test_AC_CAMP_021_failed_receipt_after_delivered_fails(
    client: TestClient, db: Engine, clock: FakeClock, worker: Worker, make_lead
) -> None:
    """Given a DELIVERED item, when a failed receipt arrives, then it fails."""
    item = _sent_item(client, db, clock, worker, make_lead)
    message_id = item["provider_message_id"]
    assert _signed_post(
        client, {"provider_message_id": message_id, "status": "delivered"}
    ).json() == {"applied": True}

    assert _signed_post(
        client, {"provider_message_id": message_id, "status": "failed"}
    ).json() == {"applied": True}
    body = client.get(
        f"/api/v1/campaigns/{item['task_id']}/items"
    ).json()["items"][0]
    assert (body["status"], body["reason_code"]) == ("FAILED", "DELIVERY_FAILED")


def test_AC_CAMP_021_failed_receipt_after_read_is_ignored(
    client: TestClient, db: Engine, clock: FakeClock, worker: Worker, make_lead
) -> None:
    """Given a READ item, when a failed receipt arrives, then it is ignored."""
    item = _sent_item(client, db, clock, worker, make_lead)
    message_id = item["provider_message_id"]
    assert _signed_post(
        client, {"provider_message_id": message_id, "status": "read"}
    ).json() == {"applied": True}

    response = _signed_post(
        client, {"provider_message_id": message_id, "status": "failed"}
    )

    assert response.json() == {"applied": False}
    body = client.get(
        f"/api/v1/campaigns/{item['task_id']}/items"
    ).json()["items"][0]
    assert body["status"] == "READ"

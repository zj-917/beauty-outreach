"""Delivery receipt handling through the signed webhook (CAMP-020)."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.models import SendLog
from app.providers.messenger.mock import MockMessenger
from app.services.receipt_service import ReceiptService
from app.services.seed_service import seed_defaults

SECRET = "test-webhook-secret"


def _seed(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _signed_post(client: TestClient, path: str, payload: dict):
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        path,
        content=raw,
        headers={
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json",
        },
    )


def _sent_item(client: TestClient, db: Engine, clock: FakeClock, worker: Worker, make_lead) -> dict:
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="receipt_target", phone="+15555550102")
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "receipts",
            "template_id": template_id,
            "selection": {"lead_ids": [lead_id]},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    worker.tick()
    body = client.get(f"/api/v1/campaigns/{campaign_id}/items").json()
    item = body["items"][0]
    assert item["status"] == "SENT"
    return item


def test_AC_CAMP_020_delivered_then_read_advance_the_item(
    client: TestClient, db: Engine, clock: FakeClock, worker: Worker, make_lead
) -> None:
    """Given a SENT item, when delivered then read arrive, then state advances."""
    item = _sent_item(client, db, clock, worker, make_lead)

    delivered = _signed_post(
        client,
        "/api/v1/webhooks/whatsapp/status",
        {
            "provider_message_id": item["provider_message_id"],
            "status": "delivered",
            "timestamp": "2026-11-14T09:00:05Z",
        },
    )
    assert delivered.status_code == 200
    assert delivered.json() == {"applied": True}
    body = client.get(
        f"/api/v1/campaigns/{item['task_id']}/items"
    ).json()["items"][0]
    assert body["status"] == "DELIVERED"
    assert body["delivered_at"] == "2026-11-14T09:00:05Z"

    read = _signed_post(
        client,
        "/api/v1/webhooks/whatsapp/status",
        {"provider_message_id": item["provider_message_id"], "status": "read"},
    )
    assert read.json() == {"applied": True}
    body = client.get(
        f"/api/v1/campaigns/{item['task_id']}/items"
    ).json()["items"][0]
    assert body["status"] == "READ"
    assert body["read_at"] is not None

    with Session(db) as session:
        logs = session.scalars(
            select(SendLog).where(
                SendLog.phase == "RECEIPT", SendLog.item_id == item["id"]
            )
        ).all()
    assert [log.outcome for log in logs] == ["DELIVERED", "READ"]


def test_AC_CAMP_020_out_of_order_and_duplicate_receipts_are_noops(
    client: TestClient, db: Engine, clock: FakeClock, worker: Worker, make_lead
) -> None:
    """Given a READ item, when stale receipts arrive, then nothing moves backwards."""
    item = _sent_item(client, db, clock, worker, make_lead)
    message_id = item["provider_message_id"]
    assert _signed_post(
        client,
        "/api/v1/webhooks/whatsapp/status",
        {"provider_message_id": message_id, "status": "read"},
    ).json() == {"applied": True}
    assert _signed_post(
        client,
        "/api/v1/webhooks/whatsapp/status",
        {"provider_message_id": message_id, "status": "delivered"},
    ).json() == {"applied": False}
    assert _signed_post(
        client,
        "/api/v1/webhooks/whatsapp/status",
        {"provider_message_id": message_id, "status": "read"},
    ).json() == {"applied": False}
    body = client.get(
        f"/api/v1/campaigns/{item['task_id']}/items"
    ).json()["items"][0]
    assert body["status"] == "READ"


def test_AC_CAMP_020_sent_to_read_jump_is_allowed(
    client: TestClient, db: Engine, clock: FakeClock, worker: Worker, make_lead
) -> None:
    """Given a SENT item, when a read receipt skips delivered, then READ is applied."""
    item = _sent_item(client, db, clock, worker, make_lead)
    response = _signed_post(
        client,
        "/api/v1/webhooks/whatsapp/status",
        {"provider_message_id": item["provider_message_id"], "status": "read"},
    )
    assert response.json() == {"applied": True}
    body = client.get(
        f"/api/v1/campaigns/{item['task_id']}/items"
    ).json()["items"][0]
    assert body["status"] == "READ"


def test_AC_CAMP_020_unknown_message_id_is_a_noop(
    client: TestClient, db: Engine, clock: FakeClock, worker: Worker, make_lead
) -> None:
    """Given an unknown provider message id, when a receipt arrives, then 200 applied false."""
    _sent_item(client, db, clock, worker, make_lead)
    with Session(db) as session:
        count_before = len(session.scalars(select(SendLog)).all())

    response = _signed_post(
        client,
        "/api/v1/webhooks/whatsapp/status",
        {"provider_message_id": "mock-msg-unknown", "status": "delivered"},
    )

    assert response.status_code == 200
    assert response.json() == {"applied": False}
    with Session(db) as session:
        count_after = len(session.scalars(select(SendLog)).all())
    assert count_after == count_before


def test_AC_CAMP_020_worker_polls_receipts_each_tick(
    client: TestClient, db: Engine, clock: FakeClock, app: FastAPI, make_lead
) -> None:
    """Given queued mock receipts, when the worker ticks later, then they are applied."""
    messenger = MockMessenger(clock)
    processor = Processor(
        clock,
        app.state.phone_cipher,
        messenger,
        worker_id="poller",
        audit=app.state.audit_service,
    )
    receipts = ReceiptService(
        clock,
        messenger=messenger,
        session_factory=app.state.session_factory,
    )
    worker = Worker(
        app.state.session_factory,
        clock,
        processor,
        worker_id="poller",
        receipts=receipts,
    )
    item = _sent_item(client, db, clock, worker, make_lead)

    clock.advance(5)
    worker.tick()

    body = client.get(
        f"/api/v1/campaigns/{item['task_id']}/items"
    ).json()["items"][0]
    assert body["status"] == "READ"

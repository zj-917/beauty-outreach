"""E2E-8: receipts advance states in order, ignore stale ones and fail 9005."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable

from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.providers.messenger.mock import MockMessenger

SECRET = "test-webhook-secret"


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


def test_e2e_08_receipts_advance_in_order_and_failed_delivery_fails(
    client: TestClient,
    clock: FakeClock,
    template_id: int,
    messenger: MockMessenger,
    make_worker: Callable[..., object],
    make_lead,
) -> None:
    """Covers: AC-CAMP-020, AC-CAMP-021.

    Given two sent items, when the queued receipts apply, then the healthy one
    reaches READ, stale repeats are no-ops and 9005 fails with DELIVERY_FAILED.
    """
    healthy = make_lead(username="e2e_receipt_ok", phone="+15555550104")
    failing = make_lead(username="e2e_receipt_fail", phone="+15555559005")
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "e2e receipts",
            "template_id": template_id,
            "selection": {"lead_ids": [healthy, failing]},
        },
    ).json()
    campaign_id = campaign["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200

    worker = make_worker(messenger, receipts=True)
    worker.tick()
    items = {
        item["lead_id"]: item
        for item in client.get(
            f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
        ).json()["items"]
    }
    assert {item["status"] for item in items.values()} == {"SENT"}

    clock.advance(10)
    worker.tick()

    items = {
        item["lead_id"]: item
        for item in client.get(
            f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
        ).json()["items"]
    }
    assert items[healthy]["status"] == "READ"
    assert items[healthy]["delivered_at"] is not None
    assert items[healthy]["read_at"] is not None
    assert (items[failing]["status"], items[failing]["reason_code"]) == (
        "FAILED",
        "DELIVERY_FAILED",
    )

    stale = _signed_post(
        client,
        {
            "provider_message_id": items[healthy]["provider_message_id"],
            "status": "delivered",
        },
    )
    assert stale.json() == {"applied": False}
    duplicate = _signed_post(
        client,
        {
            "provider_message_id": items[healthy]["provider_message_id"],
            "status": "read",
        },
    )
    assert duplicate.json() == {"applied": False}

    stats = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()
    assert (stats["success"], stats["failed"]) == (1, 1)
    assert stats["failure_reasons"] == {"DELIVERY_FAILED": 1}

"""Lease recovery after a simulated crash (AC-CAMP-009)."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.worker import Worker
from app.models import TaskItem
from app.providers.messenger.base import SendRequest
from app.providers.messenger.mock import MockMessenger
from app.services.seed_service import seed_defaults


def _seed(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def test_AC_CAMP_009_expired_sending_item_is_recovered_with_same_key(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given a crashed SENDING item the provider accepted, when ticking, then no duplicate."""
    template_id = _seed(client, db, clock)
    phone = "+15555550121"
    lead_id = make_lead(username="crashed", phone=phone)
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "crash recovery",
            "template_id": template_id,
            "selection": {"lead_ids": [lead_id]},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200

    with Session(db) as session:
        row = session.scalar(select(TaskItem))
        assert row is not None
        item_id = row.id
        key = row.idempotency_key
    first = messenger.send(
        SendRequest(
            idempotency_key=key,
            to_phone=phone,
            body="hello",
            template_name="greeting",
            language="en",
        )
    )
    assert first.provider_message_id is not None
    assert messenger.unique_messages == 1

    with Session(db) as session:
        row = session.get(TaskItem, item_id)
        assert row is not None
        row.status = "SENDING"
        row.attempts = 1
        row.locked_by = "crashed-worker"
        row.locked_at = clock.now() - timedelta(seconds=120)
        session.commit()

    worker.tick()

    item = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"][0]
    assert item["status"] == "SENT"
    assert item["attempts"] == 2
    assert messenger.unique_messages == 1
    assert messenger.calls == 2

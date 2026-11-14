"""E2E-3: an expired lease after a simulated crash resends with the same key."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import TaskItem
from app.providers.messenger.base import SendRequest
from app.providers.messenger.mock import MockMessenger


def test_e2e_03_expired_lease_recovers_without_duplicate(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    template_id: int,
    messenger: MockMessenger,
    make_worker: Callable[..., object],
    make_lead,
) -> None:
    """Covers: AC-CAMP-005, AC-CAMP-009, AC-CAMP-025.

    Given an item left SENDING with an expired lease after the provider accepted it,
    when the worker ticks, then it is resent with the same key and no duplicate.
    """
    phone = "+15555550121"
    lead_id = make_lead(username="e2e_crashed", phone=phone)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "e2e crash",
            "template_id": template_id,
            "selection": {"lead_ids": [lead_id]},
        },
    ).json()
    campaign_id = campaign["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200

    with Session(db) as session:
        row = session.scalar(select(TaskItem))
        assert row is not None
        item_id, key = row.id, row.idempotency_key
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

    worker = make_worker(messenger)
    worker.tick()

    item = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"][0]
    assert item["status"] == "SENT"
    assert item["attempts"] == 2
    assert messenger.calls == 2
    assert messenger.unique_messages == 1
    assert client.get(f"/api/v1/campaigns/{campaign_id}").json()["status"] == "COMPLETED"

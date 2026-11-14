"""Duplicate-contact gate across tasks."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.worker import Worker
from app.providers.messenger.mock import MockMessenger
from app.services.seed_service import seed_defaults


def _seed(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _campaign(client: TestClient, template_id: int, lead_ids: list[int], name: str) -> int:
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": name,
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    assert response.status_code == 201, response.text
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    return campaign_id


def test_AC_CAMP_014_same_template_name_is_not_sent_twice(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given an accepted send for a template name, when another task reuses it, then skip."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="contacted", phone="+15555550181")
    first = _campaign(client, template_id, [lead_id], "first")
    worker.tick()
    assert (
        client.get(f"/api/v1/campaigns/{first}/items").json()["items"][0]["status"]
        == "SENT"
    )

    second = _campaign(client, template_id, [lead_id], "second")
    worker.tick()

    item = client.get(f"/api/v1/campaigns/{second}/items").json()["items"][0]
    assert (item["status"], item["reason_code"]) == ("SKIPPED", "ALREADY_CONTACTED")
    assert messenger.calls == 1
    assert messenger.unique_messages == 1

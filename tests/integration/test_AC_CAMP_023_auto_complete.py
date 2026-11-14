"""Automatic completion once every item is terminal (AC-CAMP-023)."""

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


def test_AC_CAMP_023_all_terminal_items_complete_the_task_once(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given the last item turns terminal, when written back, then the task completes."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username="done_one", phone="+15555550171"),
        make_lead(username="done_two", phone="+15555550172"),
        make_lead(username="done_bad", phone="+15555559003"),
    ]
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "auto complete",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200

    worker.tick()

    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["status"] == "COMPLETED"
    assert detail["finished_at"] == "2026-11-14T09:00:00Z"
    counts = detail["counts"]
    assert (counts["success"], counts["failed"], counts["in_progress"]) == (2, 1, 0)

    audit = client.get(
        "/api/v1/audit-logs",
        params={"action": "CAMPAIGN_COMPLETED", "entity_id": str(campaign_id)},
    ).json()
    assert audit["total"] == 1
    assert audit["items"][0]["actor"] == "system:worker"

    worker.tick()
    again = client.get(
        "/api/v1/audit-logs",
        params={"action": "CAMPAIGN_COMPLETED", "entity_id": str(campaign_id)},
    ).json()
    assert again["total"] == 1
    assert client.get(f"/api/v1/campaigns/{campaign_id}").json()["status"] == (
        "COMPLETED"
    )


def test_AC_CAMP_023_open_items_prevent_completion(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given one item still waits for retry, when a tick ends, then the task stays RUNNING."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username="open_ok", phone="+15555550173"),
        make_lead(username="open_retry", phone="+15555559002"),
    ]
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "still open",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200

    worker.tick()

    assert client.get(f"/api/v1/campaigns/{campaign_id}").json()["status"] == "RUNNING"

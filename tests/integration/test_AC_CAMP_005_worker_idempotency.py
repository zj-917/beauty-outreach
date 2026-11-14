"""Runner idempotency over the whole pool (AC-CAMP-005)."""

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


def test_AC_CAMP_005_repeated_start_never_duplicates_messages(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given a RUNNING task, when started again, then unique messages equal recipients."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username=f"idem_{index}", phone=f"+15555550{400 + index}")
        for index in range(3)
    ]
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "idempotent",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    campaign_id = response.json()["id"]
    first_start = client.post(f"/api/v1/campaigns/{campaign_id}/start")
    assert first_start.status_code == 200
    second_start = client.post(f"/api/v1/campaigns/{campaign_id}/start")
    assert second_start.status_code == 200
    assert second_start.json()["status"] == "RUNNING"

    worker.tick()
    worker.tick()
    assert messenger.unique_messages == 3
    assert messenger.calls == 3

    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    worker.tick()
    assert messenger.unique_messages == 3
    assert messenger.calls == 3

    audit = client.get(
        "/api/v1/audit-logs",
        params={"action": "CAMPAIGN_STARTED", "entity_id": str(campaign_id)},
    ).json()
    assert audit["total"] == 1

    items = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]
    assert {item["status"] for item in items} == {"SENT"}
    assert len({item["provider_message_id"] for item in items}) == 3

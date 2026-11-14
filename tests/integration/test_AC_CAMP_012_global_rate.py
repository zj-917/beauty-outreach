"""Global rate limiting defers items and releases them when the window slides."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.worker import Worker
from app.models import SendLog
from app.providers.messenger.mock import MockMessenger
from app.services.seed_service import seed_defaults


def _seed(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _campaign(client: TestClient, template_id: int, lead_ids: list[int]) -> int:
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "rate limited",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    assert response.status_code == 201, response.text
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    return campaign_id


def _items(client: TestClient, campaign_id: int) -> dict[int, dict]:
    body = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()
    return {item["lead_id"]: item for item in body["items"]}


def test_AC_CAMP_012_global_limit_defers_then_window_slides(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given 7 items and a 5/10s global rule, when ticking, then 5 send and 2 defer."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username=f"rate_{index}", phone=f"+15555550{200 + index}")
        for index in range(7)
    ]
    campaign_id = _campaign(client, template_id, lead_ids)

    worker.tick()

    items = _items(client, campaign_id)
    sent = [item for item in items.values() if item["status"] == "SENT"]
    deferred = [item for item in items.values() if item["status"] == "PENDING"]
    assert len(sent) == 5
    assert len(deferred) == 2
    assert messenger.calls == 5
    for item in deferred:
        assert item["attempts"] == 0
        assert item["next_attempt_at"] == "2026-11-14T09:00:10Z"

    with Session(db) as session:
        logs = session.scalars(
            select(SendLog).where(
                SendLog.task_id == campaign_id,
                SendLog.phase == "GATE",
                SendLog.outcome == "DEFERRED",
            )
        ).all()
    assert len(logs) == 2
    assert {log.reason_code for log in logs} == {"RATE_LIMIT_GLOBAL"}
    assert all(log.detail == {"until": "2026-11-14T09:00:10Z"} for log in logs)

    clock.advance(11)
    worker.tick()

    items = _items(client, campaign_id)
    assert {item["status"] for item in items.values()} == {"SENT"}
    assert messenger.calls == 7
    assert messenger.unique_messages == 7

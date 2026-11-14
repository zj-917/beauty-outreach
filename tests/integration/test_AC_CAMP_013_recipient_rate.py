"""Per-recipient rate limiting across tasks."""

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


def _item(client: TestClient, campaign_id: int) -> dict:
    body = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()
    return body["items"][0]


def test_AC_CAMP_013_second_task_for_same_phone_is_rate_limited(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given one accepted message today, when another task targets it, then it skips."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="repeat_target", phone="+15555550171")
    first = _campaign(client, template_id, [lead_id], "first")
    worker.tick()
    assert _item(client, first)["status"] == "SENT"

    followup = client.post(
        "/api/v1/templates",
        json={"name": "followup", "body": "Again {{name}}", "language": "en"},
    ).json()
    assert (
        client.post(f"/api/v1/templates/{followup['id']}/approve").status_code
        == 200
    )
    second = _campaign(client, followup["id"], [lead_id], "second")

    worker.tick()

    item = _item(client, second)
    assert (item["status"], item["reason_code"]) == (
        "SKIPPED",
        "RECIPIENT_RATE_LIMITED",
    )
    assert messenger.calls == 1

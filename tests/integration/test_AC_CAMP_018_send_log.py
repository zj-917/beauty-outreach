"""Provider-call send log tests (AC-CAMP-018)."""

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
            "name": "provider log",
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


def test_AC_CAMP_018_each_provider_call_writes_one_log_row(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given accepted, permanent and retryable results, when ticking, then logs match."""
    template_id = _seed(client, db, clock)
    ok = make_lead(username="ok", phone="+15555550191")
    invalid = make_lead(username="invalid", phone="+15555559003")
    retry = make_lead(username="retry", phone="+15555559002")
    campaign_id = _campaign(client, template_id, [ok, invalid, retry])

    worker.tick()

    items = _items(client, campaign_id)
    assert items[ok]["status"] == "SENT"
    assert (items[invalid]["status"], items[invalid]["reason_code"]) == (
        "FAILED",
        "INVALID_NUMBER",
    )
    assert (items[retry]["status"], items[retry]["attempts"]) == ("RETRY_WAIT", 1)

    with Session(db) as session:
        logs = session.scalars(
            select(SendLog)
            .where(SendLog.task_id == campaign_id, SendLog.phase == "PROVIDER")
            .order_by(SendLog.id)
        ).all()
    assert len(logs) == 3
    assert sum(1 for log in logs if log.outcome == "ACCEPTED") == 1

    accepted = next(log for log in logs if log.outcome == "ACCEPTED")
    assert accepted.item_id == items[ok]["id"]
    assert accepted.attempt_no == 1
    assert accepted.reason_code is None
    assert accepted.provider_message_id == items[ok]["provider_message_id"]
    assert accepted.latency_ms is not None

    permanent = next(log for log in logs if log.outcome == "PERMANENT_ERROR")
    assert permanent.item_id == items[invalid]["id"]
    assert permanent.attempt_no == 1
    assert permanent.reason_code == "INVALID_NUMBER"

    retryable = next(log for log in logs if log.outcome == "RETRYABLE_ERROR")
    assert retryable.item_id == items[retry]["id"]
    assert retryable.reason_code == "SERVER_ERROR"

    for item in items.values():
        assert "+15555550" not in (item.get("last_error_code") or "")

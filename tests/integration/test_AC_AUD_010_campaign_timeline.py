"""Campaign event timeline (AC-AUD-010)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.worker import Worker
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
    return response.json()["id"]


def test_AC_AUD_010_timeline_lists_lifecycle_events_in_order(
    client: TestClient, db: Engine, clock: FakeClock, worker: Worker, make_lead
) -> None:
    """Given create/start/pause/resume/complete, when reading the timeline, then ordered."""
    template_id = _seed(client, db, clock)
    lead = make_lead(username="timeline_life", phone="+15555550291")
    campaign_id = _campaign(client, template_id, [lead], "timeline-life")

    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    clock.advance(60)
    assert client.post(f"/api/v1/campaigns/{campaign_id}/pause").status_code == 200
    clock.advance(60)
    assert client.post(f"/api/v1/campaigns/{campaign_id}/resume").status_code == 200
    clock.advance(60)
    worker.tick()

    response = client.get(f"/api/v1/campaigns/{campaign_id}/timeline")
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == campaign_id
    assert [event["event"] for event in body["events"]] == [
        "CREATED",
        "STARTED",
        "PAUSED",
        "RESUMED",
        "COMPLETED",
    ]
    timestamps = [event["ts"] for event in body["events"]]
    assert timestamps == sorted(timestamps)
    assert all(ts.endswith("Z") for ts in timestamps)
    assert [event["actor"] for event in body["events"]] == [
        "admin",
        "admin",
        "admin",
        "admin",
        "system:worker",
    ]


def test_AC_AUD_010_timeline_is_scoped_to_one_task(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given two campaigns, when reading one timeline, then the other task is absent."""
    template_id = _seed(client, db, clock)
    lead_a = make_lead(username="timeline_a", phone="+15555550292")
    lead_b = make_lead(username="timeline_b", phone="+15555550293")
    task_a = _campaign(client, template_id, [lead_a], "timeline-a")
    task_b = _campaign(client, template_id, [lead_b], "timeline-b")
    assert client.post(f"/api/v1/campaigns/{task_b}/start").status_code == 200

    body_a = client.get(f"/api/v1/campaigns/{task_a}/timeline").json()
    assert [event["event"] for event in body_a["events"]] == ["CREATED"]

    body_b = client.get(f"/api/v1/campaigns/{task_b}/timeline").json()
    assert [event["event"] for event in body_b["events"]] == ["CREATED", "STARTED"]


def test_AC_AUD_010_timeline_unknown_task_returns_404(
    client: TestClient,
) -> None:
    """Given no such campaign, when reading its timeline, then 404 NOT_FOUND."""
    response = client.get("/api/v1/campaigns/99999/timeline")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

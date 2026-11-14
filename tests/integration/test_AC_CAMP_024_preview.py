"""Dry-run gate preview without side effects (AC-CAMP-024)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
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
            "name": "preview",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    assert response.status_code == 201, response.text
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    return campaign_id


def _send_log_count(db: Engine) -> int:
    with Session(db) as session:
        return session.scalar(select(func.count()).select_from(SendLog)) or 0


def test_AC_CAMP_024_preview_reports_gate_distribution_without_side_effects(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given blocked and ready items, when previewing, then counts appear and nothing moves."""
    template_id = _seed(client, db, clock)
    blocked = make_lead(username="preview_blocked", phone="+15555550801")
    no_consent = make_lead(
        username="preview_noconsent", phone="+15555550802", consent=None
    )
    ready = make_lead(username="preview_ready", phone="+15555550803")
    assert (
        client.post(
            "/api/v1/suppressions",
            json={"type": "BLACKLIST", "phone": "+15555550801", "reason": "legal"},
        ).status_code
        == 201
    )
    campaign_id = _campaign(client, template_id, [blocked, no_consent, ready])

    response = client.post(f"/api/v1/campaigns/{campaign_id}/preview")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == campaign_id
    assert body["total_items"] == 3
    assert body["will_attempt"] == 1
    assert body["will_skip"] == {"BLACKLISTED": 1, "NO_CONSENT": 1}
    assert body["will_release"] == 0
    assert "note" in body
    assert _send_log_count(db) == 0
    assert messenger.calls == 0
    items = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]
    assert {item["status"] for item in items} == {"PENDING"}
    assert all(item["attempts"] == 0 for item in items)
    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["status"] == "RUNNING"


def test_AC_CAMP_024_preview_reports_disabled_template(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given the template is disabled, when previewing, then every item would skip."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username=f"preview_tpl_{index}", phone=f"+1555555081{index}")
        for index in range(2)
    ]
    campaign_id = _campaign(client, template_id, lead_ids)
    assert client.post(f"/api/v1/templates/{template_id}/disable").status_code == 200

    body = client.post(f"/api/v1/campaigns/{campaign_id}/preview").json()

    assert body["will_attempt"] == 0
    assert body["will_skip"] == {"TEMPLATE_NOT_APPROVED": 2}


def test_AC_CAMP_024_preview_reports_duplicate_contact(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    make_lead,
) -> None:
    """Given a prior accepted send with the same template, when previewing, then skip."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="preview_dup", phone="+15555550821")
    first = _campaign(client, template_id, [lead_id])
    worker.tick()
    assert (
        client.get(f"/api/v1/campaigns/{first}/items").json()["items"][0]["status"]
        == "SENT"
    )
    second = _campaign(client, template_id, [lead_id])

    body = client.post(f"/api/v1/campaigns/{second}/preview").json()

    assert body["will_attempt"] == 0
    assert body["will_skip"] == {"ALREADY_CONTACTED": 1}


def test_AC_CAMP_024_preview_releases_when_task_is_not_running(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given a paused task, when previewing, then gate 1 releases every open item."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username=f"preview_paused_{index}", phone=f"+1555555083{index}")
        for index in range(2)
    ]
    campaign_id = _campaign(client, template_id, lead_ids)
    assert client.post(f"/api/v1/campaigns/{campaign_id}/pause").status_code == 200

    body = client.post(f"/api/v1/campaigns/{campaign_id}/preview").json()

    assert body["will_attempt"] == 0
    assert body["will_release"] == 2
    assert body["will_skip"] == {}


def test_AC_CAMP_024_preview_counts_only_open_items(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    make_lead,
) -> None:
    """Given every item already sent, when previewing, then nothing remains to attempt."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username=f"preview_done_{index}", phone=f"+1555555084{index}")
        for index in range(2)
    ]
    campaign_id = _campaign(client, template_id, lead_ids)
    worker.tick()

    body = client.post(f"/api/v1/campaigns/{campaign_id}/preview").json()

    assert body["total_items"] == 0
    assert body["will_attempt"] == 0
    assert body["will_skip"] == {}


def test_AC_CAMP_024_preview_unknown_campaign_is_404(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given no such task, when previewing, then 404 is returned."""
    _seed(client, db, clock)
    assert client.post("/api/v1/campaigns/999/preview").status_code == 404

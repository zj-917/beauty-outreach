"""Campaign control endpoint tests for the state layer."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import CampaignTask, TaskItem
from app.services.seed_service import seed_defaults


def _prepare(client: TestClient, db: Engine, clock: FakeClock) -> int:
    """Seed defaults, import the mock batch, screen it and return the approved template id."""
    with Session(db) as session:
        seed_defaults(session, clock)
    assert client.post("/api/v1/lead-batches/import", json={"source": "mock"}).status_code == 201
    assert client.post("/api/v1/leads/screen").status_code == 200
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _campaign_in(client: TestClient, db: Engine, template_id: int, status: str) -> int:
    """Create a campaign and drive it to the requested status."""
    created = client.post(
        "/api/v1/campaigns",
        json={"name": f"in {status}", "template_id": template_id},
    )
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]
    if status in {"RUNNING", "PAUSED", "COMPLETED"}:
        assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    if status == "PAUSED":
        assert client.post(f"/api/v1/campaigns/{campaign_id}/pause").status_code == 200
    if status == "CANCELLED":
        assert client.post(f"/api/v1/campaigns/{campaign_id}/cancel").status_code == 200
    if status == "COMPLETED":
        with Session(db) as session:
            row = session.get(CampaignTask, campaign_id)
            assert row is not None
            row.status = "COMPLETED"
            session.commit()
    return campaign_id


def _audit_count(client: TestClient, action: str, campaign_id: int) -> int:
    body = client.get(
        "/api/v1/audit-logs",
        params={"action": action, "entity_id": str(campaign_id)},
    ).json()
    return body["total"]


@pytest.mark.parametrize(
    ("status", "action", "expected"),
    [
        ("DRAFT", "start", "RUNNING"),
        ("DRAFT", "pause", None),
        ("DRAFT", "resume", None),
        ("DRAFT", "cancel", "CANCELLED"),
        ("RUNNING", "start", "RUNNING"),
        ("RUNNING", "pause", "PAUSED"),
        ("RUNNING", "resume", None),
        ("RUNNING", "cancel", "CANCELLED"),
        ("PAUSED", "start", None),
        ("PAUSED", "pause", None),
        ("PAUSED", "resume", "RUNNING"),
        ("PAUSED", "cancel", "CANCELLED"),
        ("COMPLETED", "start", None),
        ("COMPLETED", "pause", None),
        ("COMPLETED", "resume", None),
        ("COMPLETED", "cancel", None),
        ("CANCELLED", "start", None),
        ("CANCELLED", "pause", None),
        ("CANCELLED", "resume", None),
        ("CANCELLED", "cancel", None),
    ],
)
def test_AC_CAMP_004_control_matrix(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    status: str,
    action: str,
    expected: str | None,
) -> None:
    """Given each status/action pair, when called, then the result matches §4 exactly."""
    template_id = _prepare(client, db, clock)
    campaign_id = _campaign_in(client, db, template_id, status)

    response = client.post(f"/api/v1/campaigns/{campaign_id}/{action}")

    if expected is None:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CAMPAIGN_INVALID_STATE"
        detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
        assert detail["status"] == status
    else:
        assert response.status_code == 200, response.text
        assert response.json()["id"] == campaign_id
        assert response.json()["status"] == expected
        detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
        assert detail["status"] == expected


def test_AC_CAMP_004_repeat_start_is_an_audit_free_noop(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a RUNNING task, when started again, then 200 with no new audit record."""
    template_id = _prepare(client, db, clock)
    campaign_id = _campaign_in(client, db, template_id, "RUNNING")
    assert _audit_count(client, "CAMPAIGN_STARTED", campaign_id) == 1

    response = client.post(f"/api/v1/campaigns/{campaign_id}/start")

    assert response.status_code == 200
    assert response.json()["status"] == "RUNNING"
    assert _audit_count(client, "CAMPAIGN_STARTED", campaign_id) == 1


def test_AC_CAMP_004_pause_sets_reason_and_resume_clears_failures(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a running task with failures, when paused and resumed, then flags are updated."""
    template_id = _prepare(client, db, clock)
    campaign_id = _campaign_in(client, db, template_id, "RUNNING")
    with Session(db) as session:
        row = session.get(CampaignTask, campaign_id)
        assert row is not None
        row.consecutive_failures = 3
        session.commit()

    assert client.post(f"/api/v1/campaigns/{campaign_id}/pause").status_code == 200
    paused = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert paused["status"] == "PAUSED"
    assert paused["pause_reason"] == "MANUAL"
    assert paused["paused_at"] == "2026-11-14T09:00:00Z"
    assert paused["consecutive_failures"] == 3

    items_before = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]

    assert client.post(f"/api/v1/campaigns/{campaign_id}/resume").status_code == 200
    resumed = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert resumed["status"] == "RUNNING"
    assert resumed["pause_reason"] is None
    assert resumed["consecutive_failures"] == 0

    items_after = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]
    assert [{k: item[k] for k in ("id", "status", "attempts")} for item in items_after] == [
        {k: item[k] for k in ("id", "status", "attempts")} for item in items_before
    ]


def test_AC_CAMP_004_cancel_skips_open_items(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a running task, when cancelled, then open items become SKIPPED(TASK_CANCELLED)."""
    template_id = _prepare(client, db, clock)
    campaign_id = _campaign_in(client, db, template_id, "RUNNING")
    with Session(db) as session:
        rows = session.scalars(
            select(TaskItem).where(TaskItem.task_id == campaign_id)
        ).all()
        rows[0].status = "SENT"
        for row in rows[1:]:
            row.status = "RETRY_WAIT"
        session.commit()

    assert client.post(f"/api/v1/campaigns/{campaign_id}/cancel").status_code == 200

    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["status"] == "CANCELLED"
    assert detail["finished_at"] == "2026-11-14T09:00:00Z"
    items = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]
    statuses = {item["status"] for item in items}
    assert statuses == {"SENT", "SKIPPED"}
    skipped = [item for item in items if item["status"] == "SKIPPED"]
    assert {item["reason_code"] for item in skipped} == {"TASK_CANCELLED"}
    assert _audit_count(client, "CAMPAIGN_CANCELLED", campaign_id) == 1

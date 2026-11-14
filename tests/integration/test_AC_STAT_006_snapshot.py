"""Snapshot consistency of task stats (AC-STAT-006)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.worker import Worker
from app.models import AuditLog, SendLog, TaskItem
from app.services.seed_service import seed_defaults

LAYOUT = [
    ("SENT", 1, None),
    ("SENT", 1, None),
    ("DELIVERED", 1, None),
    ("READ", 3, None),
    ("FAILED", 1, "INVALID_NUMBER"),
    ("FAILED", 3, "MAX_ATTEMPTS_EXCEEDED"),
    ("SKIPPED", 0, "BLACKLISTED"),
    ("SKIPPED", 0, "BLACKLISTED"),
    ("SKIPPED", 0, "NO_PHONE"),
    ("PENDING", 0, None),
    ("PENDING", 0, None),
    ("RETRY_WAIT", 2, None),
]


def _layout_campaign(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    template_id = next(
        item["id"]
        for item in client.get("/api/v1/templates").json()
        if item["name"] == "greeting"
    )
    lead_ids = [
        make_lead(username=f"snapshot_{index}", phone=f"+1555559{index:04d}")
        for index in range(len(LAYOUT))
    ]
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "snapshot",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    assert response.status_code == 201, response.text
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    with Session(db) as session:
        rows = session.scalars(
            select(TaskItem)
            .where(TaskItem.task_id == campaign_id)
            .order_by(TaskItem.id)
        ).all()
        for row, (status, attempts, reason) in zip(rows, LAYOUT, strict=True):
            row.status = status
            row.attempts = attempts
            row.reason_code = reason
        session.commit()
    return campaign_id


def _assert_self_consistent(body: dict) -> None:
    by_status = body["by_status"]
    assert sum(by_status.values()) == body["total"]
    assert body["success"] == by_status["SENT"] + by_status["DELIVERED"] + by_status["READ"]
    assert body["failed"] == by_status["FAILED"]
    assert body["skipped"] == by_status["SKIPPED"]
    assert body["in_progress"] == (
        by_status["PENDING"] + by_status["SENDING"] + by_status["RETRY_WAIT"]
    )
    assert sum(body["skip_reasons"].values()) == body["skipped"]
    assert sum(body["failure_reasons"].values()) == body["failed"]
    assert sum(body["attempts_histogram"].values()) == body["total"]
    assert body["retry_total"] == sum(
        (int(attempts) - 1) * count
        for attempts, count in body["attempts_histogram"].items()
        if int(attempts) >= 1
    )


def test_AC_STAT_006_one_read_is_internally_consistent_and_write_free(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    make_lead,
) -> None:
    """Given a mixed task, when reading around a worker write, then each read is consistent."""
    campaign_id = _layout_campaign(client, db, clock, make_lead)
    with Session(db) as session:
        logs_before = session.scalar(select(func.count()).select_from(SendLog))
        audits_before = session.scalar(select(func.count()).select_from(AuditLog))

    first = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()
    _assert_self_consistent(first)
    assert first["status"] == "RUNNING"

    with Session(db) as session:
        assert session.scalar(select(func.count()).select_from(SendLog)) == logs_before
        assert session.scalar(select(func.count()).select_from(AuditLog)) == audits_before

    worker.tick()

    second = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()
    _assert_self_consistent(second)
    assert second["status"] == "COMPLETED"
    assert second["by_status"]["SENT"] == 5
    assert second["in_progress"] == 0
    assert second["finished_at"] is not None
    assert second["elapsed_seconds"] is not None

"""Campaign list summaries agree with task stats (AC-STAT-007)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import TaskItem
from app.services.seed_service import seed_defaults

LAYOUT = [
    ("SENT", 1, None),
    ("DELIVERED", 2, None),
    ("FAILED", 1, "INVALID_NUMBER"),
    ("SKIPPED", 0, "NO_PHONE"),
    ("PENDING", 0, None),
]


def _seed(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    return next(
        item["id"]
        for item in client.get("/api/v1/templates").json()
        if item["name"] == "greeting"
    )


def _create(
    client: TestClient, template_id: int, lead_ids: list[int], name: str
) -> int:
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


def test_AC_STAT_007_list_summary_matches_each_task_stats(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given two tasks, when listing campaigns, then each summary equals its /stats."""
    template_id = _seed(client, db, clock)
    mixed_id = _create(
        client,
        template_id,
        [
            make_lead(username=f"summary_{index}", phone=f"+1555550{index:04d}")
            for index in range(len(LAYOUT))
        ],
        "summary-mixed",
    )
    assert client.post(f"/api/v1/campaigns/{mixed_id}/start").status_code == 200
    with Session(db) as session:
        rows = session.scalars(
            select(TaskItem)
            .where(TaskItem.task_id == mixed_id)
            .order_by(TaskItem.id)
        ).all()
        for row, (status, attempts, reason) in zip(rows, LAYOUT, strict=True):
            row.status = status
            row.attempts = attempts
            row.reason_code = reason
        session.commit()
    draft_id = _create(
        client,
        template_id,
        [
            make_lead(username="summary_draft_a", phone="+15555559901"),
            make_lead(username="summary_draft_b", phone="+15555559902"),
        ],
        "summary-draft",
    )

    listing = client.get("/api/v1/campaigns", params={"page_size": 100}).json()
    summaries = {row["id"]: row["counts"] for row in listing["items"]}

    for campaign_id in (mixed_id, draft_id):
        stats = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()
        counts = summaries[campaign_id]
        for key in ("total", "success", "failed", "skipped", "in_progress"):
            assert counts[key] == stats[key], (campaign_id, key)
        assert counts["by_status"] == stats["by_status"]

    assert summaries[draft_id]["in_progress"] == 2
    assert summaries[mixed_id]["success"] == 2

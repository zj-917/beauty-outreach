"""Task result statistics (AC-STAT-001..004)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import TaskItem
from app.services.seed_service import seed_defaults

# (status, attempts, reason_code) for twelve items: 4 success, 2 failed,
# 3 skipped, 3 in progress.
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


def _template_id(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _create(
    client: TestClient,
    template_id: int,
    lead_ids: list[int],
    name: str,
    *,
    started: bool = True,
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
    campaign_id = response.json()["id"]
    if started:
        assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    return campaign_id


def _apply_layout(db: Engine, campaign_id: int) -> None:
    with Session(db) as session:
        rows = session.scalars(
            select(TaskItem)
            .where(TaskItem.task_id == campaign_id)
            .order_by(TaskItem.id)
        ).all()
        assert len(rows) == len(LAYOUT)
        for row, (status, attempts, reason) in zip(rows, LAYOUT, strict=True):
            row.status = status
            row.attempts = attempts
            row.reason_code = reason
        session.commit()


def _layout_campaign(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    make_lead,
    *,
    name: str = "stats-layout",
) -> int:
    template_id = _template_id(client, db, clock)
    lead_ids = [
        make_lead(username=f"{name}_{index}", phone=f"+1555557{index:04d}")
        for index in range(len(LAYOUT))
    ]
    campaign_id = _create(client, template_id, lead_ids, name)
    _apply_layout(db, campaign_id)
    return campaign_id


def test_AC_STAT_001_by_status_has_all_eight_statuses_and_sums_to_total(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given a mixed task, when reading stats, then eight statuses sum to total."""
    campaign_id = _layout_campaign(client, db, clock, make_lead)

    body = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()

    assert body["task_id"] == campaign_id
    assert body["status"] == "RUNNING"
    assert set(body["by_status"]) == {
        "PENDING",
        "SENDING",
        "RETRY_WAIT",
        "SENT",
        "DELIVERED",
        "READ",
        "FAILED",
        "SKIPPED",
    }
    assert body["by_status"]["SENDING"] == 0
    assert sum(body["by_status"].values()) == body["total"] == len(LAYOUT)


def test_AC_STAT_002_summary_metrics_match_the_layout(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given 4 success, 2 failed, 3 skipped, 3 open, when reading, then figures match."""
    campaign_id = _layout_campaign(client, db, clock, make_lead)
    clock.advance(90)

    body = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()

    assert body["total"] == 12
    assert (body["success"], body["failed"], body["skipped"], body["in_progress"]) == (
        4,
        2,
        3,
        3,
    )
    assert body["success_rate"] == 0.6667
    assert body["elapsed_seconds"] == 90.0
    assert body["started_at"].endswith("Z")
    assert body["finished_at"] is None


def test_AC_STAT_002_success_rate_is_null_without_decided_items(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given a draft task with only PENDING items, when reading, then rate and elapsed are null."""
    template_id = _template_id(client, db, clock)
    lead_ids = [
        make_lead(username=f"stats_draft_{index}", phone=f"+1555558{index:04d}")
        for index in range(2)
    ]
    campaign_id = _create(client, template_id, lead_ids, "stats-draft", started=False)

    body = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()

    assert body["status"] == "DRAFT"
    assert body["success_rate"] is None
    assert body["elapsed_seconds"] is None
    assert body["started_at"] is None
    assert body["by_status"]["PENDING"] == 2
    assert body["in_progress"] == 2


def test_AC_STAT_003_skip_and_failure_reasons_are_grouped(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given skips and failures with codes, when reading, then reason maps count them."""
    campaign_id = _layout_campaign(client, db, clock, make_lead)

    body = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()

    assert body["skip_reasons"] == {"BLACKLISTED": 2, "NO_PHONE": 1}
    assert body["failure_reasons"] == {
        "INVALID_NUMBER": 1,
        "MAX_ATTEMPTS_EXCEEDED": 1,
    }


def test_AC_STAT_004_attempts_histogram_and_retry_total(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given attempts 0/1/2/3 across items, when reading, then histogram and retries match."""
    campaign_id = _layout_campaign(client, db, clock, make_lead)

    body = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()

    assert body["attempts_histogram"] == {"0": 5, "1": 4, "2": 1, "3": 2}
    assert body["retry_total"] == 5

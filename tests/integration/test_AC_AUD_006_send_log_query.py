"""Send log query API (AC-AUD-006)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.repositories import send_log_repo
from app.services.seed_service import seed_defaults


def _seed(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _campaign(
    client: TestClient, template_id: int, lead_ids: list[int], name: str
) -> tuple[int, list[int]]:
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
    body = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()
    return campaign_id, [item["id"] for item in body["items"]]


def _log(
    db: Engine,
    *,
    task_id: int,
    item_id: int,
    phase: str,
    outcome: str,
    reason_code: str | None = None,
    created_at: datetime,
) -> int:
    with Session(db) as session:
        log_id = send_log_repo.insert(
            session,
            task_id=task_id,
            item_id=item_id,
            phone_hash="query-phone-hash",
            phone_masked="+155****0191",
            phase=phase,
            outcome=outcome,
            reason_code=reason_code,
            attempt_no=1 if phase == "PROVIDER" else None,
            created_at=created_at,
        )
        session.commit()
        return log_id


def test_AC_AUD_006_send_logs_filter_by_task_and_item(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given logs in two tasks, when filtering by task or item, then only matches return."""
    template_id = _seed(client, db, clock)
    lead_a1 = make_lead(username="log_a1", phone="+15555550191")
    lead_a2 = make_lead(username="log_a2", phone="+15555550192")
    lead_b1 = make_lead(username="log_b1", phone="+15555550193")
    task_a, items_a = _campaign(client, template_id, [lead_a1, lead_a2], "logs-a")
    task_b, items_b = _campaign(client, template_id, [lead_b1], "logs-b")
    now = clock.now()
    log_a1 = _log(
        db,
        task_id=task_a,
        item_id=items_a[0],
        phase="GATE",
        outcome="BLOCKED",
        reason_code="SUPPRESSED",
        created_at=now,
    )
    log_a2 = _log(
        db,
        task_id=task_a,
        item_id=items_a[1],
        phase="PROVIDER",
        outcome="ACCEPTED",
        created_at=now,
    )
    log_b1 = _log(
        db,
        task_id=task_b,
        item_id=items_b[0],
        phase="PROVIDER",
        outcome="ACCEPTED",
        created_at=now,
    )

    by_task = client.get("/api/v1/send-logs", params={"task_id": task_a}).json()
    assert by_task["total"] == 2
    assert {row["id"] for row in by_task["items"]} == {log_a1, log_a2}

    by_item = client.get("/api/v1/send-logs", params={"item_id": items_b[0]}).json()
    assert by_item["total"] == 1
    assert by_item["items"][0]["id"] == log_b1
    assert by_item["items"][0]["task_id"] == task_b


def test_AC_AUD_006_send_logs_filter_by_phase_outcome_and_reason(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given mixed phases, when filtering by phase/outcome/reason, then rows match."""
    template_id = _seed(client, db, clock)
    lead = make_lead(username="log_mixed", phone="+15555550194")
    task_id, items = _campaign(client, template_id, [lead], "logs-mixed")
    now = clock.now()
    blocked = _log(
        db,
        task_id=task_id,
        item_id=items[0],
        phase="GATE",
        outcome="BLOCKED",
        reason_code="SUPPRESSED",
        created_at=now,
    )
    deferred = _log(
        db,
        task_id=task_id,
        item_id=items[0],
        phase="GATE",
        outcome="DEFERRED",
        reason_code="QUIET_HOURS",
        created_at=now,
    )
    accepted = _log(
        db,
        task_id=task_id,
        item_id=items[0],
        phase="PROVIDER",
        outcome="ACCEPTED",
        created_at=now,
    )
    retryable = _log(
        db,
        task_id=task_id,
        item_id=items[0],
        phase="PROVIDER",
        outcome="RETRYABLE_ERROR",
        reason_code="SERVER_ERROR",
        created_at=now,
    )

    gate = client.get("/api/v1/send-logs", params={"phase": "GATE"}).json()
    assert {row["id"] for row in gate["items"]} == {blocked, deferred}

    deferred_only = client.get(
        "/api/v1/send-logs", params={"outcome": "DEFERRED"}
    ).json()
    assert [row["id"] for row in deferred_only["items"]] == [deferred]

    server_errors = client.get(
        "/api/v1/send-logs", params={"reason_code": "SERVER_ERROR"}
    ).json()
    assert [row["id"] for row in server_errors["items"]] == [retryable]

    combined = client.get(
        "/api/v1/send-logs", params={"phase": "PROVIDER", "outcome": "ACCEPTED"}
    ).json()
    assert [row["id"] for row in combined["items"]] == [accepted]


def test_AC_AUD_006_send_logs_filter_by_time_range(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given logs at three hours, when filtering from/to, then the range is inclusive."""
    template_id = _seed(client, db, clock)
    lead = make_lead(username="log_time", phone="+15555550195")
    task_id, items = _campaign(client, template_id, [lead], "logs-time")
    ids = [
        _log(
            db,
            task_id=task_id,
            item_id=items[0],
            phase="PROVIDER",
            outcome="ACCEPTED",
            created_at=datetime(2026, 11, 14, hour, 0, tzinfo=UTC),
        )
        for hour in (9, 10, 11)
    ]

    hour_ten = client.get(
        "/api/v1/send-logs",
        params={"from": "2026-11-14T10:00:00Z", "to": "2026-11-14T10:00:00Z"},
    ).json()
    assert [row["id"] for row in hour_ten["items"]] == [ids[1]]

    ten_to_eleven = client.get(
        "/api/v1/send-logs",
        params={"from": "2026-11-14T10:00:00Z", "to": "2026-11-14T11:00:00Z"},
    ).json()
    assert {row["id"] for row in ten_to_eleven["items"]} == {ids[1], ids[2]}

    early = client.get(
        "/api/v1/send-logs", params={"to": "2026-11-14T09:30:00Z"}
    ).json()
    assert [row["id"] for row in early["items"]] == [ids[0]]


def test_AC_AUD_006_send_logs_paginate_newest_first_with_masked_phone(
    client: TestClient, db: Engine, clock: FakeClock, make_lead
) -> None:
    """Given three logs, when paging, then newest-first pages hold only masked phones."""
    template_id = _seed(client, db, clock)
    lead = make_lead(username="log_page", phone="+15555550191")
    task_id, items = _campaign(client, template_id, [lead], "logs-page")
    ids = [
        _log(
            db,
            task_id=task_id,
            item_id=items[0],
            phase="PROVIDER",
            outcome="ACCEPTED",
            created_at=datetime(2026, 11, 14, 9, minute, tzinfo=UTC),
        )
        for minute in (0, 10, 20)
    ]

    first = client.get(
        "/api/v1/send-logs", params={"task_id": task_id, "page_size": 2}
    ).json()
    assert first["total"] == 3
    assert [row["id"] for row in first["items"]] == [ids[2], ids[1]]

    second = client.get(
        "/api/v1/send-logs",
        params={"task_id": task_id, "page_size": 2, "page": 2},
    ).json()
    assert [row["id"] for row in second["items"]] == [ids[0]]

    body = client.get("/api/v1/send-logs", params={"task_id": task_id})
    assert "+15555550191" not in body.text
    row = body.json()["items"][0]
    assert row["phone_masked"] == "+155****0191"
    assert "phone_hash" not in row
    assert row["created_at"].endswith("Z")

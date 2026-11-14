"""Global stats overview (AC-STAT-005)."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.worker import Worker
from app.repositories import send_log_repo
from app.services.seed_service import seed_defaults


def _template_id(client: TestClient, db: Engine, clock: FakeClock) -> int:
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


def test_AC_STAT_005_overview_counts_match_the_tables(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    make_lead,
) -> None:
    """Given leads, consents, suppressions and a finished task, when reading, then counts match."""
    template_id = _template_id(client, db, clock)
    make_lead(username="ov_new", phone="+15555561001", status="NEW")
    make_lead(username="ov_pending", phone="+15555561002", status="PENDING_REVIEW")
    lead_ok = make_lead(username="ov_ok", phone="+15555561003")
    lead_revoked = make_lead(
        username="ov_revoked", phone="+15555561004", consent="REVOKED"
    )
    make_lead(username="ov_rejected", phone="+15555561005", status="REJECTED")
    make_lead(username="ov_discarded", phone="+15555561006", status="DISCARDED")

    blacklist = client.post(
        "/api/v1/suppressions",
        json={"type": "BLACKLIST", "phone": "+15555561005", "reason": "manual"},
    )
    assert blacklist.status_code == 201, blacklist.text
    unsubscribe = client.post(
        "/api/v1/suppressions",
        json={
            "type": "UNSUBSCRIBE",
            "username": "ov_discarded",
            "reason": "manual",
        },
    )
    assert unsubscribe.status_code == 201, unsubscribe.text

    finished = _campaign(client, template_id, [lead_ok], "overview-sent")
    assert client.post(f"/api/v1/campaigns/{finished}/start").status_code == 200
    worker.tick()
    _campaign(client, template_id, [lead_revoked], "overview-draft")

    item_id = client.get(f"/api/v1/campaigns/{finished}/items").json()["items"][0]["id"]
    with Session(db) as session:
        send_log_repo.insert(
            session,
            task_id=finished,
            item_id=item_id,
            phone_hash="old-accepted",
            phone_masked="+155****1003",
            phase="PROVIDER",
            outcome="ACCEPTED",
            created_at=clock.now() - timedelta(hours=25),
        )
        session.commit()

    body = client.get("/api/v1/stats/overview").json()

    assert body["leads_by_status"] == {
        "NEW": 1,
        "PENDING_REVIEW": 1,
        "APPROVED": 2,
        "REJECTED": 1,
        "DISCARDED": 1,
    }
    assert body["pool_size"] == 2
    assert body["campaigns_by_status"] == {
        "DRAFT": 1,
        "RUNNING": 0,
        "PAUSED": 0,
        "COMPLETED": 1,
        "CANCELLED": 0,
    }
    assert body["accepted_last_24h"] == 1
    assert body["suppressions_by_type"] == {"BLACKLIST": 1, "UNSUBSCRIBE": 1}
    assert body["consents_by_status"] == {"GRANTED": 5, "REVOKED": 1}

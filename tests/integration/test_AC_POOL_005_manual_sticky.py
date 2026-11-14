"""Manual decision stickiness tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import Keyword, Lead
from app.services.seed_service import seed_defaults


def _prepare(client: TestClient, db: Engine, clock: FakeClock) -> None:
    with Session(db) as session:
        seed_defaults(session, clock)
    assert (
        client.post(
            "/api/v1/lead-batches/import", json={"source": "mock"}
        ).status_code
        == 201
    )
    assert client.post("/api/v1/leads/screen").status_code == 200


def _lead_ids(db: Engine, status: str, count: int) -> list[int]:
    with Session(db) as session:
        rows = session.scalars(
            select(Lead).where(Lead.status == status).order_by(Lead.id).limit(count)
        ).all()
        assert len(rows) == count
        return [row.id for row in rows]


def test_AC_POOL_005_manual_decisions_survive_rescoring(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given manual decisions, when keywords change and leads are rescored, then decisions stick."""
    _prepare(client, db, clock)
    approved_id, rejected_id = _lead_ids(db, "PENDING_REVIEW", 2)

    assert (
        client.post(
            f"/api/v1/leads/{approved_id}/review",
            json={"decision": "APPROVE"},
            headers={"X-Operator": "alice"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/leads/{rejected_id}/review",
            json={"decision": "REJECT", "note": "not a fit"},
            headers={"X-Operator": "bob"},
        ).status_code
        == 200
    )

    with Session(db) as session:
        session.execute(update(Keyword).values(enabled=False))
        session.commit()

    report = client.post("/api/v1/leads/screen").json()
    assert report["processed"] == 22

    approved = client.get(f"/api/v1/leads/{approved_id}").json()
    assert approved["status"] == "APPROVED"
    assert approved["decision_source"] == "MANUAL"
    assert approved["reviewed_by"] == "alice"
    assert approved["reviewed_at"] == "2026-11-14T09:00:00Z"

    rejected = client.get(f"/api/v1/leads/{rejected_id}").json()
    assert rejected["status"] == "REJECTED"
    assert rejected["decision_source"] == "MANUAL"
    assert rejected["reviewed_by"] == "bob"
    assert rejected["review_note"] == "not a fit"

    for lead_id in (approved_id, rejected_id):
        audits = client.get(
            "/api/v1/audit-logs",
            params={
                "action": "LEAD_REVIEWED",
                "entity_type": "lead",
                "entity_id": str(lead_id),
            },
        ).json()
        assert audits["total"] == 1

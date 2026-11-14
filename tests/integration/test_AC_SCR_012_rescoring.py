"""Re-screening stickiness tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import Keyword, Lead
from app.services.seed_service import seed_defaults


def _seed(db: Engine, clock: FakeClock) -> None:
    with Session(db) as session:
        seed_defaults(session, clock)


def _lead_id(db: Engine, status: str) -> int:
    with Session(db) as session:
        row = session.scalar(
            select(Lead).where(Lead.status == status).order_by(Lead.id).limit(1)
        )
        assert row is not None
        return row.id


def test_AC_SCR_012_rescoring_updates_only_machine_decided_leads(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given keyword changes, then pending/discarded are rescored and manual decisions stick."""
    _seed(db, clock)
    response = client.post("/api/v1/lead-batches/import", json={"source": "mock"})
    assert response.status_code == 201
    first = client.post("/api/v1/leads/screen").json()
    assert (first["approved"], first["pending_review"], first["discarded"]) == (20, 8, 16)

    pending_id = _lead_id(db, "PENDING_REVIEW")
    discarded_id = _lead_id(db, "DISCARDED")
    with Session(db) as session:
        session.get(Lead, pending_id).status = "APPROVED"
        session.get(Lead, pending_id).decision_source = "MANUAL"
        session.get(Lead, discarded_id).status = "REJECTED"
        session.get(Lead, discarded_id).decision_source = "MANUAL"
        session.execute(update(Keyword).values(enabled=False))
        session.commit()

    second = client.post("/api/v1/leads/screen").json()
    assert (second["processed"], second["approved"], second["pending_review"]) == (
        22,
        0,
        0,
    )
    assert (second["discarded"], second["unchanged"]) == (22, 15)

    with Session(db) as session:
        manual_approved = session.get(Lead, pending_id)
        manual_rejected = session.get(Lead, discarded_id)
        assert manual_approved.status == "APPROVED"
        assert manual_approved.decision_source == "MANUAL"
        assert manual_rejected.status == "REJECTED"
        assert manual_rejected.decision_source == "MANUAL"
        remaining = session.scalars(
            select(Lead).where(Lead.status.in_(["NEW", "PENDING_REVIEW"]))
        ).all()
        assert remaining == []


def test_AC_SCR_012_new_keyword_changes_rescored_decisions(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a new keyword, then previously discarded leads are rescored and re-decided."""
    _seed(db, clock)
    client.post("/api/v1/lead-batches/import", json={"source": "mock"})
    client.post("/api/v1/leads/screen")
    fitness_id = _lead_id(db, "DISCARDED")
    with Session(db) as session:
        fitness = session.get(Lead, fitness_id)
        username = fitness.username
        assert fitness.score is not None and fitness.score < 40

    created = client.post(
        "/api/v1/keywords",
        json={"term": "fitness", "kind": "POSITIVE", "weight": 50},
    )
    assert created.status_code == 201
    body = client.post("/api/v1/leads/screen").json()
    assert (body["pending_review"], body["discarded"], body["unchanged"]) == (9, 15, 23)

    leads = client.get("/api/v1/leads", params={"q": username}).json()["items"]
    assert len(leads) == 1
    assert leads[0]["status"] == "PENDING_REVIEW"
    assert leads[0]["score"] == 65
    assert leads[0]["top_keyword"] == "fitness"

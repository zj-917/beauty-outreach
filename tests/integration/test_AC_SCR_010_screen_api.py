"""Screening API and decision integration tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import Keyword
from app.services.seed_service import seed_defaults


def _seed(db: Engine, clock: FakeClock) -> None:
    with Session(db) as session:
        seed_defaults(session, clock)


def _import_mock(client: TestClient) -> None:
    response = client.post("/api/v1/lead-batches/import", json={"source": "mock"})
    assert response.status_code == 201


def test_AC_SCR_010_mock_dataset_lands_in_expected_buckets(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given the mock dataset, when screened, then decisions follow the expected labels."""
    _seed(db, clock)
    _import_mock(client)
    response = client.post("/api/v1/leads/screen")
    assert response.status_code == 200
    body = response.json()
    assert (body["processed"], body["approved"], body["pending_review"]) == (44, 20, 8)
    assert (body["discarded"], body["unchanged"]) == (16, 0)
    assert body["warning"] is None
    assert client.get("/api/v1/leads", params={"status": "APPROVED"}).json()["total"] == 20
    assert (
        client.get("/api/v1/leads", params={"status": "PENDING_REVIEW"}).json()["total"]
        == 8
    )
    assert (
        client.get("/api/v1/leads", params={"status": "DISCARDED"}).json()["total"] == 16
    )
    assert client.get("/api/v1/leads", params={"min_score": 70}).json()["total"] == 20


def test_AC_SCR_010_auto_approve_off_sends_high_scores_to_review(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given auto-approve disabled, when screened, then no lead is auto-approved."""
    _seed(db, clock)
    _import_mock(client)
    client.put(
        "/api/v1/settings", json={"screening.auto_approve_enabled": False}
    )
    body = client.post("/api/v1/leads/screen", json={}).json()
    assert (body["approved"], body["pending_review"], body["discarded"]) == (0, 28, 16)


def test_AC_SCR_010_no_enabled_keywords_warns(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given no enabled keywords, when screened, then a warning is returned and nothing breaks."""
    _seed(db, clock)
    _import_mock(client)
    with Session(db) as session:
        session.execute(update(Keyword).values(enabled=False))
        session.commit()
        assert session.scalar(select(Keyword).where(Keyword.enabled.is_(True))) is None
    body = client.post("/api/v1/leads/screen").json()
    assert body["warning"] == "NO_ENABLED_KEYWORDS"
    assert (body["processed"], body["approved"], body["pending_review"]) == (44, 0, 0)
    assert body["discarded"] == 44


def test_AC_SCR_010_screening_can_target_ids(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given explicit lead ids, when screening, then only those leads are processed."""
    _seed(db, clock)
    _import_mock(client)
    ids = [
        item["id"]
        for item in client.get("/api/v1/leads", params={"page_size": 2}).json()["items"]
    ]
    body = client.post("/api/v1/leads/screen", json={"lead_ids": ids}).json()
    assert body["processed"] == 2
    assert body["approved"] + body["pending_review"] + body["discarded"] == 2

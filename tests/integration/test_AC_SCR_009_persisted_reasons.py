"""Persisted score explanation tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.services.seed_service import seed_defaults


def test_AC_SCR_009_reasons_and_top_keyword_are_persisted_and_consistent(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a screened lead, when read back, then reasons sum to score and top_keyword is set."""
    with Session(db) as session:
        seed_defaults(session, clock)
    client.post("/api/v1/lead-batches/import", json={"source": "mock"})
    client.post("/api/v1/leads/screen")

    lead = client.get("/api/v1/leads", params={"q": "glow.with.mia"}).json()["items"][0]
    assert lead["status"] == "APPROVED"
    assert lead["score"] == 100
    assert lead["top_keyword"] == "beauty device"
    assert sum(reason["delta"] for reason in lead["score_reasons"]) == lead["score"]
    assert all(
        {"code", "detail", "delta"} <= set(reason) for reason in lead["score_reasons"]
    )

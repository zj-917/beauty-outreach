"""Screening audit tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.services.seed_service import seed_defaults


def test_AC_SCR_013_each_run_writes_one_audit_row(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a screening run, then exactly one audit row records counts and thresholds."""
    with Session(db) as session:
        seed_defaults(session, clock)
    client.post("/api/v1/lead-batches/import", json={"source": "mock"})
    client.post("/api/v1/leads/screen")
    logs = client.get(
        "/api/v1/audit-logs", params={"action": "LEAD_SCREENING_RUN"}
    ).json()
    assert logs["total"] == 1
    item = logs["items"][0]
    assert item["after"] == {
        "processed": 44,
        "approved": 20,
        "pending_review": 8,
        "discarded": 16,
        "unchanged": 0,
        "threshold_high": 70,
        "threshold_low": 40,
        "auto_approve_enabled": True,
    }
    assert "+1555555" not in json.dumps(item)
    assert client.get("/api/v1/audit-logs/verify").json()["ok"] is True

    second = client.post("/api/v1/leads/screen").json()
    assert (second["processed"], second["unchanged"]) == (24, 24)
    logs = client.get(
        "/api/v1/audit-logs", params={"action": "LEAD_SCREENING_RUN"}
    ).json()
    assert logs["total"] == 2
    assert logs["items"][0]["after"]["processed"] == 24


def test_AC_SCR_013_batch_run_is_recorded_against_the_batch(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a batch-scoped run, then the audit points at the batch."""
    with Session(db) as session:
        seed_defaults(session, clock)
    response = client.post("/api/v1/lead-batches/import", json={"source": "mock"})
    batch_id = response.json()["id"]
    client.post("/api/v1/leads/screen", json={"batch_id": batch_id})
    item = client.get(
        "/api/v1/audit-logs", params={"action": "LEAD_SCREENING_RUN"}
    ).json()["items"][0]
    assert (item["entity_type"], item["entity_id"]) == ("lead_batch", str(batch_id))
    assert item["after"]["batch_id"] == batch_id

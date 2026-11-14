"""Demo helper endpoints (AC-SYS-012)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.core.config import Settings
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.main import create_app
from app.services.seed_service import seed_defaults


def _seed(db: Engine, clock: FakeClock) -> None:
    with Session(db) as session:
        seed_defaults(session, clock)


def test_AC_SYS_012_demo_routes_are_absent_when_disabled(
    settings: Settings, clock: FakeClock
) -> None:
    """Given DEMO_MODE=false, when a demo endpoint is called, then it is 404."""
    disabled = settings.model_copy(update={"demo_mode": False})
    app = create_app(settings=disabled, clock=clock)
    with TestClient(app, headers={"X-Admin-Token": settings.admin_token}) as client:
        response = client.post(
            "/demo/inbound-stop", json={"phone": "+15555550401"}
        )
    assert response.status_code == 404


def test_AC_SYS_012_inbound_stop_requires_token_and_processes(
    client: TestClient,
    anon_client: TestClient,
    db: Engine,
    clock: FakeClock,
    settings: Settings,
) -> None:
    """Given DEMO_MODE=true, when signed-in demo STOP runs, then suppression is created."""
    _seed(db, clock)

    unauthorized = anon_client.post(
        "/demo/inbound-stop", json={"phone": "+15555550401"}
    )
    assert unauthorized.status_code == 401

    response = client.post("/demo/inbound-stop", json={"phone": "+15555550401"})

    assert response.status_code == 200
    assert response.json() == {"action": "UNSUBSCRIBED"}
    suppressions = client.get("/api/v1/suppressions").json()
    assert len(suppressions) == 1
    assert suppressions[0]["source"] == "INBOUND_STOP"


def test_AC_SYS_012_flush_receipts_applies_queued_receipts(
    client: TestClient,
    app: FastAPI,
    db: Engine,
    clock: FakeClock,
    make_lead,
) -> None:
    """Given queued mock receipts, when flushing, then they are applied immediately."""
    _seed(db, clock)
    lead_id = make_lead(username="flush_target", phone="+15555550402")
    messenger = app.state.messenger
    processor = Processor(
        clock,
        app.state.phone_cipher,
        messenger,
        worker_id="demo-worker",
        audit=app.state.audit_service,
    )
    worker = Worker(
        app.state.session_factory, clock, processor, worker_id="demo-worker"
    )
    templates = client.get("/api/v1/templates").json()
    template_id = next(item["id"] for item in templates if item["name"] == "greeting")
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "flush",
            "template_id": template_id,
            "selection": {"lead_ids": [lead_id]},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    worker.tick()

    flushed = client.post("/demo/flush-receipts")

    assert flushed.status_code == 200
    assert flushed.json()["applied"] == 2
    item = client.get(f"/api/v1/campaigns/{campaign_id}/items").json()["items"][0]
    assert item["status"] == "READ"


def test_AC_SYS_012_reset_clears_and_reseeds(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given populated data, when reset runs, then leads and audits vanish but seeds remain."""
    _seed(db, clock)
    assert (
        client.post("/api/v1/lead-batches/import", json={"source": "mock"}).status_code
        == 201
    )
    assert client.get("/api/v1/leads").json()["total"] == 44
    assert client.get("/api/v1/audit-logs").json()["total"] == 1

    response = client.post("/demo/reset")

    assert response.status_code == 200
    assert response.json()["status"] == "reset"
    assert client.get("/api/v1/leads").json()["total"] == 0
    assert client.get("/api/v1/audit-logs").json()["total"] == 0
    templates = client.get("/api/v1/templates").json()
    assert [item["name"] for item in templates] == ["greeting"]
    assert client.get("/api/v1/settings").json()["sending.max_attempts"] == 3

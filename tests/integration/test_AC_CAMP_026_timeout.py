"""Provider call timeout handling (AC-CAMP-026)."""

from __future__ import annotations

import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.providers.messenger.base import ResultKind, SendResult
from app.services.seed_service import seed_defaults


def _seed(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


class _HangingMessenger:
    """Block inside send() until the test releases it."""

    name = "hanging"

    def __init__(self) -> None:
        self.calls = 0
        self.release = threading.Event()
        self.finished = threading.Event()

    def send(self, req) -> SendResult:
        self.calls += 1
        self.release.wait(2.0)
        self.finished.set()
        return SendResult(kind=ResultKind.ACCEPTED, provider_message_id="late")

    def poll_receipts(self) -> list:
        return []


def test_AC_CAMP_026_slow_provider_call_times_out(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given a call longer than the configured timeout, then it becomes TIMEOUT."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="hanging", phone="+15555550181")
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "timeout",
            "template_id": template_id,
            "selection": {"lead_ids": [lead_id]},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    assert (
        client.put(
            "/api/v1/settings", json={"sending.provider_timeout_seconds": 0.5}
        ).status_code
        == 200
    )
    messenger = _HangingMessenger()
    processor = Processor(
        clock,
        app.state.phone_cipher,
        messenger,
        worker_id="timeout-worker",
        audit=app.state.audit_service,
        rng=lambda: 0.0,
    )
    worker = Worker(
        app.state.session_factory, clock, processor, worker_id="timeout-worker"
    )

    try:
        worker.tick()
    finally:
        messenger.release.set()
        messenger.finished.wait(2.0)

    item = client.get(f"/api/v1/campaigns/{campaign_id}/items").json()["items"][0]
    assert (item["status"], item["last_error_code"]) == ("RETRY_WAIT", "TIMEOUT")
    assert item["attempts"] == 1
    assert messenger.calls == 1

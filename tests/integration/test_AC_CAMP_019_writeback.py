"""Item write-back fields after provider calls (AC-CAMP-019)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.models import TaskItem
from app.providers.messenger.base import ResultKind, SendResult
from app.services.seed_service import seed_defaults


def _seed(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _campaign(client: TestClient, template_id: int, lead_ids: list[int]) -> int:
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "write back",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    assert response.status_code == 201, response.text
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    return campaign_id


def _worker_with(app: FastAPI, clock: FakeClock, messenger) -> Worker:
    processor = Processor(
        clock,
        app.state.phone_cipher,
        messenger,
        worker_id="writeback-worker",
        audit=app.state.audit_service,
        rng=lambda: 0.0,
    )
    return Worker(
        app.state.session_factory, clock, processor, worker_id="writeback-worker"
    )


class _ScriptedMessenger:
    name = "scripted"

    def __init__(self, result: SendResult) -> None:
        self._result = result
        self.calls = 0

    def send(self, req) -> SendResult:
        self.calls += 1
        return self._result

    def poll_receipts(self) -> list:
        return []


def test_AC_CAMP_019_accepted_send_records_all_fields(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    worker: Worker,
    make_lead,
) -> None:
    """Given an accepted send, when written back, then ids and timestamps are stored."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="accepted", phone="+15555550161")
    campaign_id = _campaign(client, template_id, [lead_id])

    worker.tick()

    item = client.get(f"/api/v1/campaigns/{campaign_id}/items").json()["items"][0]
    assert item["status"] == "SENT"
    assert item["attempts"] == 1
    assert item["provider_message_id"].startswith("mock-msg-")
    assert item["sent_at"] == "2026-11-14T09:00:00Z"
    assert item["next_attempt_at"] is None
    assert item["last_error_code"] is None
    with Session(db) as session:
        row = session.get(TaskItem, item["id"])
        assert row is not None
        assert row.rendered_body is not None
        assert row.locked_by is None and row.locked_at is None


def test_AC_CAMP_019_retryable_failure_stores_a_clean_message(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given a retryable failure with a phone in the message, then it is masked."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="dirty", phone="+15555550162")
    messenger = _ScriptedMessenger(
        SendResult(
            kind=ResultKind.RETRYABLE,
            code="SERVER_ERROR",
            message="upstream failed for +15555550162 please retry",
        )
    )
    campaign_id = _campaign(client, template_id, [lead_id])

    _worker_with(app, clock, messenger).tick()

    item = client.get(f"/api/v1/campaigns/{campaign_id}/items").json()["items"][0]
    assert (item["status"], item["attempts"]) == ("RETRY_WAIT", 1)
    assert item["last_error_code"] == "SERVER_ERROR"
    assert item["next_attempt_at"] == "2026-11-14T09:00:02Z"
    with Session(db) as session:
        row = session.get(TaskItem, item["id"])
        assert row is not None
        assert row.last_error_message is not None
        assert "15555550162" not in row.last_error_message
        assert "****" in row.last_error_message


def test_AC_CAMP_019_permanent_failure_records_the_reason(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given a permanent failure, when written back, then the reason is stored."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="permanent", phone="+15555550163")
    messenger = _ScriptedMessenger(
        SendResult(kind=ResultKind.PERMANENT, code="NOT_WHATSAPP_USER")
    )
    campaign_id = _campaign(client, template_id, [lead_id])

    _worker_with(app, clock, messenger).tick()

    item = client.get(f"/api/v1/campaigns/{campaign_id}/items").json()["items"][0]
    assert (item["status"], item["reason_code"]) == ("FAILED", "NOT_WHATSAPP_USER")
    assert item["last_error_code"] == "NOT_WHATSAPP_USER"
    assert item["attempts"] == 1

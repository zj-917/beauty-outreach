"""Retry scheduling uses the injected RNG and clock (AC-CAMP-016)."""

from __future__ import annotations

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


def _campaign(client: TestClient, template_id: int, lead_ids: list[int]) -> int:
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "retry schedule",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    assert response.status_code == 201, response.text
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    return campaign_id


def _item(client: TestClient, campaign_id: int) -> dict:
    return client.get(f"/api/v1/campaigns/{campaign_id}/items").json()["items"][0]


def _worker_with(app: FastAPI, clock: FakeClock, messenger, rng) -> Worker:
    processor = Processor(
        clock,
        app.state.phone_cipher,
        messenger,
        worker_id="schedule-worker",
        audit=app.state.audit_service,
        rng=rng,
    )
    return Worker(
        app.state.session_factory, clock, processor, worker_id="schedule-worker"
    )


class _ScriptedMessenger:
    name = "scripted"

    def __init__(self, results: list[SendResult]) -> None:
        self._results = list(results)
        self.calls = 0

    def send(self, req) -> SendResult:
        self.calls += 1
        if len(self._results) > 1:
            return self._results.pop(0)
        return self._results[0]

    def poll_receipts(self) -> list:
        return []


def test_AC_CAMP_016_injected_rng_drives_the_jitter(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given u=1, when a retry is scheduled, then the delay is base * 1.2."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="jitter", phone="+15555550151")
    messenger = _ScriptedMessenger(
        [SendResult(kind=ResultKind.RETRYABLE, code="SERVER_ERROR")]
    )
    campaign_id = _campaign(client, template_id, [lead_id])

    _worker_with(app, clock, messenger, lambda: 1.0).tick()

    item = _item(client, campaign_id)
    assert item["status"] == "RETRY_WAIT"
    assert item["next_attempt_at"] == "2026-11-14T09:00:02.400000Z"


def test_AC_CAMP_016_retry_waits_for_its_due_time(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given a scheduled retry, when the clock has not reached it, then it is not claimed."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="due_later", phone="+15555550152")
    messenger = _ScriptedMessenger(
        [
            SendResult(kind=ResultKind.RETRYABLE, code="SERVER_ERROR"),
            SendResult(kind=ResultKind.ACCEPTED, provider_message_id="msg-ok"),
        ]
    )
    campaign_id = _campaign(client, template_id, [lead_id])
    worker = _worker_with(app, clock, messenger, lambda: 0.0)

    worker.tick()
    assert messenger.calls == 1

    clock.advance(1)
    worker.tick()
    assert messenger.calls == 1

    clock.advance(1)
    worker.tick()
    assert messenger.calls == 2
    item = _item(client, campaign_id)
    assert (item["status"], item["attempts"]) == ("SENT", 2)

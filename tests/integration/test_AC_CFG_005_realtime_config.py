"""Runtime settings take effect on the next processed item (AC-CFG-005)."""

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


def _worker_with(app: FastAPI, clock: FakeClock, messenger) -> Worker:
    processor = Processor(
        clock,
        app.state.phone_cipher,
        messenger,
        worker_id="config-worker",
        audit=app.state.audit_service,
        rng=lambda: 0.0,
    )
    return Worker(
        app.state.session_factory, clock, processor, worker_id="config-worker"
    )


def test_AC_CFG_005_tightened_max_attempts_applies_immediately(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given max_attempts drops to 1, when the next retryable item runs, then it fails."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username="cfg_first", phone="+15555550191"),
        make_lead(username="cfg_second", phone="+15555550192"),
    ]
    messenger = _ScriptedMessenger(
        [
            SendResult(kind=ResultKind.ACCEPTED, provider_message_id="msg-1"),
            SendResult(kind=ResultKind.RETRYABLE, code="SERVER_ERROR"),
        ]
    )
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "live config",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    worker = _worker_with(app, clock, messenger)

    worker.tick()
    items = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]
    second = next(item for item in items if item["lead_id"] == lead_ids[1])
    assert (second["status"], second["attempts"]) == ("RETRY_WAIT", 1)

    assert (
        client.put(
            "/api/v1/settings", json={"sending.max_attempts": 1}
        ).status_code
        == 200
    )
    clock.advance(2)
    worker.tick()

    items = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]
    second = next(item for item in items if item["lead_id"] == lead_ids[1])
    assert (second["status"], second["reason_code"]) == (
        "FAILED",
        "MAX_ATTEMPTS_EXCEEDED",
    )
    assert second["attempts"] == 2


def test_AC_CFG_005_tightened_global_rate_defers_the_next_item(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given a tighter global rule, when the next item runs, then it is deferred."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username="cfg_rate_one", phone="+15555550193"),
        make_lead(username="cfg_rate_two", phone="+15555550194"),
    ]
    messenger = _ScriptedMessenger(
        [SendResult(kind=ResultKind.ACCEPTED, provider_message_id="msg-rate")]
    )
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "tighten rate",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    worker = _worker_with(app, clock, messenger)

    rates = client.get("/api/v1/rate-rules").json()
    global_rule = next(rule for rule in rates if rule["scope"] == "GLOBAL")
    assert (
        client.patch(
            f"/api/v1/rate-rules/{global_rule['id']}",
            json={"max_count": 1, "window_seconds": 600},
        ).status_code
        == 200
    )

    worker.tick()

    items = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]
    statuses = {item["lead_id"]: item["status"] for item in items}
    assert statuses[lead_ids[0]] == "SENT"
    second = next(item for item in items if item["lead_id"] == lead_ids[1])
    assert second["status"] == "PENDING"
    assert second["next_attempt_at"] == "2026-11-14T09:10:00Z"
    assert messenger.calls == 1

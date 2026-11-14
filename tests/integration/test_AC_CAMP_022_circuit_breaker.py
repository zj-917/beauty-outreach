"""Circuit breaker behaviour (AC-CAMP-022)."""

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
        worker_id="circuit-worker",
        audit=app.state.audit_service,
        rng=lambda: 0.0,
    )
    return Worker(
        app.state.session_factory, clock, processor, worker_id="circuit-worker"
    )


def _campaign(
    client: TestClient, template_id: int, lead_ids: list[int], name: str = "circuit"
) -> int:
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": name,
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    assert response.status_code == 201, response.text
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    return campaign_id


def _items(client: TestClient, campaign_id: int) -> dict[int, dict]:
    body = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()
    return {item["lead_id"]: item for item in body["items"]}


def _leads(make_lead, base: int, count: int) -> list[int]:
    return [
        make_lead(username=f"circuit_{base}_{index}", phone=f"+1555555{base + index}")
        for index in range(count)
    ]


def test_AC_CAMP_022_five_consecutive_failures_pause_the_task(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given five counted failures in a row, when ticking, then the task pauses once."""
    template_id = _seed(client, db, clock)
    lead_ids = _leads(make_lead, 700, 5)
    codes = ["SERVER_ERROR", "TIMEOUT", "NETWORK_ERROR", "SERVER_ERROR", "TIMEOUT"]
    messenger = _ScriptedMessenger(
        [SendResult(kind=ResultKind.RETRYABLE, code=code) for code in codes]
    )
    campaign_id = _campaign(client, template_id, lead_ids)

    _worker_with(app, clock, messenger).tick()

    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert (detail["status"], detail["pause_reason"]) == ("PAUSED", "CIRCUIT_OPEN")
    assert detail["consecutive_failures"] == 5
    assert {item["status"] for item in _items(client, campaign_id).values()} == {
        "RETRY_WAIT"
    }
    audit = client.get(
        "/api/v1/audit-logs",
        params={"action": "CAMPAIGN_CIRCUIT_OPENED", "entity_id": str(campaign_id)},
    ).json()
    assert audit["total"] == 1


def test_AC_CAMP_022_accepted_send_resets_the_counter(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given two failures then an accepted send, when two more fail, then the count is 2."""
    template_id = _seed(client, db, clock)
    lead_ids = _leads(make_lead, 710, 5)
    messenger = _ScriptedMessenger(
        [
            SendResult(kind=ResultKind.RETRYABLE, code="SERVER_ERROR"),
            SendResult(kind=ResultKind.RETRYABLE, code="TIMEOUT"),
            SendResult(kind=ResultKind.ACCEPTED, provider_message_id="msg-ok"),
            SendResult(kind=ResultKind.RETRYABLE, code="SERVER_ERROR"),
            SendResult(kind=ResultKind.RETRYABLE, code="NETWORK_ERROR"),
        ]
    )
    campaign_id = _campaign(client, template_id, lead_ids)

    _worker_with(app, clock, messenger).tick()

    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["status"] == "RUNNING"
    assert detail["consecutive_failures"] == 2
    items = _items(client, campaign_id)
    assert items[lead_ids[2]]["status"] == "SENT"


def test_AC_CAMP_022_rate_limited_failures_are_not_counted(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given five rate-limited failures, when ticking, then the counter stays zero."""
    template_id = _seed(client, db, clock)
    lead_ids = _leads(make_lead, 720, 5)
    messenger = _ScriptedMessenger(
        [
            SendResult(
                kind=ResultKind.RETRYABLE,
                code="RATE_LIMITED",
                retry_after_seconds=1.0,
            )
        ]
    )
    campaign_id = _campaign(client, template_id, lead_ids)

    _worker_with(app, clock, messenger).tick()

    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["status"] == "RUNNING"
    assert detail["consecutive_failures"] == 0


def test_AC_CAMP_022_auth_error_pauses_immediately(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given AUTH_ERROR on the first attempt, when ticking, then the task pauses at once."""
    template_id = _seed(client, db, clock)
    lead_ids = _leads(make_lead, 730, 1)
    messenger = _ScriptedMessenger(
        [SendResult(kind=ResultKind.PERMANENT, code="AUTH_ERROR")]
    )
    campaign_id = _campaign(client, template_id, lead_ids)

    _worker_with(app, clock, messenger).tick()

    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert (detail["status"], detail["pause_reason"]) == ("PAUSED", "CIRCUIT_OPEN")
    assert detail["consecutive_failures"] == 0


def test_AC_CAMP_022_resume_after_circuit_continues_sending(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given a circuit-opened task, when resumed, then retries continue to completion."""
    template_id = _seed(client, db, clock)
    lead_ids = _leads(make_lead, 740, 5)
    messenger = _ScriptedMessenger(
        [SendResult(kind=ResultKind.RETRYABLE, code="SERVER_ERROR")] * 5
        + [SendResult(kind=ResultKind.ACCEPTED, provider_message_id="msg-recovered")]
    )
    campaign_id = _campaign(client, template_id, lead_ids)
    worker = _worker_with(app, clock, messenger)

    worker.tick()
    assert client.get(f"/api/v1/campaigns/{campaign_id}").json()["status"] == "PAUSED"

    clock.advance(11)
    assert client.post(f"/api/v1/campaigns/{campaign_id}/resume").status_code == 200
    worker.tick()

    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["status"] == "COMPLETED"
    assert detail["consecutive_failures"] == 0
    items = _items(client, campaign_id)
    assert {item["status"] for item in items.values()} == {"SENT"}
    assert {item["attempts"] for item in items.values()} == {2}

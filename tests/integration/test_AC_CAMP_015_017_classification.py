"""Provider result classification and attempt limits (CAMP-015, CAMP-017)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.models import TaskItem
from app.providers.messenger.base import ResultKind, SendResult
from app.providers.messenger.mock import MockMessenger
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
            "name": "classification",
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


def _detail(client: TestClient, campaign_id: int) -> dict:
    return client.get(f"/api/v1/campaigns/{campaign_id}").json()


class _ScriptedMessenger:
    """Return scripted results in order; the last one repeats."""

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


def _worker_with(
    app: FastAPI, clock: FakeClock, messenger, *, rng=None
) -> Worker:
    processor = Processor(
        clock,
        app.state.phone_cipher,
        messenger,
        worker_id="scripted-worker",
        audit=app.state.audit_service,
        rng=rng or (lambda: 0.0),
    )
    return Worker(
        app.state.session_factory, clock, processor, worker_id="scripted-worker"
    )


def test_AC_CAMP_015_retryable_results_wait_for_retry(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given each retryable code, when ticking, then the item waits with that code."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username=f"retry_{code.lower()}", phone=f"+15555550{600 + index}")
        for index, code in enumerate(
            ["TIMEOUT", "NETWORK_ERROR", "SERVER_ERROR"]
        )
    ]
    messenger = _ScriptedMessenger(
        [
            SendResult(kind=ResultKind.RETRYABLE, code="TIMEOUT", message="timed out"),
            SendResult(
                kind=ResultKind.RETRYABLE, code="NETWORK_ERROR", message="network"
            ),
            SendResult(
                kind=ResultKind.RETRYABLE, code="SERVER_ERROR", message="server"
            ),
        ]
    )
    campaign_id = _campaign(client, template_id, lead_ids)

    _worker_with(app, clock, messenger).tick()

    items = _items(client, campaign_id)
    assert {item["status"] for item in items.values()} == {"RETRY_WAIT"}
    assert {item["attempts"] for item in items.values()} == {1}
    with Session(db) as session:
        rows = session.scalars(
            select(TaskItem).where(TaskItem.task_id == campaign_id)
        ).all()
        codes = {row.lead_id: row.last_error_code for row in rows}
    assert set(codes.values()) == {"TIMEOUT", "NETWORK_ERROR", "SERVER_ERROR"}


def test_AC_CAMP_015_rate_limited_waits_for_retry_after(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given a 429 with retry_after, when ticking, then the wait is at least that long."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="limited", phone="+15555550131")
    messenger = _ScriptedMessenger(
        [
            SendResult(
                kind=ResultKind.RETRYABLE,
                code="RATE_LIMITED",
                message="slow down",
                retry_after_seconds=30.0,
            )
        ]
    )
    campaign_id = _campaign(client, template_id, [lead_id])

    _worker_with(app, clock, messenger).tick()

    item = _items(client, campaign_id)[lead_id]
    assert (item["status"], item["last_error_code"]) == ("RETRY_WAIT", "RATE_LIMITED")
    assert item["next_attempt_at"] == "2026-11-14T09:00:30Z"


def test_AC_CAMP_015_permanent_results_fail_on_first_attempt(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given each permanent code, when ticking, then the item fails immediately."""
    template_id = _seed(client, db, clock)
    codes = ["INVALID_NUMBER", "NOT_WHATSAPP_USER", "TEMPLATE_REJECTED"]
    lead_ids = [
        make_lead(username=f"perm_{code.lower()}", phone=f"+15555550{610 + index}")
        for index, code in enumerate(codes)
    ]
    messenger = _ScriptedMessenger(
        [SendResult(kind=ResultKind.PERMANENT, code=code) for code in codes]
    )
    campaign_id = _campaign(client, template_id, lead_ids)

    _worker_with(app, clock, messenger).tick()

    items = _items(client, campaign_id)
    assert {item["status"] for item in items.values()} == {"FAILED"}
    assert {item["reason_code"] for item in items.values()} == set(codes)
    assert {item["attempts"] for item in items.values()} == {1}


def test_AC_CAMP_015_auth_error_trips_the_circuit(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    make_lead,
) -> None:
    """Given AUTH_ERROR, when ticking, then the task fails and pauses with CIRCUIT_OPEN."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="auth", phone="+15555550140")
    messenger = _ScriptedMessenger(
        [SendResult(kind=ResultKind.PERMANENT, code="AUTH_ERROR", message="denied")]
    )
    campaign_id = _campaign(client, template_id, [lead_id])

    _worker_with(app, clock, messenger).tick()

    item = _items(client, campaign_id)[lead_id]
    assert (item["status"], item["reason_code"]) == ("FAILED", "AUTH_ERROR")
    detail = _detail(client, campaign_id)
    assert (detail["status"], detail["pause_reason"]) == ("PAUSED", "CIRCUIT_OPEN")
    audit = client.get(
        "/api/v1/audit-logs",
        params={"action": "CAMPAIGN_CIRCUIT_OPENED", "entity_id": str(campaign_id)},
    ).json()
    assert audit["total"] == 1


def test_AC_CAMP_017_third_retryable_failure_exhausts_attempts(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given max_attempts=3, when the third call still fails, then the item fails."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="exhausted", phone="+15555559002")
    campaign_id = _campaign(client, template_id, [lead_id])
    worker = _worker_with(app, clock, messenger)

    worker.tick()
    clock.advance(2)
    worker.tick()
    clock.advance(4)
    worker.tick()

    item = _items(client, campaign_id)[lead_id]
    assert (item["status"], item["reason_code"]) == (
        "FAILED",
        "MAX_ATTEMPTS_EXCEEDED",
    )
    assert item["attempts"] == 3
    with Session(db) as session:
        row = session.get(TaskItem, item["id"])
        assert row is not None
        assert row.last_error_code == "SERVER_ERROR"

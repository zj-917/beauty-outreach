"""Cancel semantics for in-flight sends (AC-CAMP-008)."""

from __future__ import annotations

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


class _CancellingMessenger:
    """Cancel the campaign mid-call and then report a retryable failure."""

    name = "cancelling"

    def __init__(self, client: TestClient, campaign_id: int) -> None:
        self._client = client
        self._campaign_id = campaign_id
        self.calls = 0
        self.cancel_status: int | None = None

    def send(self, req) -> SendResult:
        self.calls += 1
        self.cancel_status = self._client.post(
            f"/api/v1/campaigns/{self._campaign_id}/cancel"
        ).status_code
        return SendResult(
            kind=ResultKind.RETRYABLE, code="SERVER_ERROR", message="mock failure"
        )

    def poll_receipts(self) -> list:
        return []


def test_AC_CAMP_008_in_flight_retryable_failure_skips_instead(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app,
    make_lead,
) -> None:
    """Given cancel lands during the call, when a retryable failure returns, then skip."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="cancelled", phone="+15555550111")
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "cancel mid flight",
            "template_id": template_id,
            "selection": {"lead_ids": [lead_id]},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    messenger = _CancellingMessenger(client, campaign_id)
    processor = Processor(
        clock,
        app.state.phone_cipher,
        messenger,
        worker_id="cancel-worker",
        audit=app.state.audit_service,
    )
    worker = Worker(
        app.state.session_factory, clock, processor, worker_id="cancel-worker"
    )

    worker.tick()

    assert messenger.cancel_status == 200
    item = client.get(f"/api/v1/campaigns/{campaign_id}/items").json()["items"][0]
    assert (item["status"], item["reason_code"]) == ("SKIPPED", "TASK_CANCELLED")
    assert item["attempts"] == 1
    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["status"] == "CANCELLED"

    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 409
    assert client.post(f"/api/v1/campaigns/{campaign_id}/resume").status_code == 409

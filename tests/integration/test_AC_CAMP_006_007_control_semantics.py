"""Pause and resume semantics inside the send engine (CAMP-006, CAMP-007)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.models import CampaignTask, SendLog, TaskItem
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
            "name": "control semantics",
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


class _PausingMessenger(MockMessenger):
    """Pause the campaign right before the provider accepts the message."""

    def __init__(self, clock: FakeClock, client: TestClient, campaign_id: int) -> None:
        super().__init__(clock)
        self._client = client
        self._campaign_id = campaign_id
        self.pause_status: int | None = None

    def send(self, req):
        self.pause_status = self._client.post(
            f"/api/v1/campaigns/{self._campaign_id}/pause"
        ).status_code
        return super().send(req)


def _worker_with(app, clock: FakeClock, messenger) -> Worker:
    processor = Processor(
        clock,
        app.state.phone_cipher,
        messenger,
        worker_id="control-worker",
        audit=app.state.audit_service,
    )
    return Worker(
        app.state.session_factory, clock, processor, worker_id="control-worker"
    )


def test_AC_CAMP_006_pause_stops_claims_and_releases_leased_items(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app,
    worker: Worker,
    processor: Processor,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given leased items, when the task pauses, then no new claims happen and leases release."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username=f"pause_{index}", phone=f"+15555550{500 + index}")
        for index in range(3)
    ]
    campaign_id = _campaign(client, template_id, lead_ids)
    claimed = worker.claim(campaign_id)
    assert len(claimed) == 3

    assert client.post(f"/api/v1/campaigns/{campaign_id}/pause").status_code == 200
    assert worker.claim(campaign_id) == []

    with Session(db) as session:
        assert processor.process(session, claimed[0]) == "RELEASED"
        row = session.get(TaskItem, claimed[0])
        assert row is not None
        assert (row.status, row.attempts, row.locked_at) == ("PENDING", 0, None)

    assert messenger.calls == 0
    with Session(db) as session:
        logs = session.scalar(
            select(SendLog).where(SendLog.task_id == campaign_id)
        )
    assert logs is None


def test_AC_CAMP_006_in_flight_send_completes_after_pause(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app,
    make_lead,
) -> None:
    """Given a pause arrives during the provider call, when it returns, then it writes back."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="in_flight", phone="+15555550101")
    campaign_id = _campaign(client, template_id, [lead_id])
    messenger = _PausingMessenger(clock, client, campaign_id)
    worker = _worker_with(app, clock, messenger)

    worker.tick()

    assert messenger.pause_status == 200
    assert messenger.calls == 1
    item = _items(client, campaign_id)[lead_id]
    assert item["status"] == "SENT"
    assert item["attempts"] == 1
    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["status"] == "PAUSED"
    assert detail["pause_reason"] == "MANUAL"


def test_AC_CAMP_007_resume_continues_only_remaining_items(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given a paused task, when resumed, then remaining items send and terminal ones stay."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username=f"resume_{index}", phone=f"+15555550{510 + index}")
        for index in range(3)
    ]
    campaign_id = _campaign(client, template_id, lead_ids)
    assert client.post(f"/api/v1/campaigns/{campaign_id}/pause").status_code == 200
    with Session(db) as session:
        row = session.get(CampaignTask, campaign_id)
        assert row is not None
        row.consecutive_failures = 2
        session.commit()

    worker.tick()
    assert messenger.calls == 0

    assert client.post(f"/api/v1/campaigns/{campaign_id}/resume").status_code == 200
    worker.tick()

    items = _items(client, campaign_id)
    assert {item["status"] for item in items.values()} == {"SENT"}
    assert {item["attempts"] for item in items.values()} == {1}
    assert messenger.calls == 3

    worker.tick()
    assert messenger.calls == 3
    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["consecutive_failures"] == 0
    assert detail["pause_reason"] is None

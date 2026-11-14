"""Gate chain behaviour inside the send engine (CAMP-011, COMP-004/007, TPL-005/006)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.worker import Worker
from app.models import SendLog
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
            "name": "gate chain",
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


def _gate_logs(db: Engine, campaign_id: int) -> list[SendLog]:
    with Session(db) as session:
        return list(
            session.scalars(
                select(SendLog).where(
                    SendLog.task_id == campaign_id, SendLog.phase == "GATE"
                )
            ).all()
        )


def test_AC_CAMP_011_gates_two_to_four_skip_without_messenger_calls(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given fatal compliance facts, when ticking, then items skip and Messenger is untouched."""
    template_id = _seed(client, db, clock)
    blacklisted = make_lead(username="blacklisted", phone="+15555550121")
    unsubscribed = make_lead(username="unsubscribed", phone="+15555550122")
    no_phone = make_lead(username="no_phone")
    no_consent = make_lead(username="no_consent", phone="+15555550124", consent=None)
    revoked = make_lead(
        username="revoked", phone="+15555550125", consent="REVOKED"
    )
    assert (
        client.post(
            "/api/v1/suppressions",
            json={"type": "BLACKLIST", "phone": "+15555550121", "reason": "spam"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/suppressions",
            json={
                "type": "UNSUBSCRIBE",
                "username": "unsubscribed",
                "reason": "stop",
            },
        ).status_code
        == 201
    )
    campaign_id = _campaign(
        client,
        template_id,
        [blacklisted, unsubscribed, no_phone, no_consent, revoked],
    )

    worker.tick()

    items = _items(client, campaign_id)
    assert items[blacklisted]["status"] == "SKIPPED"
    assert items[blacklisted]["reason_code"] == "BLACKLISTED"
    assert items[unsubscribed]["reason_code"] == "UNSUBSCRIBED"
    assert items[no_phone]["reason_code"] == "NO_PHONE"
    assert items[no_consent]["reason_code"] == "NO_CONSENT"
    assert items[revoked]["reason_code"] == "CONSENT_REVOKED"
    assert messenger.calls == 0

    logs = _gate_logs(db, campaign_id)
    assert len(logs) == 5
    assert {log.outcome for log in logs} == {"BLOCKED"}
    assert {log.reason_code for log in logs} == {
        "BLACKLISTED",
        "UNSUBSCRIBED",
        "NO_PHONE",
        "NO_CONSENT",
        "CONSENT_REVOKED",
    }


def test_AC_COMP_004_suppressed_recipients_are_skipped_without_send(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given a blacklisted phone, when the task runs, then no provider call happens."""
    template_id = _seed(client, db, clock)
    lead_id = make_lead(username="blocked", phone="+15555550131")
    client.post(
        "/api/v1/suppressions",
        json={"type": "BLACKLIST", "phone": "+15555550131", "reason": "legal"},
    )
    campaign_id = _campaign(client, template_id, [lead_id])

    worker.tick()

    item = _items(client, campaign_id)[lead_id]
    assert (item["status"], item["reason_code"]) == ("SKIPPED", "BLACKLISTED")
    assert messenger.calls == 0


def test_AC_COMP_007_stop_applies_without_restarting_the_task(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given a running task, when one recipient stops, then only that item is skipped."""
    template_id = _seed(client, db, clock)
    stayer = make_lead(username="stayer", phone="+15555550141")
    stopper = make_lead(username="stopper", phone="+15555550142")
    campaign_id = _campaign(client, template_id, [stayer, stopper])

    response = client.post(
        "/api/v1/suppressions",
        json={"type": "UNSUBSCRIBE", "phone": "+15555550142", "reason": "STOP"},
    )
    assert response.status_code == 201
    worker.tick()

    items = _items(client, campaign_id)
    assert items[stayer]["status"] == "SENT"
    assert (items[stopper]["status"], items[stopper]["reason_code"]) == (
        "SKIPPED",
        "UNSUBSCRIBED",
    )
    assert messenger.calls == 1


def test_AC_TPL_005_disabled_template_skips_remaining_items(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given the template is disabled while running, when ticking, then items skip."""
    template_id = _seed(client, db, clock)
    lead_one = make_lead(username="tpl_one", phone="+15555550151")
    lead_two = make_lead(username="tpl_two", phone="+15555550152")
    campaign_id = _campaign(client, template_id, [lead_one, lead_two])
    assert client.post(f"/api/v1/templates/{template_id}/disable").status_code == 200

    worker.tick()

    items = _items(client, campaign_id)
    assert {item["status"] for item in items.values()} == {"SKIPPED"}
    assert {item["reason_code"] for item in items.values()} == {
        "TEMPLATE_NOT_APPROVED"
    }
    assert messenger.calls == 0


def test_AC_TPL_006_missing_variable_skips_without_messenger_calls(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given a variable with no value or default, when ticking, then the item skips."""
    _seed(client, db, clock)
    lead_id = make_lead(
        username="no_keyword", phone="+15555550161", top_keyword=None
    )
    template = client.post(
        "/api/v1/templates",
        json={"name": "keyword-only", "body": "Hi {{keyword}}", "language": "en"},
    ).json()
    client.post(f"/api/v1/templates/{template['id']}/approve")
    campaign_id = _campaign(client, template["id"], [lead_id])

    worker.tick()

    item = _items(client, campaign_id)[lead_id]
    assert (item["status"], item["reason_code"]) == (
        "SKIPPED",
        "TEMPLATE_VARIABLE_MISSING",
    )
    assert messenger.calls == 0

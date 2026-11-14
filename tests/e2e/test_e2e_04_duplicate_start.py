"""E2E-4: repeated start never sends a second message to any recipient."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.providers.messenger.mock import MockMessenger


def test_e2e_04_duplicate_start_keeps_one_message_per_recipient(
    client: TestClient,
    template_id: int,
    messenger: MockMessenger,
    make_worker: Callable[..., object],
    make_lead,
) -> None:
    """Covers: AC-CAMP-003, AC-CAMP-005.

    Given a task, when start is called again while RUNNING and after completion,
    then every recipient still has exactly one message.
    """
    lead_ids = [
        make_lead(username=f"e2e_idem_{index}", phone=f"+15555550{410 + index}")
        for index in range(3)
    ]
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "e2e idempotent",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    ).json()
    campaign_id = campaign["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200

    worker = make_worker(messenger)
    worker.tick()
    worker.tick()
    assert messenger.unique_messages == 3
    assert messenger.calls == 3

    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 409
    worker.tick()
    assert messenger.unique_messages == 3
    assert messenger.calls == 3

    items = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]
    assert {item["status"] for item in items} == {"SENT"}
    assert len({item["provider_message_id"] for item in items}) == 3

    audit = client.get(
        "/api/v1/audit-logs",
        params={"action": "CAMPAIGN_STARTED", "entity_id": str(campaign_id)},
    ).json()
    assert audit["total"] == 1

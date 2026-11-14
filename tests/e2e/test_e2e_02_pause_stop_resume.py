"""E2E-2: pause the task, receive an inbound STOP, resume and skip the target."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.providers.messenger.mock import MockMessenger


def test_e2e_02_pause_stop_resume_skips_without_calling_provider(
    client: TestClient,
    template_id: int,
    messenger: MockMessenger,
    make_worker: Callable[..., object],
    make_lead,
) -> None:
    """Covers: AC-COMP-006, AC-CAMP-007, AC-CAMP-011.

    Given a running task paused mid-flight, when the target sends STOP and the
    task resumes, then the item is SKIPPED(UNSUBSCRIBED) with no provider call.
    """
    phone = "+15555550177"
    lead_id = make_lead(username="e2e_stopper", phone=phone)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "e2e stop",
            "template_id": template_id,
            "selection": {"lead_ids": [lead_id]},
        },
    ).json()
    campaign_id = campaign["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    assert client.post(f"/api/v1/campaigns/{campaign_id}/pause").status_code == 200

    stop = client.post("/demo/inbound-stop", json={"phone": phone})
    assert stop.status_code == 200
    assert stop.json() == {"action": "UNSUBSCRIBED"}
    assert client.post(f"/api/v1/campaigns/{campaign_id}/resume").status_code == 200

    worker = make_worker(messenger)
    worker.tick()

    item = client.get(f"/api/v1/campaigns/{campaign_id}/items").json()["items"][0]
    assert (item["status"], item["reason_code"]) == ("SKIPPED", "UNSUBSCRIBED")
    assert messenger.calls == 0
    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["status"] == "COMPLETED"
    assert detail["counts"]["skipped"] == 1

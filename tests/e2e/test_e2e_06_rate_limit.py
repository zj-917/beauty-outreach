"""E2E-6: the global window defers items, which send once the window slides."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.providers.messenger.mock import MockMessenger


def test_e2e_06_global_rate_defers_then_the_window_slides(
    client: TestClient,
    clock: FakeClock,
    template_id: int,
    messenger: MockMessenger,
    make_worker: Callable[..., object],
    make_lead,
) -> None:
    """Covers: AC-CAMP-012, AC-COMP-004.

    Given seven targets and the seeded 5/10s global rule, when one tick runs,
    then five send and two defer without consuming an attempt; after the window
    slides the deferred items send.
    """
    lead_ids = [
        make_lead(username=f"e2e_rate_{index}", phone=f"+15555550{210 + index}")
        for index in range(7)
    ]
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "e2e rate",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    ).json()
    campaign_id = campaign["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200

    worker = make_worker(messenger)
    worker.tick()

    items = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]
    sent = [item for item in items if item["status"] == "SENT"]
    deferred = [item for item in items if item["status"] == "PENDING"]
    assert (len(sent), len(deferred)) == (5, 2)
    assert messenger.calls == 5
    for item in deferred:
        assert item["attempts"] == 0
        assert item["next_attempt_at"] == "2026-11-14T09:00:10Z"

    logs = client.get(
        "/api/v1/send-logs",
        params={"task_id": campaign_id, "phase": "GATE", "outcome": "DEFERRED"},
    ).json()
    assert logs["total"] == 2
    assert {entry["reason_code"] for entry in logs["items"]} == {"RATE_LIMIT_GLOBAL"}

    clock.advance(11)
    worker.tick()

    items = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()["items"]
    assert {item["status"] for item in items} == {"SENT"}
    assert messenger.calls == 7
    assert messenger.unique_messages == 7

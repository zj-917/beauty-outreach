"""E2E-9: a tightened global rate rule applies to the very next item."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.providers.messenger.mock import MockMessenger


def _campaign(client: TestClient, template_id: int, lead_ids: list[int]) -> int:
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "e2e live config",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    assert response.status_code == 201, response.text
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    return campaign_id


def test_e2e_09_tightened_global_rate_defers_the_next_campaign(
    client: TestClient,
    clock: FakeClock,
    template_id: int,
    messenger: MockMessenger,
    make_worker: Callable[..., object],
    make_lead,
) -> None:
    """Covers: AC-CFG-005, AC-CAMP-012.

    Given three sends inside the window, when the global rule is tightened while
    running, then the next campaign's item is deferred by the new window.
    """
    first_ids = [
        make_lead(username=f"e2e_live_{index}", phone=f"+15555550{220 + index}")
        for index in range(3)
    ]
    first_campaign = _campaign(client, template_id, first_ids)
    worker = make_worker(messenger)
    worker.tick()
    assert messenger.calls == 3
    assert client.get(f"/api/v1/campaigns/{first_campaign}").json()["status"] == "COMPLETED"

    rates = client.get("/api/v1/rate-rules").json()
    global_rule = next(rule for rule in rates if rule["scope"] == "GLOBAL")
    assert (
        client.patch(
            f"/api/v1/rate-rules/{global_rule['id']}",
            json={"max_count": 3, "window_seconds": 600},
        ).status_code
        == 200
    )

    second_id = make_lead(username="e2e_live_next", phone="+15555550223")
    second_campaign = _campaign(client, template_id, [second_id])
    worker.tick()

    items = client.get(
        f"/api/v1/campaigns/{second_campaign}/items", params={"page_size": 100}
    ).json()["items"]
    assert items[0]["status"] == "PENDING"
    assert items[0]["attempts"] == 0
    assert items[0]["next_attempt_at"] == "2026-11-14T09:10:00Z"
    assert messenger.calls == 3

    clock.advance(601)
    worker.tick()
    items = client.get(
        f"/api/v1/campaigns/{second_campaign}/items", params={"page_size": 100}
    ).json()["items"]
    assert items[0]["status"] == "SENT"
    assert messenger.calls == 4

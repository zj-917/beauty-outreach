"""E2E-7: the full retry chain across the 9001–9004 mock behaviours."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.providers.messenger.mock import MockMessenger


def _items(client: TestClient, campaign_id: int) -> dict[int, dict]:
    body = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()
    return {item["lead_id"]: item for item in body["items"]}


def test_e2e_07_retry_chain_covers_timeout_exhaustion_and_429(
    client: TestClient,
    clock: FakeClock,
    template_id: int,
    messenger: MockMessenger,
    make_worker: Callable[..., object],
    make_lead,
) -> None:
    """Covers: AC-CAMP-015, AC-CAMP-016, AC-CAMP-017, AC-CAMP-018.

    Given one target per mock behaviour, when retries run with zero jitter,
    then attempts, delays, reason codes and send_log rows match the plan.
    """
    leads = {
        "timeout": make_lead(username="e2e_9001", phone="+15555559001"),
        "exhausted": make_lead(username="e2e_9002", phone="+15555559002"),
        "invalid": make_lead(username="e2e_9003", phone="+15555559003"),
        "rate_limited": make_lead(username="e2e_9004", phone="+15555559004"),
    }
    # Keep the seeded global window out of the way so delays come from backoff only.
    rates = client.get("/api/v1/rate-rules").json()
    global_rule = next(rule for rule in rates if rule["scope"] == "GLOBAL")
    assert (
        client.patch(
            f"/api/v1/rate-rules/{global_rule['id']}",
            json={"max_count": 100, "window_seconds": 10},
        ).status_code
        == 200
    )
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "e2e retries",
            "template_id": template_id,
            "selection": {"lead_ids": list(leads.values())},
        },
    ).json()
    campaign_id = campaign["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    worker = make_worker(messenger)

    worker.tick()
    items = _items(client, campaign_id)
    assert (items[leads["invalid"]]["status"], items[leads["invalid"]]["reason_code"]) == (
        "FAILED",
        "INVALID_NUMBER",
    )
    assert items[leads["invalid"]]["attempts"] == 1
    assert items[leads["timeout"]]["next_attempt_at"] == "2026-11-14T09:00:02Z"
    assert items[leads["exhausted"]]["next_attempt_at"] == "2026-11-14T09:00:02Z"
    assert items[leads["rate_limited"]]["next_attempt_at"] == "2026-11-14T09:00:03Z"

    clock.advance(3)
    worker.tick()
    items = _items(client, campaign_id)
    assert (items[leads["timeout"]]["status"], items[leads["timeout"]]["attempts"]) == (
        "RETRY_WAIT",
        2,
    )
    assert items[leads["timeout"]]["next_attempt_at"] == "2026-11-14T09:00:07Z"
    assert (items[leads["rate_limited"]]["status"], items[leads["rate_limited"]]["attempts"]) == (
        "SENT",
        2,
    )

    clock.advance(4)
    worker.tick()
    items = _items(client, campaign_id)
    assert (items[leads["timeout"]]["status"], items[leads["timeout"]]["attempts"]) == (
        "SENT",
        3,
    )
    assert (
        items[leads["exhausted"]]["status"],
        items[leads["exhausted"]]["reason_code"],
    ) == ("FAILED", "MAX_ATTEMPTS_EXCEEDED")
    assert items[leads["exhausted"]]["attempts"] == 3
    assert items[leads["exhausted"]]["last_error_code"] == "SERVER_ERROR"

    logs = client.get(
        "/api/v1/send-logs",
        params={"task_id": campaign_id, "phase": "PROVIDER", "page_size": 100},
    ).json()
    assert logs["total"] == 9

    stats = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()
    assert (stats["success"], stats["failed"]) == (2, 2)
    assert stats["failure_reasons"] == {
        "MAX_ATTEMPTS_EXCEEDED": 1,
        "INVALID_NUMBER": 1,
    }
    assert client.get(f"/api/v1/campaigns/{campaign_id}").json()["status"] == "COMPLETED"

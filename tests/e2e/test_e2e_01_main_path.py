"""E2E-1: import → screen → campaign → completed, matching 05-mock-data §3."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.providers.messenger.mock import MockMessenger

EXPECTED_SKIP_REASONS = {
    "NO_PHONE": 7,
    "NO_CONSENT": 1,
    "CONSENT_REVOKED": 1,
    "BLACKLISTED": 2,
    "UNSUBSCRIBED": 1,
}
EXPECTED_FAILURE_REASONS = {
    "MAX_ATTEMPTS_EXCEEDED": 1,
    "INVALID_NUMBER": 1,
    "DELIVERY_FAILED": 1,
}


def test_e2e_01_main_path_imports_screens_and_completes(
    client: TestClient,
    clock: FakeClock,
    template_id: int,
    messenger: MockMessenger,
    make_worker: Callable[..., object],
    run_until_complete: Callable[..., str],
) -> None:
    """Covers: AC-LEAD-001, AC-SCR-010, AC-CAMP-001, AC-CAMP-023, AC-STAT-001.

    Given the mock dataset, when the whole flow runs without a STOP step, then
    every 05-mock-data §3 number holds (success=5, failed=3, skipped=12).
    """
    batch = client.post("/api/v1/lead-batches/import", json={"source": "mock"}).json()
    assert (
        batch["total_rows"],
        batch["imported"],
        batch["duplicates"],
        batch["invalid"],
        batch["warnings"],
    ) == (52, 44, 4, 4, 1)

    screening = client.post("/api/v1/leads/screen", json={}).json()
    assert (
        screening["processed"],
        screening["approved"],
        screening["pending_review"],
        screening["discarded"],
    ) == (44, 20, 8, 16)
    pool = client.get("/api/v1/pool", params={"page_size": 100}).json()
    assert pool["total"] == 20

    campaign = client.post(
        "/api/v1/campaigns",
        json={"name": "e2e main path", "template_id": template_id, "selection": {}},
    ).json()
    campaign_id = campaign["id"]
    assert campaign["total_items"] == 20
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200

    worker = make_worker(messenger, receipts=True)
    assert run_until_complete(worker, campaign_id) == "COMPLETED"
    clock.advance(10)
    worker.tick()  # apply the queued mock receipts (9005 fails delivery)

    stats = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()
    assert (stats["total"], stats["success"], stats["failed"], stats["skipped"]) == (
        20,
        5,
        3,
        12,
    )
    assert stats["skip_reasons"] == EXPECTED_SKIP_REASONS
    assert stats["failure_reasons"] == EXPECTED_FAILURE_REASONS
    assert stats["success_rate"] == round(5 / 8, 4)
    # 9005 is accepted by the provider but its receipt later reports a failed delivery.
    assert messenger.unique_messages == 6

    detail = client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail["status"] == "COMPLETED"
    assert detail["counts"]["total"] == 20
    assert detail["counts"]["success"] == 5

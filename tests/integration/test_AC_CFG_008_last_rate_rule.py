"""Last enabled rate rule protection tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_pair(client: TestClient) -> tuple[int, int]:
    global_rule = client.post(
        "/api/v1/rate-rules",
        json={"name": "g", "scope": "GLOBAL", "window_seconds": 10, "max_count": 5},
    ).json()
    recipient = client.post(
        "/api/v1/rate-rules",
        json={
            "name": "p",
            "scope": "PER_RECIPIENT",
            "window_seconds": 86400,
            "max_count": 1,
        },
    ).json()
    return global_rule["id"], recipient["id"]


def test_AC_CFG_008_last_global_cannot_be_removed_or_moved(
    client: TestClient,
) -> None:
    """Given the only GLOBAL rule, when deleted/disabled/moved, then each is rejected."""
    global_id, _ = _create_pair(client)
    deleted = client.delete(f"/api/v1/rate-rules/{global_id}")
    assert deleted.status_code == 422
    assert deleted.json()["error"]["code"] == "CFG_LAST_RATE_RULE"
    disabled = client.patch(
        f"/api/v1/rate-rules/{global_id}", json={"enabled": False}
    )
    assert disabled.status_code == 422
    assert disabled.json()["error"]["code"] == "CFG_LAST_RATE_RULE"
    moved = client.patch(
        f"/api/v1/rate-rules/{global_id}", json={"scope": "PER_RECIPIENT"}
    )
    assert moved.status_code == 422
    assert moved.json()["error"]["code"] == "CFG_LAST_RATE_RULE"
    rule = next(
        item
        for item in client.get("/api/v1/rate-rules").json()
        if item["id"] == global_id
    )
    assert (rule["enabled"], rule["scope"]) == (True, "GLOBAL")


def test_AC_CFG_008_last_recipient_rule_cannot_be_disabled(
    client: TestClient,
) -> None:
    """Given the only PER_RECIPIENT rule, when disabled, then it is rejected."""
    _, recipient_id = _create_pair(client)
    response = client.patch(
        f"/api/v1/rate-rules/{recipient_id}", json={"enabled": False}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CFG_LAST_RATE_RULE"


def test_AC_CFG_008_extra_global_rule_can_be_deleted(client: TestClient) -> None:
    """Given two GLOBAL rules, when one is deleted, then it succeeds."""
    _create_pair(client)
    extra = client.post(
        "/api/v1/rate-rules",
        json={"name": "g2", "scope": "GLOBAL", "window_seconds": 10, "max_count": 5},
    ).json()
    removed = client.delete(f"/api/v1/rate-rules/{extra['id']}")
    assert removed.status_code == 204
    assert len(client.get("/api/v1/rate-rules").json()) == 2

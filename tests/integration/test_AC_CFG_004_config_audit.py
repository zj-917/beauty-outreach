"""Configuration change audit tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_AC_CFG_004_changes_write_audit_with_before_and_after(
    client: TestClient,
) -> None:
    """Given config changes, when applied, then each writes an audit with before/after."""
    created = client.post(
        "/api/v1/keywords",
        json={"term": "beauty", "kind": "POSITIVE", "weight": 10},
    )
    keyword_id = created.json()["id"]
    client.patch(f"/api/v1/keywords/{keyword_id}", json={"weight": 12})
    client.delete(f"/api/v1/keywords/{keyword_id}")
    client.post(
        "/api/v1/rate-rules",
        json={"name": "r", "scope": "GLOBAL", "window_seconds": 10, "max_count": 5},
    )
    client.put("/api/v1/settings", json={"message.brand": "AuditBrand"})

    keyword_logs = client.get(
        "/api/v1/audit-logs", params={"entity_type": "keyword"}
    ).json()
    assert [item["action"] for item in keyword_logs["items"]] == [
        "KEYWORD_DELETED",
        "KEYWORD_UPDATED",
        "KEYWORD_CREATED",
    ]
    updated = next(
        item for item in keyword_logs["items"] if item["action"] == "KEYWORD_UPDATED"
    )
    assert updated["before"] == {"weight": 10, "enabled": True}
    assert updated["after"] == {"weight": 12, "enabled": True}

    rule_logs = client.get(
        "/api/v1/audit-logs", params={"entity_type": "rate_rule"}
    ).json()
    assert rule_logs["total"] == 1
    assert rule_logs["items"][0]["action"] == "RATE_RULE_CREATED"

    setting_logs = client.get(
        "/api/v1/audit-logs", params={"entity_type": "system_setting"}
    ).json()
    assert setting_logs["total"] == 1
    assert setting_logs["items"][0]["entity_id"] == "message.brand"
    assert setting_logs["items"][0]["before"] == {"value": "GlowLab"}
    assert setting_logs["items"][0]["after"] == {"value": "AuditBrand"}


def test_AC_CFG_004_noop_updates_write_no_audit(client: TestClient) -> None:
    """Given an update that changes nothing, when applied, then no audit row is written."""
    keyword = client.post(
        "/api/v1/keywords",
        json={"term": "beauty", "kind": "POSITIVE", "weight": 10},
    ).json()
    client.patch(
        f"/api/v1/keywords/{keyword['id']}",
        json={"weight": 10, "enabled": True},
    )
    rule = client.post(
        "/api/v1/rate-rules",
        json={"name": "r", "scope": "GLOBAL", "window_seconds": 10, "max_count": 5},
    ).json()
    client.patch(
        f"/api/v1/rate-rules/{rule['id']}",
        json={"window_seconds": 10, "max_count": 5},
    )

    logs = client.get("/api/v1/audit-logs").json()
    assert [item["action"] for item in logs["items"]] == [
        "RATE_RULE_CREATED",
        "KEYWORD_CREATED",
    ]

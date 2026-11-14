"""Batch audit tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


def test_AC_LEAD_013_import_writes_batch_audit_without_phone(
    client: TestClient,
) -> None:
    """Given a successful import, when done, then one audit row records the batch and counts."""
    batch = client.post(
        "/api/v1/lead-batches/import",
        json={"source": "mock"},
        headers={"X-Operator": "ops"},
    ).json()
    logs = client.get(
        "/api/v1/audit-logs", params={"action": "LEAD_BATCH_IMPORTED"}
    ).json()
    assert logs["total"] == 1
    item = logs["items"][0]
    assert (item["entity_type"], item["entity_id"]) == ("lead_batch", str(batch["id"]))
    assert item["actor"] == "ops"
    assert item["after"] == {
        "source_type": "MOCK",
        "source_name": "mock_leads.json",
        "total_rows": 52,
        "imported": 44,
        "duplicates": 4,
        "invalid": 4,
        "warnings": 1,
    }
    assert "+1555555" not in json.dumps(item)
    assert client.get("/api/v1/audit-logs/verify").json()["ok"] is True

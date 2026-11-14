"""Mock dataset import tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_AC_LEAD_001_mock_import_report(client: TestClient) -> None:
    """Given the mock dataset, when imported, then the report matches the spec counts."""
    response = client.post(
        "/api/v1/lead-batches/import",
        json={"source": "mock"},
        headers={"X-Operator": "ops"},
    )
    assert response.status_code == 201
    body = response.json()
    assert (
        body["total_rows"],
        body["imported"],
        body["duplicates"],
        body["invalid"],
        body["warnings"],
    ) == (52, 44, 4, 4, 1)
    assert body["source_type"] == "MOCK"
    assert body["source_name"] == "mock_leads.json"
    assert body["created_by"] == "ops"
    assert body["created_at"].endswith("Z")

    listed = client.get("/api/v1/lead-batches").json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == body["id"]
    assert client.get("/api/v1/leads").json()["total"] == 44


def test_AC_LEAD_001_mock_report_lists_expected_error_codes(client: TestClient) -> None:
    """Given the mock dataset, when imported, then duplicate and invalid rows are explained."""
    body = client.post(
        "/api/v1/lead-batches/import", json={"source": "mock"}
    ).json()
    codes = {item["code"] for item in body["errors"]}
    assert codes == {
        "DUPLICATE_USERNAME",
        "DUPLICATE_PHONE",
        "IMPORT_CONFLICT",
        "MISSING_USERNAME",
        "INVALID_USERNAME",
        "INVALID_SOURCE_URL",
        "INVALID_PHONE_DROPPED",
    }
    rows = [item["row"] for item in body["errors"]]
    assert rows == sorted(rows)
    assert len(body["errors"]) == 9

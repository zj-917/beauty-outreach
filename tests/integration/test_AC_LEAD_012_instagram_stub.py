"""Instagram API stub tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_AC_LEAD_012_instagram_api_returns_501_without_network(
    client: TestClient,
) -> None:
    """Given the instagram_api source, when requested, then 501 is returned and no batch exists."""
    response = client.post(
        "/api/v1/lead-batches/import", json={"source": "instagram_api"}
    )
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "PROVIDER_NOT_ENABLED"
    assert client.get("/api/v1/lead-batches").json()["total"] == 0

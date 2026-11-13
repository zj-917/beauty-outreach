"""Runtime settings update tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_AC_CFG_003_valid_partial_update(client: TestClient) -> None:
    """Given valid updates, when applied, then only the given keys change."""
    initial = client.get("/api/v1/settings").json()
    assert initial["screening.threshold_high"] == 70
    response = client.put(
        "/api/v1/settings",
        json={"screening.threshold_high": 80, "message.brand": "NewBrand"},
    )
    assert response.status_code == 200
    assert response.json()["screening.threshold_high"] == 80
    assert response.json()["message.brand"] == "NewBrand"
    assert client.get("/api/v1/settings").json()["screening.threshold_high"] == 80


def test_AC_CFG_003_invalid_update_is_atomic(client: TestClient) -> None:
    """Given one invalid key, when submitted with a valid one, then nothing changes."""
    before = client.get("/api/v1/settings").json()
    crossed = client.put(
        "/api/v1/settings",
        json={"message.brand": "Changed", "screening.threshold_high": 30},
    )
    assert crossed.status_code == 422
    assert client.get("/api/v1/settings").json() == before

    unknown = client.put("/api/v1/settings", json={"unknown.key": 1})
    assert unknown.status_code == 422
    assert client.get("/api/v1/settings").json() == before

    wrong_type = client.put(
        "/api/v1/settings", json={"screening.auto_approve_enabled": "true"}
    )
    assert wrong_type.status_code == 422
    assert client.get("/api/v1/settings").json() == before

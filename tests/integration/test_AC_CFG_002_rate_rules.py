"""Rate rule CRUD tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_AC_CFG_002_rate_rule_crud(client: TestClient) -> None:
    """Given a valid rule, when created and patched, then it persists and updates."""
    created = client.post(
        "/api/v1/rate-rules",
        json={
            "name": "global",
            "scope": "GLOBAL",
            "window_seconds": 10,
            "max_count": 5,
        },
    )
    assert created.status_code == 201
    rule_id = created.json()["id"]
    patched = client.patch(f"/api/v1/rate-rules/{rule_id}", json={"max_count": 6})
    assert patched.status_code == 200
    assert patched.json()["max_count"] == 6
    assert client.get("/api/v1/rate-rules").json()[0]["scope"] == "GLOBAL"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "bad", "scope": "GLOBAL", "window_seconds": 0, "max_count": 1},
        {"name": "bad", "scope": "GLOBAL", "window_seconds": 1, "max_count": 0},
        {"name": "bad", "scope": "WRONG", "window_seconds": 1, "max_count": 1},
    ],
)
def test_AC_CFG_002_invalid_rate_rule_is_rejected(
    client: TestClient, payload: dict[str, object]
) -> None:
    """Given invalid rate rule fields, when created, then 422 is returned."""
    assert client.post("/api/v1/rate-rules", json=payload).status_code == 422

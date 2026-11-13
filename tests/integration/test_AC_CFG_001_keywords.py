"""Keyword CRUD tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_AC_CFG_001_keyword_crud_and_normalization(client: TestClient) -> None:
    """Given a keyword, when created/updated/deleted, then normalization and CRUD hold."""
    created = client.post(
        "/api/v1/keywords",
        json={"term": "  Beauty Device  ", "kind": "POSITIVE", "weight": 30},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["term"] == "beauty device"
    assert body["enabled"] is True
    assert body["created_at"].endswith("Z")
    keyword_id = body["id"]

    duplicate = client.post(
        "/api/v1/keywords",
        json={"term": "BEAUTY DEVICE", "kind": "POSITIVE", "weight": 10},
    )
    assert duplicate.status_code == 409

    patched = client.patch(
        f"/api/v1/keywords/{keyword_id}", json={"weight": 20, "enabled": False}
    )
    assert patched.status_code == 200
    assert patched.json()["weight"] == 20
    assert patched.json()["enabled"] is False

    listed = client.get("/api/v1/keywords").json()
    assert [item["term"] for item in listed] == ["beauty device"]

    deleted = client.delete(f"/api/v1/keywords/{keyword_id}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/keywords").json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"term": "x", "kind": "POSITIVE", "weight": 0},
        {"term": "x", "kind": "POSITIVE", "weight": 51},
        {"term": "   ", "kind": "POSITIVE", "weight": 10},
        {"term": "x", "kind": "UNKNOWN", "weight": 10},
    ],
)
def test_AC_CFG_001_invalid_keyword_is_rejected(
    client: TestClient, payload: dict[str, object]
) -> None:
    """Given invalid keyword fields, when created, then 422 is returned."""
    assert client.post("/api/v1/keywords", json=payload).status_code == 422

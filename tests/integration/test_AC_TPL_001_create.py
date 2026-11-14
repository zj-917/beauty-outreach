"""Template creation tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _create(
    client: TestClient,
    *,
    name: str = "welcome",
    body: str = "Hi {{name|there}}",
    language: str = "en",
    operator: str = "admin",
):
    return client.post(
        "/api/v1/templates",
        json={"name": name, "body": body, "language": language},
        headers={"X-Operator": operator},
    )


def test_AC_TPL_001_create_returns_draft_v1(client: TestClient) -> None:
    """Given a valid name and body, when created, then a DRAFT version 1 is returned."""
    response = _create(client, operator="alice")

    assert response.status_code == 201
    body = response.json()
    assert body["version"] == 1
    assert body["status"] == "DRAFT"
    assert body["created_by"] == "alice"
    assert body["approved_by"] is None
    assert body["approved_at"] is None
    assert body["body"] == "Hi {{name|there}}"
    assert body["created_at"] == "2026-11-14T09:00:00Z"

    listed = client.get("/api/v1/templates").json()
    assert [item["id"] for item in listed] == [body["id"]]
    assert client.get(f"/api/v1/templates/{body['id']}").json() == body

    audits = client.get(
        "/api/v1/audit-logs",
        params={
            "action": "TEMPLATE_CREATED",
            "entity_type": "template",
            "entity_id": str(body["id"]),
        },
    ).json()
    assert audits["total"] == 1
    entry = audits["items"][0]
    assert entry["actor"] == "alice"
    assert entry["after"]["name"] == "welcome"
    assert entry["after"]["version"] == 1
    assert entry["after"]["status"] == "DRAFT"
    assert "body" not in json.dumps(entry)


def test_AC_TPL_001_body_length_boundary(client: TestClient) -> None:
    """Given 800 characters, when created, then it passes; 801 is rejected with 422."""
    assert _create(client, name="ok", body="a" * 800).status_code == 201

    response = _create(client, name="too-long", body="a" * 801)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_AC_TPL_001_duplicate_name_and_version_conflict(client: TestClient) -> None:
    """Given an existing name/version, when created again, then 409 is returned."""
    assert _create(client).status_code == 201

    response = _create(client, body="Different {{name}}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_AC_TPL_001_missing_template_returns_not_found(client: TestClient) -> None:
    """Given an unknown template id, when read, then 404 is returned."""
    response = client.get("/api/v1/templates/9999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

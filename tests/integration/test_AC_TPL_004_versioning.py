"""Template versioning, approval and immutability tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

APPROVED_AT = "2026-11-14T09:00:00Z"


def _create(
    client: TestClient,
    *,
    name: str = "welcome",
    body: str = "Hi {{name}}",
    operator: str = "alice",
):
    return client.post(
        "/api/v1/templates",
        json={"name": name, "body": body, "language": "en"},
        headers={"X-Operator": operator},
    )


def _audits(client: TestClient, action: str, template_id: int) -> dict:
    return client.get(
        "/api/v1/audit-logs",
        params={
            "action": action,
            "entity_type": "template",
            "entity_id": str(template_id),
        },
    ).json()


def test_AC_TPL_004_draft_edit_approve_and_immutability(
    client: TestClient,
) -> None:
    """Given a draft, when edited and approved, then approved bodies are immutable and versioned."""
    template_id = _create(client).json()["id"]

    updated = client.patch(
        f"/api/v1/templates/{template_id}",
        json={"body": "Hello {{name}}"},
        headers={"X-Operator": "bob"},
    )
    assert updated.status_code == 200
    assert updated.json()["body"] == "Hello {{name}}"
    assert updated.json()["status"] == "DRAFT"
    edits = _audits(client, "TEMPLATE_UPDATED", template_id)
    assert edits["total"] == 1
    assert edits["items"][0]["actor"] == "bob"
    assert "body" not in json.dumps(edits["items"][0])

    approved = client.post(
        f"/api/v1/templates/{template_id}/approve",
        headers={"X-Operator": "carol"},
    )
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["status"] == "APPROVED"
    assert approved_body["approved_by"] == "carol"
    assert approved_body["approved_at"] == APPROVED_AT
    approvals = _audits(client, "TEMPLATE_APPROVED", template_id)
    assert approvals["total"] == 1
    assert approvals["items"][0]["actor"] == "carol"
    assert approvals["items"][0]["before"]["status"] == "DRAFT"
    assert approvals["items"][0]["after"]["status"] == "APPROVED"

    rejected = client.patch(
        f"/api/v1/templates/{template_id}",
        json={"body": "Changed {{name}}"},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "TEMPLATE_IMMUTABLE"
    assert (
        client.get(f"/api/v1/templates/{template_id}").json()["body"]
        == "Hello {{name}}"
    )

    versioned = client.post(
        f"/api/v1/templates/{template_id}/new-version",
        json={"body": "Hey {{name}}"},
        headers={"X-Operator": "dave"},
    )
    assert versioned.status_code == 201
    v2 = versioned.json()
    assert v2["version"] == 2
    assert v2["status"] == "DRAFT"
    assert v2["created_by"] == "dave"
    assert v2["approved_by"] is None
    assert _audits(client, "TEMPLATE_VERSIONED", v2["id"])["total"] == 1

    approved_v2 = client.post(
        f"/api/v1/templates/{v2['id']}/approve",
        headers={"X-Operator": "carol"},
    )
    assert approved_v2.status_code == 200
    assert approved_v2.json()["status"] == "APPROVED"

    listed = client.get("/api/v1/templates").json()
    versions = [
        item["version"] for item in listed if item["name"] == "welcome"
    ]
    assert versions == [2, 1]

    disabled = client.post(f"/api/v1/templates/{v2['id']}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"
    assert client.post(f"/api/v1/templates/{v2['id']}/disable").status_code == 200
    assert _audits(client, "TEMPLATE_DISABLED", v2["id"])["total"] == 1
    assert (
        client.patch(f"/api/v1/templates/{v2['id']}", json={"body": "Nope"}).status_code
        == 409
    )


def test_AC_TPL_004_new_version_conflict_is_reported(
    client: TestClient,
) -> None:
    """Given an existing next version, when creating it again, then 409 is returned."""
    template_id = _create(client).json()["id"]
    assert (
        client.post(
            f"/api/v1/templates/{template_id}/new-version",
            json={"body": "v2"},
        ).status_code
        == 201
    )

    response = client.post(
        f"/api/v1/templates/{template_id}/new-version",
        json={"body": "v2 again"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_AC_TPL_004_approve_requires_a_draft(client: TestClient) -> None:
    """Given a non-draft template, when approved, then 409 is returned."""
    template_id = _create(client).json()["id"]
    assert client.post(f"/api/v1/templates/{template_id}/approve").status_code == 200

    response = client.post(f"/api/v1/templates/{template_id}/approve")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"

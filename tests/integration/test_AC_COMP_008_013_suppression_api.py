"""Suppression API tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _post(
    client: TestClient,
    *,
    type: str = "BLACKLIST",
    phone: str | None = None,
    username: str | None = None,
    reason: str = "manual review",
    operator: str = "alice",
):
    body: dict[str, object] = {"type": type, "reason": reason}
    if phone is not None:
        body["phone"] = phone
    if username is not None:
        body["username"] = username
    return client.post(
        "/api/v1/suppressions", json=body, headers={"X-Operator": operator}
    )


def test_AC_COMP_013_add_suppression_by_phone_and_username(
    client: TestClient,
) -> None:
    """Given a phone or username, when added, then it is stored with masked data and audited."""
    phone_row = _post(client, phone="+15555550111", operator="alice")

    assert phone_row.status_code == 201
    body = phone_row.json()
    assert body["type"] == "BLACKLIST"
    assert body["phone_masked"] == "+155****0111"
    assert body["username"] is None
    assert body["source"] == "MANUAL"
    assert body["created_by"] == "alice"
    assert "phone_hash" not in body
    assert "phone" not in body

    username_row = _post(
        client, phone=None, username="@Glow.Routine", type="UNSUBSCRIBE"
    )
    assert username_row.status_code == 201
    assert username_row.json()["username"] == "glow.routine"
    assert username_row.json()["phone_masked"] is None

    audits = client.get(
        "/api/v1/audit-logs", params={"action": "SUPPRESSION_ADDED"}
    ).json()
    assert audits["total"] == 2
    assert "+15555550111" not in json.dumps(audits)


def test_AC_COMP_013_rejects_empty_or_invalid_identifiers(
    client: TestClient,
) -> None:
    """Given no identifier, an invalid phone or type, when added, then 422 is returned."""
    empty = _post(client)
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_phone = _post(client, phone="555-0101")
    assert invalid_phone.status_code == 422
    assert invalid_phone.json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_with_username = _post(
        client, phone="555-0101", username="glow.routine"
    )
    assert invalid_with_username.status_code == 422

    invalid_type = _post(client, type="OTHER", phone="+15555550111")
    assert invalid_type.status_code == 422


def test_AC_COMP_013_duplicate_registration_is_idempotent(
    client: TestClient,
) -> None:
    """Given an existing entry, when added again, then the same row is returned without audit."""
    first = _post(client, phone="+15555550111")
    second = _post(client, phone="+15555550111")

    assert first.status_code == second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert len(client.get("/api/v1/suppressions").json()) == 1
    audits = client.get(
        "/api/v1/audit-logs", params={"action": "SUPPRESSION_ADDED"}
    ).json()
    assert audits["total"] == 1


def test_AC_COMP_013_list_filters_by_type_and_masks_phones(
    client: TestClient,
) -> None:
    """Given entries of both types, when filtered, then types are separated and phones masked."""
    _post(client, type="BLACKLIST", phone="+15555550111")
    _post(client, type="UNSUBSCRIBE", phone="+15555550112")
    _post(client, type="BLACKLIST", username="glow.routine")

    blacklist = client.get(
        "/api/v1/suppressions", params={"type": "BLACKLIST"}
    ).json()
    assert len(blacklist) == 2
    assert all(item["type"] == "BLACKLIST" for item in blacklist)
    assert all("phone_hash" not in item for item in blacklist)

    unsubscribed = client.get(
        "/api/v1/suppressions", params={"type": "UNSUBSCRIBE"}
    ).json()
    assert len(unsubscribed) == 1
    assert unsubscribed[0]["phone_masked"] == "+155****0112"

    invalid = client.get(
        "/api/v1/suppressions", params={"type": "OTHER"}
    )
    assert invalid.status_code == 422


def test_AC_COMP_008_blacklist_can_be_deleted_but_unsubscribe_cannot(
    client: TestClient,
) -> None:
    """Given both types, when deleted, then BLACKLIST succeeds and UNSUBSCRIBE is immutable."""
    blacklist = _post(client, type="BLACKLIST", phone="+15555550111").json()
    unsubscribed = _post(client, type="UNSUBSCRIBE", phone="+15555550112").json()

    deleted = client.delete(f"/api/v1/suppressions/{blacklist['id']}")
    assert deleted.status_code == 204
    remaining = client.get("/api/v1/suppressions").json()
    assert [item["id"] for item in remaining] == [unsubscribed["id"]]
    removed = client.get(
        "/api/v1/audit-logs", params={"action": "SUPPRESSION_REMOVED"}
    ).json()
    assert removed["total"] == 1
    assert removed["items"][0]["before"]["type"] == "BLACKLIST"
    assert "+15555550111" not in json.dumps(removed)

    immutable = client.delete(f"/api/v1/suppressions/{unsubscribed['id']}")
    assert immutable.status_code == 409
    assert immutable.json()["error"]["code"] == "COMP_UNSUBSCRIBE_IMMUTABLE"
    assert client.get("/api/v1/suppressions").json()[0]["id"] == unsubscribed["id"]

    missing = client.delete("/api/v1/suppressions/9999")
    assert missing.status_code == 404

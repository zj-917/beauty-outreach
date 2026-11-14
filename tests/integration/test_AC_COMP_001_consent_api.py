"""Consent API tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.clock import FakeClock


def _put(
    client: TestClient,
    *,
    phone: str = "+15555550101",
    status: str = "GRANTED",
    source: str = "web_form",
    evidence: str | None = "form-1",
    operator: str = "alice",
):
    body: dict[str, object] = {
        "phone": phone,
        "status": status,
        "source": source,
    }
    if evidence is not None:
        body["evidence_ref"] = evidence
    return client.put(
        "/api/v1/consents", json=body, headers={"X-Operator": operator}
    )


def test_AC_COMP_001_upsert_returns_masked_consent_and_audits(
    client: TestClient,
) -> None:
    """Given a valid consent, when upserted, then only the masked phone is exposed and audited."""
    response = _put(client)

    assert response.status_code == 200
    body = response.json()
    assert body["phone_masked"] == "+155****0101"
    assert body["status"] == "GRANTED"
    assert body["source"] == "web_form"
    assert body["evidence_ref"] == "form-1"
    assert body["granted_at"] == "2026-11-14T09:00:00Z"
    assert body["updated_by"] == "alice"
    assert "phone" not in body
    assert "phone_hash" not in body

    audits = client.get(
        "/api/v1/audit-logs", params={"action": "CONSENT_UPSERTED"}
    ).json()
    assert audits["total"] == 1
    entry = audits["items"][0]
    assert entry["actor"] == "alice"
    assert entry["after"] == {
        "phone_masked": "+155****0101",
        "status": "GRANTED",
    }
    assert "+15555550101" not in json.dumps(entry)

    listed = client.get("/api/v1/consents").json()
    assert len(listed) == 1
    assert listed[0]["phone_masked"] == "+155****0101"
    assert "phone_hash" not in listed[0]


def test_AC_COMP_001_upsert_to_revoked_records_before_and_after(
    client: TestClient,
) -> None:
    """Given GRANTED consent, when revoked, then the audit keeps masked before/after states."""
    assert _put(client).status_code == 200

    revoked = _put(
        client, status="REVOKED", source="user_request", evidence=None
    )

    assert revoked.status_code == 200
    body = revoked.json()
    assert body["status"] == "REVOKED"
    assert body["granted_at"] is None
    audits = client.get(
        "/api/v1/audit-logs", params={"action": "CONSENT_UPSERTED"}
    ).json()
    assert audits["total"] == 2
    newest = audits["items"][0]
    assert newest["before"] == {
        "phone_masked": "+155****0101",
        "status": "GRANTED",
    }
    assert newest["after"] == {
        "phone_masked": "+155****0101",
        "status": "REVOKED",
    }


def test_AC_COMP_001_repeat_grant_keeps_the_original_grant_time(
    client: TestClient, clock: FakeClock
) -> None:
    """Given an existing grant, when granted again later, then the original grant time stays."""
    first = _put(client).json()
    clock.advance(3600)

    second = _put(client, source="crm", evidence="form-2")

    assert second.status_code == 200
    assert second.json()["granted_at"] == first["granted_at"]
    assert second.json()["evidence_ref"] == "form-2"


def test_AC_COMP_001_rejects_incomplete_or_invalid_input(
    client: TestClient,
) -> None:
    """Given missing source/evidence or an invalid phone, when upserted, then 422 and no audit."""
    no_source = client.put(
        "/api/v1/consents",
        json={
            "phone": "+15555550101",
            "status": "GRANTED",
            "source": "",
            "evidence_ref": "form-1",
        },
    )
    assert no_source.status_code == 422

    no_evidence = _put(client, evidence=None)
    assert no_evidence.status_code == 422
    assert no_evidence.json()["error"]["code"] == "VALIDATION_ERROR"

    bad_phone = _put(client, phone="555-0101")
    assert bad_phone.status_code == 422
    assert bad_phone.json()["error"]["code"] == "VALIDATION_ERROR"

    bad_status = _put(client, status="UNKNOWN")
    assert bad_status.status_code == 422

    assert client.get("/api/v1/consents").json() == []
    audits = client.get(
        "/api/v1/audit-logs", params={"action": "CONSENT_UPSERTED"}
    ).json()
    assert audits["total"] == 0

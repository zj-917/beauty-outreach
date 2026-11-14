"""Consent import tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import ContactConsent

HEADER = "username,phone,consent_status,consent_source,consent_evidence\n"


def _import(client: TestClient, rows: str) -> dict:
    response = client.post(
        "/api/v1/lead-batches/import",
        files={"file": ("consent.csv", (HEADER + rows).encode(), "text/csv")},
    )
    assert response.status_code == 201
    return response.json()


def _consent(client: TestClient, db: Engine, phone: str) -> ContactConsent | None:
    phone_hash = client.app.state.phone_cipher.hash_phone(phone)
    with Session(db) as session:
        return session.scalar(
            select(ContactConsent).where(ContactConsent.phone_hash == phone_hash)
        )


def test_AC_LEAD_009_consent_rows_are_upgraded_but_not_downgraded(
    client: TestClient, db: Engine
) -> None:
    """Given granted/revoked consent rows, then records follow completeness and revocation rules."""
    body = _import(
        client,
        "consent.good,+15555550141,GRANTED,web_form,form-9\n"
        "consent.bad,+15555550142,GRANTED,web_form,\n"
        "consent.rev,+15555550143,REVOKED,crm,\n",
    )
    assert (body["imported"], body["warnings"]) == (3, 1)
    codes = {(item["row"], item["code"]) for item in body["errors"]}
    assert (2, "CONSENT_INCOMPLETE") in codes

    good = _consent(client, db, "+15555550141")
    assert good is not None
    assert (good.status, good.source, good.evidence_ref) == (
        "GRANTED",
        "web_form",
        "form-9",
    )
    assert _consent(client, db, "+15555550142") is None
    revoked = _consent(client, db, "+15555550143")
    assert revoked is not None
    assert revoked.status == "REVOKED"

    _import(client, "consent.rev,+15555550143,GRANTED,web_form,form-10\n")
    assert _consent(client, db, "+15555550143").status == "REVOKED"

    _import(client, "consent.good,+15555550141,REVOKED,crm,ticket-1\n")
    updated = _consent(client, db, "+15555550141")
    assert updated is not None
    assert updated.status == "REVOKED"

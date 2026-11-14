"""Pool delivery-readiness tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.domain.gates import READINESS_VALUES, Pass, Skip, evaluate, readiness
from app.domain.masking import mask_phone
from app.models import Lead
from app.repositories import lead_repo
from app.services.compliance_service import ComplianceService
from app.services.seed_service import seed_defaults


def _prepare(client: TestClient, db: Engine, clock: FakeClock) -> None:
    with Session(db) as session:
        seed_defaults(session, clock)
    assert (
        client.post(
            "/api/v1/lead-batches/import", json={"source": "mock"}
        ).status_code
        == 201
    )
    assert client.post("/api/v1/leads/screen").status_code == 200


def _approved(db: Engine, count: int) -> list[tuple[int, str]]:
    with Session(db) as session:
        rows = session.scalars(
            select(Lead)
            .where(Lead.status == "APPROVED")
            .order_by(Lead.id)
            .limit(count)
        ).all()
        assert len(rows) == count
        return [(row.id, row.username) for row in rows]


def _set_phone(db: Engine, cipher: object, lead_id: int, phone: str) -> None:
    with Session(db) as session:
        lead = session.get(Lead, lead_id)
        assert lead is not None
        lead.phone_enc = cipher.encrypt(phone)
        lead.phone_hash = cipher.hash_phone(phone)
        lead.phone_masked = mask_phone(phone)
        session.commit()


def _clear_phone(db: Engine, lead_id: int) -> None:
    with Session(db) as session:
        lead = session.get(Lead, lead_id)
        assert lead is not None
        lead.phone_enc = None
        lead.phone_hash = None
        lead.phone_masked = None
        session.commit()


def _put_consent(
    client: TestClient,
    phone: str,
    *,
    status: str = "GRANTED",
    source: str = "web_form",
    evidence: str | None = "form-x",
):
    body: dict[str, object] = {
        "phone": phone,
        "status": status,
        "source": source,
    }
    if evidence is not None:
        body["evidence_ref"] = evidence
    return client.put("/api/v1/consents", json=body)


def _post_suppression(client: TestClient, **body: object):
    return client.post(
        "/api/v1/suppressions", json={"reason": "test", **body}
    )


def test_AC_POOL_006_pool_labels_readiness_and_counts(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given pool leads in every compliance state, when listed, then readiness and counts match."""
    _prepare(client, db, clock)
    approved = _approved(db, 6)
    lead_ids = [item[0] for item in approved]
    usernames = [item[1] for item in approved]
    cipher = client.app.state.phone_cipher

    _set_phone(db, cipher, lead_ids[0], "+15555556001")
    assert _put_consent(client, "+15555556001").status_code == 200

    _set_phone(db, cipher, lead_ids[1], "+15555556002")
    assert _put_consent(client, "+15555556002").status_code == 200
    assert (
        _post_suppression(
            client, type="BLACKLIST", username=usernames[1]
        ).status_code
        == 201
    )

    _set_phone(db, cipher, lead_ids[2], "+15555556003")
    assert _put_consent(client, "+15555556003").status_code == 200
    assert (
        _post_suppression(
            client, type="UNSUBSCRIBE", phone="+15555556003"
        ).status_code
        == 201
    )

    _clear_phone(db, lead_ids[3])

    _set_phone(db, cipher, lead_ids[4], "+15555556005")

    _set_phone(db, cipher, lead_ids[5], "+15555556006")
    assert (
        _put_consent(
            client,
            "+15555556006",
            status="REVOKED",
            source="user_request",
            evidence=None,
        ).status_code
        == 200
    )

    before_audit = client.get("/api/v1/audit-logs").json()["total"]
    body = client.get("/api/v1/pool", params={"page_size": 100}).json()
    after_audit = client.get("/api/v1/audit-logs").json()["total"]

    assert after_audit == before_audit
    by_id = {item["id"]: item for item in body["items"]}
    expected = {
        lead_ids[0]: "READY",
        lead_ids[1]: "BLACKLISTED",
        lead_ids[2]: "UNSUBSCRIBED",
        lead_ids[3]: "NO_PHONE",
        lead_ids[4]: "NO_CONSENT",
        lead_ids[5]: "CONSENT_REVOKED",
    }
    for lead_id, label in expected.items():
        assert by_id[lead_id]["delivery_readiness"] == label

    counts = body["readiness_counts"]
    assert set(counts) == set(READINESS_VALUES)
    assert sum(counts.values()) == body["total"] == 20
    for label in expected.values():
        assert counts[label] >= 1

    compliance = ComplianceService(clock, cipher, client.app.state.audit_service)
    with Session(db) as session:
        settings = compliance.settings(session)
        recomputed = {value: 0 for value in READINESS_VALUES}
        for lead in lead_repo.list_all_pool(session):
            recomputed[
                compliance.readiness_for_lead(session, lead, settings=settings)
            ] += 1
        assert counts == recomputed

        for lead_id, label in expected.items():
            lead = lead_repo.get_lead(session, lead_id)
            assert lead is not None
            snapshot = compliance.snapshot_for_lead(
                session, lead, settings=settings
            )
            assert readiness(snapshot) == label
            result = evaluate(snapshot)
            if label == "READY":
                assert isinstance(result, Pass)
            else:
                assert result == Skip(label)

        statuses = {
            row.id: row.status for row in session.scalars(select(Lead)).all()
        }
        assert all(statuses[lead_id] == "APPROVED" for lead_id in lead_ids)

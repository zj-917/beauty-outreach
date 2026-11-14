"""Manual review transition tests."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import Lead
from app.services.seed_service import seed_defaults

REVIEWED_AT = "2026-11-14T09:00:00Z"


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


def _lead_id(db: Engine, status: str) -> int:
    with Session(db) as session:
        row = session.scalar(
            select(Lead).where(Lead.status == status).order_by(Lead.id).limit(1)
        )
        assert row is not None
        return row.id


def _set_lead(db: Engine, lead_id: int, **values: object) -> None:
    with Session(db) as session:
        row = session.get(Lead, lead_id)
        assert row is not None
        for name, value in values.items():
            setattr(row, name, value)
        session.commit()


def _review(
    client: TestClient,
    lead_id: int,
    decision: str,
    note: str | None = None,
    *,
    operator: str = "admin",
):
    body: dict[str, object] = {"decision": decision}
    if note is not None:
        body["note"] = note
    return client.post(
        f"/api/v1/leads/{lead_id}/review",
        json=body,
        headers={"X-Operator": operator},
    )


def _review_audits(client: TestClient, lead_id: int) -> dict:
    return client.get(
        "/api/v1/audit-logs",
        params={
            "action": "LEAD_REVIEWED",
            "entity_type": "lead",
            "entity_id": str(lead_id),
        },
    ).json()


@pytest.mark.parametrize(
    ("current", "decision", "note", "expected", "expected_note"),
    [
        ("PENDING_REVIEW", "APPROVE", None, "APPROVED", None),
        ("PENDING_REVIEW", "REJECT", "not relevant", "REJECTED", "not relevant"),
        ("APPROVED", "APPROVE", None, "APPROVED", "old"),
        ("APPROVED", "REJECT", "spam", "REJECTED", "spam"),
        ("REJECTED", "APPROVE", "restored", "APPROVED", "restored"),
        ("REJECTED", "REJECT", None, "REJECTED", "old"),
        ("DISCARDED", "APPROVE", "manual override", "APPROVED", "manual override"),
        ("DISCARDED", "REJECT", "off topic", "REJECTED", "off topic"),
    ],
)
def test_AC_POOL_003_transition_table(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    current: str,
    decision: str,
    note: str | None,
    expected: str,
    expected_note: str | None,
) -> None:
    """Given each legal transition, when reviewed, then status, metadata and audit are recorded."""
    _prepare(client, db, clock)
    lead_id = _lead_id(db, "PENDING_REVIEW")
    _set_lead(
        db,
        lead_id,
        status=current,
        decision_source="AUTO",
        reviewed_by=None,
        reviewed_at=None,
        review_note="old",
    )

    response = _review(client, lead_id, decision, note, operator="alice")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected
    assert body["decision_source"] == "MANUAL"
    assert body["reviewed_by"] == "alice"
    assert body["reviewed_at"] == REVIEWED_AT
    assert body["review_note"] == expected_note

    audits = _review_audits(client, lead_id)
    assert audits["total"] == 1
    entry = audits["items"][0]
    assert entry["actor"] == "alice"
    assert entry["before"]["status"] == current
    assert entry["before"]["note"] == "old"
    assert entry["after"]["status"] == expected
    assert entry["after"]["note"] == expected_note
    assert "phone" not in json.dumps(entry)


@pytest.mark.parametrize("current", ["REJECTED", "DISCARDED"])
@pytest.mark.parametrize("note", [None, "", "   "])
def test_AC_POOL_003_restoring_an_approved_lead_requires_a_note(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    current: str,
    note: str | None,
) -> None:
    """Given a rejected or discarded lead, when approved without a note, then 422 and no change."""
    _prepare(client, db, clock)
    lead_id = _lead_id(db, "PENDING_REVIEW")
    _set_lead(
        db,
        lead_id,
        status=current,
        decision_source="AUTO",
        reviewed_by=None,
        reviewed_at=None,
        review_note=None,
    )

    response = _review(client, lead_id, "APPROVE", note)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    lead = client.get(f"/api/v1/leads/{lead_id}").json()
    assert lead["status"] == current
    assert lead["reviewed_by"] is None
    assert _review_audits(client, lead_id)["total"] == 0


@pytest.mark.parametrize("decision", ["APPROVE", "REJECT"])
def test_AC_POOL_003_new_lead_cannot_be_reviewed(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    decision: str,
) -> None:
    """Given an unscreened NEW lead, when reviewed, then 409 and no audit is written."""
    _prepare(client, db, clock)
    lead_id = _lead_id(db, "PENDING_REVIEW")
    _set_lead(db, lead_id, status="NEW", decision_source=None, review_note=None)

    response = _review(client, lead_id, decision)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    assert client.get(f"/api/v1/leads/{lead_id}").json()["status"] == "NEW"
    assert _review_audits(client, lead_id)["total"] == 0


def test_AC_POOL_003_missing_lead_returns_not_found(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given an unknown lead id, when reviewed, then 404 is returned."""
    _prepare(client, db, clock)

    response = _review(client, 999_999, "APPROVE")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_AC_POOL_003_unknown_decision_is_validation_error(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given an unknown decision, when reviewed, then the request is rejected with 422."""
    _prepare(client, db, clock)
    lead_id = _lead_id(db, "PENDING_REVIEW")

    response = client.post(
        f"/api/v1/leads/{lead_id}/review", json={"decision": "MAYBE"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get(f"/api/v1/leads/{lead_id}").json()["status"] == "PENDING_REVIEW"

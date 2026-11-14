"""Bulk manual review tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import Lead
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


def _lead_ids(db: Engine, status: str, count: int) -> list[int]:
    with Session(db) as session:
        rows = session.scalars(
            select(Lead).where(Lead.status == status).order_by(Lead.id).limit(count)
        ).all()
        assert len(rows) == count
        return [row.id for row in rows]


def _set_status(db: Engine, lead_id: int, status: str) -> None:
    with Session(db) as session:
        row = session.get(Lead, lead_id)
        assert row is not None
        row.status = status
        row.decision_source = None
        row.reviewed_by = None
        row.reviewed_at = None
        row.review_note = None
        session.commit()


def test_AC_POOL_004_bulk_reviews_each_item_independently(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a mixed batch, when bulk reviewed, then each item succeeds or reports its own error."""
    _prepare(client, db, clock)
    first_pending, second_pending = _lead_ids(db, "PENDING_REVIEW", 2)
    discarded_id = _lead_ids(db, "DISCARDED", 1)[0]
    new_id = _lead_ids(db, "DISCARDED", 2)[1]
    _set_status(db, new_id, "NEW")

    response = client.post(
        "/api/v1/leads/review-bulk",
        json={
            "reviews": [
                {"lead_id": first_pending, "decision": "APPROVE"},
                {"lead_id": new_id, "decision": "APPROVE"},
                {"lead_id": discarded_id, "decision": "APPROVE"},
                {"lead_id": 999_999, "decision": "REJECT"},
                {"lead_id": second_pending, "decision": "REJECT", "note": "not a fit"},
                {"lead_id": first_pending, "decision": "APPROVE"},
            ]
        },
        headers={"X-Operator": "alice"},
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert [result["lead_id"] for result in results] == [
        first_pending,
        new_id,
        discarded_id,
        999_999,
        second_pending,
        first_pending,
    ]
    assert [result["ok"] for result in results] == [
        True,
        False,
        False,
        False,
        True,
        True,
    ]
    assert results[1]["error"]["code"] == "CONFLICT"
    assert results[2]["error"]["code"] == "VALIDATION_ERROR"
    assert results[3]["error"]["code"] == "NOT_FOUND"
    assert "error" not in results[0]
    assert "error" not in results[4]
    assert "error" not in results[5]

    assert client.get(f"/api/v1/leads/{first_pending}").json()["status"] == "APPROVED"
    assert client.get(f"/api/v1/leads/{second_pending}").json()["status"] == "REJECTED"
    assert client.get(f"/api/v1/leads/{new_id}").json()["status"] == "NEW"
    assert client.get(f"/api/v1/leads/{discarded_id}").json()["status"] == "DISCARDED"

    audits = client.get(
        "/api/v1/audit-logs", params={"action": "LEAD_REVIEWED"}
    ).json()
    assert audits["total"] == 3
    assert {item["actor"] for item in audits["items"]} == {"alice"}


def test_AC_POOL_004_more_than_200_reviews_is_rejected(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given 201 reviews, when bulk reviewed, then the request is rejected with 422."""
    _prepare(client, db, clock)
    reviews = [
        {"lead_id": 1, "decision": "APPROVE"} for _ in range(201)
    ]

    response = client.post(
        "/api/v1/leads/review-bulk", json={"reviews": reviews}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert (
        client.get("/api/v1/audit-logs", params={"action": "LEAD_REVIEWED"}).json()[
            "total"
        ]
        == 0
    )

"""Goal pool query tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.services.seed_service import seed_defaults


def _prepare(client: TestClient, db: Engine, clock: FakeClock) -> None:
    with Session(db) as session:
        seed_defaults(session, clock)
    response = client.post("/api/v1/lead-batches/import", json={"source": "mock"})
    assert response.status_code == 201
    assert client.post("/api/v1/leads/screen").status_code == 200


def test_AC_POOL_001_pool_returns_only_approved_sorted_by_score(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given mixed-status leads, when GET /pool, then only APPROVED leads return, by score."""
    _prepare(client, db, clock)

    body = client.get("/api/v1/pool", params={"page_size": 20}).json()

    assert body["total"] == 20
    assert len(body["items"]) == 20
    assert all(item["status"] == "APPROVED" for item in body["items"])
    scores = [item["score"] for item in body["items"]]
    assert scores == sorted(scores, reverse=True)


def test_AC_POOL_001_pool_pagination_covers_each_lead_once(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given an approved pool, when paged, then every lead appears exactly once in score order."""
    _prepare(client, db, clock)

    pages = [
        client.get(
            "/api/v1/pool", params={"page": page, "page_size": 7}
        ).json()
        for page in (1, 2, 3)
    ]

    assert [page["total"] for page in pages] == [20, 20, 20]
    assert [len(page["items"]) for page in pages] == [7, 7, 6]
    ids = [item["id"] for page in pages for item in page["items"]]
    assert len(ids) == len(set(ids)) == 20
    scores = [item["score"] for page in pages for item in page["items"]]
    assert scores == sorted(scores, reverse=True)


def test_AC_POOL_001_rejected_lead_leaves_the_pool(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given an approved lead, when manually rejected, then it no longer appears in GET /pool."""
    _prepare(client, db, clock)
    approved_id = client.get("/api/v1/pool").json()["items"][0]["id"]

    response = client.post(
        f"/api/v1/leads/{approved_id}/review",
        json={"decision": "REJECT", "note": "no longer a fit"},
    )
    assert response.status_code == 200

    body = client.get("/api/v1/pool", params={"page_size": 100}).json()
    assert body["total"] == 19
    assert approved_id not in [item["id"] for item in body["items"]]

"""Manual review queue tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
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


def test_AC_POOL_002_pending_review_queue_is_score_ordered_with_reasons(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given screened leads, when listing PENDING_REVIEW, then score order and reasons hold."""
    _prepare(client, db, clock)

    body = client.get(
        "/api/v1/leads", params={"status": "PENDING_REVIEW"}
    ).json()

    assert body["total"] == 8
    assert len(body["items"]) == 8
    assert all(item["status"] == "PENDING_REVIEW" for item in body["items"])
    scores = [item["score"] for item in body["items"]]
    assert scores == sorted(scores, reverse=True)
    for item in body["items"]:
        reasons = item["score_reasons"]
        assert reasons
        for reason in reasons:
            assert {"code", "detail", "delta"} <= set(reason)
        assert sum(reason["delta"] for reason in reasons) == item["score"]


def test_AC_POOL_002_pending_review_queue_paginates_in_score_order(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a pending queue, when paged, then pages keep the score order without gaps."""
    _prepare(client, db, clock)

    pages = [
        client.get(
            "/api/v1/leads",
            params={"status": "PENDING_REVIEW", "page": page, "page_size": 3},
        ).json()
        for page in (1, 2, 3)
    ]

    assert [len(page["items"]) for page in pages] == [3, 3, 2]
    scores = [item["score"] for page in pages for item in page["items"]]
    assert scores == sorted(scores, reverse=True)
    ids = [item["id"] for page in pages for item in page["items"]]
    assert len(ids) == len(set(ids)) == 8

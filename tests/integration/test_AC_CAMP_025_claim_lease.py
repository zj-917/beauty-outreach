"""Atomic claim and lease tests (AC-CAMP-025)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.providers.messenger.mock import MockMessenger
from app.services.seed_service import seed_defaults


def _seed(client: TestClient, db: Engine, clock: FakeClock) -> int:
    with Session(db) as session:
        seed_defaults(session, clock)
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _make_worker(
    app: FastAPI, clock: FakeClock, messenger: MockMessenger, worker_id: str
) -> Worker:
    processor = Processor(
        clock, app.state.phone_cipher, messenger, worker_id=worker_id
    )
    return Worker(app.state.session_factory, clock, processor, worker_id=worker_id)


def test_AC_CAMP_025_concurrent_claims_never_overlap(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    app: FastAPI,
    messenger: MockMessenger,
    make_lead,
) -> None:
    """Given two claimers, when they claim at once, then each item goes to exactly one."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username=f"claim_{index}", phone=f"+15555550{300 + index}")
        for index in range(12)
    ]
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "claims",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200

    first = _make_worker(app, clock, messenger, "worker-a")
    second = _make_worker(app, clock, messenger, "worker-b")
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(
            pool.map(
                lambda candidate: candidate.claim(campaign_id),
                (first, second),
            )
        )

    claimed_a, claimed_b = claims
    assert set(claimed_a).isdisjoint(claimed_b)
    assert len(claimed_a) + len(claimed_b) == 12
    assert max(len(claimed_a), len(claimed_b)) <= 10


def test_AC_CAMP_025_live_leases_are_not_reclaimed(
    client: TestClient,
    db: Engine,
    clock: FakeClock,
    worker: Worker,
    make_lead,
) -> None:
    """Given freshly leased items, when claiming again, then nothing is reclaimed."""
    template_id = _seed(client, db, clock)
    lead_ids = [
        make_lead(username=f"lease_{index}", phone=f"+15555550{320 + index}")
        for index in range(3)
    ]
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "leases",
            "template_id": template_id,
            "selection": {"lead_ids": lead_ids},
        },
    )
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200

    claimed = worker.claim(campaign_id)
    assert len(claimed) == 3

    assert worker.claim(campaign_id) == []

    clock.advance(61)
    reclaimed = worker.claim(campaign_id)
    assert set(reclaimed) == set(claimed)

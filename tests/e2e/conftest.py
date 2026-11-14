"""Fixtures shared by the end-to-end scenarios (06-test-plan §5, E2E-1~10)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.services.receipt_service import ReceiptService
from app.services.seed_service import seed_defaults


@pytest.fixture
def seeded(db: Engine, app: FastAPI, clock: FakeClock) -> None:
    """Seed defaults plus the mock blacklist suppressions (needs the cipher)."""
    with Session(db) as session:
        seed_defaults(session, clock, cipher=app.state.phone_cipher)


@pytest.fixture
def template_id(client: TestClient, seeded: None) -> int:
    """Id of the seeded approved greeting template."""
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


@pytest.fixture
def make_worker(app: FastAPI, clock: FakeClock) -> Callable[..., Worker]:
    """Build a worker with a zero-jitter RNG so retry times are exact."""

    def _make(messenger: object, *, receipts: bool = False) -> Worker:
        processor = Processor(
            clock,
            app.state.phone_cipher,
            messenger,
            worker_id="e2e-worker",
            audit=app.state.audit_service,
            rng=lambda: 0.0,
        )
        poller = (
            ReceiptService(
                clock,
                messenger=messenger,
                session_factory=app.state.session_factory,
            )
            if receipts
            else None
        )
        return Worker(
            app.state.session_factory,
            clock,
            processor,
            worker_id="e2e-worker",
            receipts=poller,
        )

    return _make


@pytest.fixture
def run_until_complete(
    client: TestClient, clock: FakeClock
) -> Callable[..., str]:
    """Tick the worker, advancing one second per tick, until a task finishes."""

    def _run(worker: Worker, campaign_id: int, *, max_ticks: int = 300) -> str:
        status = "RUNNING"
        for _ in range(max_ticks):
            worker.tick()
            status = client.get(f"/api/v1/campaigns/{campaign_id}").json()["status"]
            if status in {"COMPLETED", "CANCELLED"}:
                return status
            clock.advance(1)
        return status

    return _run

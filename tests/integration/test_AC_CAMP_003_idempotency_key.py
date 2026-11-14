"""Idempotency-key derivation and uniqueness tests."""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.core.errors import AppError
from app.models import TaskItem
from app.repositories import campaign_repo
from app.services.seed_service import seed_defaults


def _prepare(client: TestClient, db: Engine, clock: FakeClock) -> int:
    """Seed defaults, import the mock batch, screen it and return the approved template id."""
    with Session(db) as session:
        seed_defaults(session, clock)
    assert client.post("/api/v1/lead-batches/import", json={"source": "mock"}).status_code == 201
    assert client.post("/api/v1/leads/screen").status_code == 200
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _create(client: TestClient, template_id: int) -> int:
    response = client.post(
        "/api/v1/campaigns",
        json={"name": "keys", "template_id": template_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _expected_key(task_id: int, lead_id: int, template_id: int) -> str:
    return hashlib.sha256(f"{task_id}:{lead_id}:{template_id}".encode()).hexdigest()


def test_AC_CAMP_003_keys_follow_the_formula_and_are_globally_unique(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given two tasks over one pool, when keys are read, then the formula holds and all differ."""
    template_id = _prepare(client, db, clock)
    first = _create(client, template_id)
    second = _create(client, template_id)

    with Session(db) as session:
        rows = session.scalars(select(TaskItem)).all()
        assert len(rows) == 40
        for row in rows:
            assert row.idempotency_key == _expected_key(
                row.task_id, row.lead_id, template_id
            )
        assert len({row.idempotency_key for row in rows}) == 40
        assert {row.task_id for row in rows} == {first, second}


def test_AC_CAMP_003_duplicate_key_is_rejected_and_rolled_back(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given an existing item, when the same key is inserted, then the DB rejects it cleanly."""
    template_id = _prepare(client, db, clock)
    campaign_id = _create(client, template_id)

    with Session(db) as session:
        existing = session.scalar(
            select(TaskItem).where(TaskItem.task_id == campaign_id)
        )
        assert existing is not None
        count_before = session.scalar(
            select(func.count()).select_from(TaskItem)
        )
        with pytest.raises(AppError) as excinfo:
            campaign_repo.insert_item(
                session,
                task_id=existing.task_id,
                lead_id=existing.lead_id,
                idempotency_key=existing.idempotency_key,
                phone_hash=existing.phone_hash,
                phone_masked=existing.phone_masked,
                created_at=clock.now(),
                updated_at=clock.now(),
            )
        assert excinfo.value.code == "CONFLICT"
        count_after = session.scalar(select(func.count()).select_from(TaskItem))
        assert count_after == count_before

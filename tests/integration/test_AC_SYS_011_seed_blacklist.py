"""Mock blacklist seeding for demo and reset (AC-SYS-011)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.services.seed_service import seed_defaults


def test_AC_SYS_011_seed_imports_blacklist_idempotently(
    client: TestClient, app: FastAPI, db: Engine, clock: FakeClock
) -> None:
    """Given the seed, when run twice, then the three mock entries exist only once."""
    with Session(db) as session:
        first = seed_defaults(session, clock, cipher=app.state.phone_cipher)
    assert first["suppressions"] == 3

    entries = client.get("/api/v1/suppressions").json()
    assert len(entries) == 3
    assert [entry["type"] for entry in entries].count("BLACKLIST") == 2
    assert [entry["type"] for entry in entries].count("UNSUBSCRIBE") == 1
    assert {entry["source"] for entry in entries} == {"IMPORT"}
    assert {
        entry["phone_masked"] for entry in entries if entry["phone_masked"]
    } == {"+155****0111", "+155****0112"}
    assert {entry["username"] for entry in entries if entry["username"]} == {
        "glow.routine"
    }

    with Session(db) as session:
        second = seed_defaults(session, clock, cipher=app.state.phone_cipher)
    assert second["suppressions"] == 0
    assert len(client.get("/api/v1/suppressions").json()) == 3


def test_AC_SYS_011_demo_reset_reseeds_blacklist(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given demo mode, when /demo/reset runs, then the blacklist is seeded again."""
    response = client.post("/demo/reset")

    assert response.status_code == 200
    assert response.json()["counts"]["suppressions"] == 3
    assert len(client.get("/api/v1/suppressions").json()) == 3

"""Smoke test for a fresh environment start (AC-SYS-007)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.core.config import Settings
from app.main import create_app

FERNET_TEST_KEY = "ZmDfcTF7_60GrrY167zsiPd67pEvs0ouEkuFfKjGmS0="


def _fresh_settings(database: Path) -> Settings:
    """Settings matching a new checkout: empty database, seeding enabled."""
    return Settings(
        database_url=f"sqlite:///{database.as_posix()}",
        admin_token="test-admin-token",
        phone_enc_key=FERNET_TEST_KEY,
        phone_hash_key="test-phone-hash-key",
        webhook_secret="test-webhook-secret",
        messenger_provider="mock",
        worker_enabled=False,
        tick_seconds=0.01,
        demo_mode=True,
        seed_defaults=True,
        log_level="WARNING",
    )


def test_AC_SYS_007_fresh_startup_smoke_test_runs_lifespan(
    tmp_path: Path, clock: FakeClock
) -> None:
    """Given a fresh database, when the app starts, then healthz, docs and seeding work."""
    settings = _fresh_settings(tmp_path / "smoke.db")
    app = create_app(settings=settings, clock=clock)
    with TestClient(app, headers={"X-Admin-Token": settings.admin_token}) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["worker"] == "disabled"
        assert client.get("/docs").status_code == 200
        assert "/healthz" in client.get("/openapi.json").json()["paths"]
        # The lifespan seeds the empty database, the same step seed.py performs.
        assert len(client.get("/api/v1/keywords").json()) == 25
        assert len(client.get("/api/v1/templates").json()) == 1

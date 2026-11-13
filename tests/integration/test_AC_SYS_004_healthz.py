"""Health check tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import APP_VERSION
from app.core.clock import FakeClock
from app.core.config import Settings
from app.main import create_app


def test_AC_SYS_004_healthz_reports_db_worker_and_version(client: TestClient) -> None:
    """Given a healthy app, when /healthz is called, then DB, worker and version are reported."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db": "ok",
        "worker": "disabled",
        "version": APP_VERSION,
    }


def test_AC_SYS_004_healthz_returns_503_when_db_unavailable(
    settings: Settings, clock: FakeClock
) -> None:
    """Given an unavailable database, when /healthz is called, then 503 is returned."""

    class BrokenSession:
        def __enter__(self) -> object:
            raise RuntimeError("database unavailable")

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

    app = create_app(settings=settings, clock=clock)

    def broken_factory() -> BrokenSession:
        return BrokenSession()

    app.state.session_factory = broken_factory
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["db"] == "error"

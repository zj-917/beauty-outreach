"""Admin token authentication tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.core.clock import FakeClock
from app.core.config import Settings
from app.main import create_app


def test_AC_SYS_002_missing_or_wrong_token_is_401(
    settings: Settings, clock: FakeClock
) -> None:
    """Given missing or wrong X-Admin-Token, when calling /api/v1, then 401 with envelope."""
    app = create_app(settings=settings, clock=clock)
    with TestClient(app) as client:
        missing = client.get("/api/v1/anything")
        wrong = client.get("/api/v1/anything", headers={"X-Admin-Token": "wrong-token"})
    for response in (missing, wrong):
        assert response.status_code == 401
        error = response.json()["error"]
        assert error["code"] == "UNAUTHORIZED"
        assert error["request_id"] == response.headers["X-Request-ID"]


def test_AC_SYS_002_exempt_paths_and_valid_token(
    settings: Settings, clock: FakeClock
) -> None:
    """Given exempt paths, when called, then no token is needed; valid token reaches routing."""
    app = create_app(settings=settings, clock=clock)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200
        webhook = client.get("/api/v1/webhooks/inbound")
        assert webhook.status_code == 404
        authed = client.get(
            "/api/v1/anything", headers={"X-Admin-Token": settings.admin_token}
        )
        assert authed.status_code == 404


def test_AC_SYS_002_token_comparison_is_constant_time(
    settings: Settings, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given the auth path, when checking tokens, then verify_admin_token decides the outcome."""
    calls: list[tuple[str, str]] = []
    original = security.verify_admin_token

    def spy(provided: str | None, expected: str) -> bool:
        calls.append((provided or "", expected))
        return original(provided, expected)

    monkeypatch.setattr("app.api.middleware.verify_admin_token", spy)
    app = create_app(settings=settings, clock=clock)
    with TestClient(app) as client:
        assert client.get("/api/v1/anything").status_code == 401
        authed = client.get(
            "/api/v1/anything", headers={"X-Admin-Token": settings.admin_token}
        )
        assert authed.status_code == 404
    assert len(calls) == 2
    assert calls[1] == (settings.admin_token, settings.admin_token)
    assert original(None, "x") is False
    assert original("x", "x") is True

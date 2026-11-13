"""Unified error envelope tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app


def test_AC_SYS_001_unknown_route_uses_error_envelope(
    settings: Settings, clock: FakeClock
) -> None:
    """Given an unknown API route, when requested, then the 404 uses the unified envelope."""
    app = create_app(settings=settings, clock=clock)
    with TestClient(app, headers={"X-Admin-Token": settings.admin_token}) as client:
        response = client.get("/api/v1/unknown")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert isinstance(error["details"], dict)


def test_AC_SYS_001_unexpected_error_hides_details(
    settings: Settings, clock: FakeClock
) -> None:
    """Given an unhandled exception, when requested, then 500 carries no stack or message."""
    app = create_app(settings=settings, clock=clock)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("sensitive stack detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert "sensitive stack detail" not in response.text
    assert "Traceback" not in response.text
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_AC_SYS_001_validation_error_lists_fields(
    settings: Settings, clock: FakeClock
) -> None:
    """Given invalid query input, when requested, then 422 lists the offending fields."""
    app = create_app(settings=settings, clock=clock)

    @app.get("/requires-int")
    def requires_int(x: int) -> dict[str, int]:
        return {"x": x}

    with TestClient(app) as client:
        response = client.get("/requires-int?x=not-a-number")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["errors"]
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_AC_SYS_001_business_error_keeps_code_and_status(
    settings: Settings, clock: FakeClock
) -> None:
    """Given a business error, when raised, then its code, status and details are returned."""
    app = create_app(settings=settings, clock=clock)

    @app.get("/business-error")
    def business_error() -> None:
        raise AppError("CONFLICT", "already exists", details={"id": 1})

    with TestClient(app) as client:
        response = client.get("/business-error")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["details"] == {"id": 1}

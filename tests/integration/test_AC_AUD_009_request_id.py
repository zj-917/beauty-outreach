"""Request id propagation tests."""

from __future__ import annotations

import logging
import re

import pytest
from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.core.config import Settings
from app.main import create_app


def test_AC_AUD_009_request_id_is_echoed_in_header_and_error(
    settings: Settings, clock: FakeClock
) -> None:
    """Given an X-Request-ID, when the request fails, then header and envelope share it."""
    app = create_app(settings=settings, clock=clock)
    with TestClient(app) as client:
        response = client.get("/api/v1/missing", headers={"X-Request-ID": "req-123"})
    assert response.headers["X-Request-ID"] == "req-123"
    assert response.json()["error"]["request_id"] == "req-123"


def test_AC_AUD_009_invalid_request_id_is_replaced(
    settings: Settings, clock: FakeClock
) -> None:
    """Given an invalid or oversized X-Request-ID, when used, then a fresh id is generated."""
    app = create_app(settings=settings, clock=clock)
    invalid = "bad id with spaces"
    with TestClient(app) as client:
        response = client.get("/healthz", headers={"X-Request-ID": invalid})
    generated = response.headers["X-Request-ID"]
    assert generated != invalid
    assert re.fullmatch(r"[A-Za-z0-9._-]{1,64}", generated)


def test_AC_AUD_009_request_id_is_written_to_logs(
    settings: Settings, clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    """Given a request, when handled, then its request id appears in log records."""
    caplog.set_level(logging.INFO)
    app = create_app(settings=settings, clock=clock)
    with TestClient(app) as client:
        client.get("/healthz", headers={"X-Request-ID": "log-req-1"})
    messages = [record.getMessage() for record in caplog.records]
    assert any("request.start" in message and "log-req-1" in message for message in messages)

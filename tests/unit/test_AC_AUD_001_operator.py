"""X-Operator extraction tests."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from app.api.deps import get_operator
from app.core.errors import AppError


def _request(headers: dict[str, str]) -> Request:
    raw_headers = [(name.lower().encode(), value.encode()) for name, value in headers.items()]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw_headers})


def test_AC_AUD_001_operator_defaults_to_admin() -> None:
    """Given no X-Operator header, when resolved, then the actor is admin."""
    assert get_operator(_request({})) == "admin"


def test_AC_AUD_001_operator_uses_valid_header() -> None:
    """Given a valid X-Operator, when resolved, then it is returned."""
    assert get_operator(_request({"X-Operator": "alice.ops@example"})) == "alice.ops@example"


def test_AC_AUD_001_operator_rejects_invalid_value() -> None:
    """Given an invalid X-Operator, when resolved, then 422 VALIDATION_ERROR is raised."""
    with pytest.raises(AppError) as exc_info:
        get_operator(_request({"X-Operator": "bad operator"}))
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.status_code == 422

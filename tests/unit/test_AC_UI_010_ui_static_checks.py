"""Static safety checks for the admin script (AC-UI-002, AC-UI-010)."""

from __future__ import annotations

from pathlib import Path

APP_JS = (
    Path(__file__).resolve().parents[2] / "app" / "static" / "admin" / "app.js"
)


def test_AC_UI_010_no_innerhtml_assignment() -> None:
    """Given app.js, when scanned, then no HTML-injection sinks are used."""
    source = APP_JS.read_text(encoding="utf-8").lower()
    assert "innerhtml" not in source
    assert "outerhtml" not in source
    assert "document.write" not in source


def test_AC_UI_002_token_is_kept_in_session_storage_only() -> None:
    """Given app.js, when scanned, then the token is stored in sessionStorage."""
    source = APP_JS.read_text(encoding="utf-8")
    assert "sessionStorage.setItem" in source
    assert "localStorage" not in source

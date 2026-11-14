"""Static safety checks for the admin scripts (AC-UI-002, AC-UI-010)."""

from __future__ import annotations

from pathlib import Path

ADMIN_DIR = Path(__file__).resolve().parents[2] / "app" / "static" / "admin"

JS_FILES = [
    "labels.js",
    "core.js",
    "pages-overview.js",
    "pages-leads.js",
    "pages-tasks.js",
    "pages-system.js",
    "app.js",
]


def read_js() -> str:
    """Return all admin script sources concatenated in load order."""
    return "\n".join(
        (ADMIN_DIR / name).read_text(encoding="utf-8")
        for name in JS_FILES
        if (ADMIN_DIR / name).exists()
    )


def test_AC_UI_010_no_innerhtml_assignment() -> None:
    """Given the admin scripts, when scanned, then no HTML-injection sinks are used."""
    source = read_js().lower()
    assert "innerhtml" not in source
    assert "outerhtml" not in source
    assert "document.write" not in source


def test_AC_UI_002_token_is_kept_in_session_storage_only() -> None:
    """Given the admin scripts, when scanned, then the token is stored in sessionStorage."""
    source = read_js()
    assert "sessionStorage.setItem" in source
    assert "localStorage" not in source

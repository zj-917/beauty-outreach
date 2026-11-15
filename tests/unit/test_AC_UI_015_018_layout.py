"""Static layout checks for the admin UI v2.0 (AC-UI-015 ~ AC-UI-018)."""

from __future__ import annotations

import re
from pathlib import Path

ADMIN_DIR = Path(__file__).resolve().parents[2] / "app" / "static" / "admin"
APP_DIR = ADMIN_DIR / "app"
INDEX_HTML = ADMIN_DIR / "index.html"
STYLE_CSS = ADMIN_DIR / "style.css"


def read_js() -> str:
    """Return every admin ES module concatenated in path order."""
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(APP_DIR.rglob("*.js"))
    )


def read_html() -> str:
    """Return the admin page source."""
    return INDEX_HTML.read_text(encoding="utf-8")


def read_css() -> str:
    """Return the admin stylesheet."""
    return STYLE_CSS.read_text(encoding="utf-8")


def test_AC_UI_015_batch_report_tabs() -> None:
    """Given an import batch, then its report is a drawer with category tabs."""
    source = read_js()
    assert "renderBatchCard" in source, "batch card renderer is missing"
    assert "loadBatchHistory" in source, "batch history loader is missing"
    assert "lead-batches" in source, "batch history endpoint is missing"
    assert '["duplicates", "invalid", "warnings"]' in source, (
        "default tab priority (duplicates, invalid, warnings) is missing"
    )
    for label in ["成功", "重复", "无效", "警告"]:
        assert label in source, f"batch tab label missing: {label}"
    assert "BATCH_ERROR_CATEGORIES" in source, "error categories are missing"


def test_AC_UI_016_task_funnel_and_grouped_items() -> None:
    """Given task detail, then a funnel drills down into grouped item tabs."""
    source = read_js()
    assert "funnel(" in source, "task funnel renderer is missing"
    for label in ["目标", "跳过", "已发送", "送达", "已读", "失败"]:
        assert label in source, f"funnel segment label missing: {label}"
    assert "skip_reasons" in source, "skip reason distribution is missing"
    for group in ['"all"', '"success"', '"failed"', '"skipped"']:
        assert group in source, f"item group missing: {group}"
    assert "item-tabs" in source, "grouped item tabs are missing"


def test_AC_UI_017_pool_view_summary() -> None:
    """Given the pool view, then a KPI summary row precedes the table."""
    source = read_js()
    assert "renderPool" in source, "pool view renderer is missing"
    assert "readiness_counts" in source, "readiness counts are not surfaced"
    assert "可发送" in source, "reachable KPI is missing"
    assert '"/pool"' in source, "pool endpoint is missing"
    assert "用户池名单" in source, "pool view tab is missing"


def test_AC_UI_018_design_tokens_and_page_consistency() -> None:
    """Given any page, then status colors come from tokens and guides exist."""
    css = read_css()
    assert ":root" in css, "design token block is missing"
    for token in ["--ok", "--warn", "--danger", "--info", "--accent"]:
        assert re.search(rf"^\s*{re.escape(token)}\s*:", css, re.M), (
            f"status token missing: {token}"
        )
    for tone in [".tone-ok", ".tone-info", ".tone-warn", ".tone-danger"]:
        assert tone in css, f"semantic tone class missing: {tone}"
    assert ".status-banner" in css, "task status banner style is missing"
    assert "var(--tone" in css, "status colors must come from tone tokens"
    source = read_js()
    for module in [
        "dashboard.js",
        "leads.js",
        "tasks.js",
        "task-detail.js",
        "compliance.js",
        "records.js",
        "settings.js",
    ]:
        module_source = (APP_DIR / "pages" / module).read_text(encoding="utf-8")
        assert "guide(" in module_source, f"{module} has no guide block"
    assert "SETTING_GROUPS" in source, "settings groups are missing"
    assert "settings-groups" in source, "settings group layout is missing"
    assert "@import" not in css, "external stylesheets are not allowed"
    assert "http" not in read_html().lower(), "the page must not load external URLs"

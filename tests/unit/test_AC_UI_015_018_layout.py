"""Static layout checks for the admin UI v1.2 (AC-UI-015 ~ AC-UI-018).

These tests read the admin page sources as text so the checks stay
deterministic and require no browser.
"""

from __future__ import annotations

import re
from pathlib import Path

ADMIN_DIR = Path(__file__).resolve().parents[2] / "app" / "static" / "admin"
INDEX_HTML = ADMIN_DIR / "index.html"
STYLE_CSS = ADMIN_DIR / "style.css"


def read_js() -> str:
    """Return all admin script sources concatenated in load order."""
    order = [
        "labels.js",
        "core.js",
        "pages-overview.js",
        "pages-leads.js",
        "pages-tasks.js",
        "pages-system.js",
        "app.js",
    ]
    return "\n".join(
        (ADMIN_DIR / name).read_text(encoding="utf-8")
        for name in order
        if (ADMIN_DIR / name).exists()
    )


def read_html() -> str:
    """Return the admin page source."""
    return INDEX_HTML.read_text(encoding="utf-8")


def read_css() -> str:
    """Return the admin stylesheet."""
    return STYLE_CSS.read_text(encoding="utf-8")


def test_AC_UI_015_batch_report_tabs() -> None:
    """Given an import batch, then its report is a card with category tabs."""
    source = read_js()
    assert "renderBatchCard" in source, "batch card renderer is missing"
    assert "loadBatchHistory" in source, "batch history list is missing"
    assert "lead-batches" in source, "batch history endpoint is missing"
    # 默认停在第一个非零异常标签：优先级 固定为 重复 → 无效 → 警告
    assert '["duplicates", "invalid", "warnings"]' in source, (
        "default tab priority (duplicates, invalid, warnings) is missing"
    )
    for label in ["成功", "重复", "无效", "警告"]:
        assert label in source, f"batch tab label missing: {label}"
    # 批次错误必须按类别分组展示，且行内给中文原因与说明
    assert "BATCH_ERROR_CATEGORIES" in source, "error categories are missing"
    assert "batch_id" in source, "successful rows must be listed via batch_id query"


def test_AC_UI_016_task_funnel_and_grouped_items() -> None:
    """Given task detail, then a funnel drills down into grouped item tabs."""
    source = read_js()
    assert "renderTaskFunnel" in source, "task funnel renderer is missing"
    for label in ["目标", "跳过", "已发送", "送达", "已读", "失败"]:
        assert label in source, f"funnel segment label missing: {label}"
    assert "itemGroup" in source, "item group state is missing"
    assert "skip_reasons" in source, "skip reason distribution is missing"
    # 明细分组标签页
    for group in ['"all"', '"success"', '"failed"', '"skipped"']:
        assert group in source, f"item group missing: {group}"


def test_AC_UI_017_pool_view_summary() -> None:
    """Given the pool sub-tab, then a KPI summary row precedes the table."""
    html = read_html()
    for marker in [
        'id="leads-tab-pool"',
        'id="leads-pool-view"',
        'id="pool-kpi"',
        'id="pool-table"',
        'id="pool-view"',
    ]:
        assert marker in html, f"pool view marker missing: {marker}"
    source = read_js()
    assert "loadPoolView" in source, "pool view loader is missing"
    assert "可触达" in source, "reachable KPI is missing"
    assert "readiness_counts" in source, "readiness counts are not surfaced"
    assert "地区分布" in source, "region distribution is missing"


def test_AC_UI_018_design_tokens_and_accordion() -> None:
    """Given any page, then status colors come from tokens and config folds."""
    css = read_css()
    assert ":root" in css, "design token block is missing"
    for token in ["--ok", "--warn", "--danger", "--info"]:
        assert re.search(rf"^\s*{re.escape(token)}\s*:", css, re.M), (
            f"status token missing: {token}"
        )
    # §3.2：进行中 = 蓝，运行中徽章必须使用 info token
    assert re.search(r"\.badge\.RUNNING\s*\{[^}]*var\(--info\)", css, re.S), (
        "RUNNING badge must use the info (blue) token"
    )
    html = read_html()
    assert html.count('class="config-group"') >= 4, (
        "config page must use four collapsible groups"
    )
    assert '<details class="config-group" open>' in html, (
        "keyword group must be expanded by default"
    )
    # 线索页子页签
    assert 'id="leads-tab-import"' in html, "leads import sub-tab is missing"

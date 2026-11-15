"""Static layout checks for the record page filter rows (AC-UI-009)."""

from __future__ import annotations

import re
from pathlib import Path

ADMIN_DIR = Path(__file__).resolve().parents[2] / "app" / "static" / "admin"
APP_DIR = ADMIN_DIR / "app"
STYLE_CSS = ADMIN_DIR / "style.css"


def read_records() -> str:
    """Return the records page module source."""
    return (APP_DIR / "pages" / "records.js").read_text(encoding="utf-8")


def read_css() -> str:
    """Return the admin stylesheet."""
    return STYLE_CSS.read_text(encoding="utf-8")


def rule(css: str, selector: str) -> str:
    """Return the declaration block of the first rule with that exact selector."""
    match = re.search(rf"(?m)^\s*{re.escape(selector)}\s*\{{([^}}]*)\}}", css)
    assert match, f"css rule missing: {selector}"
    return match.group(1)


def test_AC_UI_009_filter_fields_have_width_caps() -> None:
    """Given the audit and send-log filter rows, then fields never stretch full width."""
    css = read_css()
    grid = rule(css, ".filter-grid")
    assert "display: flex" in grid, "filter rows must lay fields out in a flow"
    assert "flex-wrap: wrap" in grid, "filter rows must wrap instead of overflowing"
    base = rule(css, ".filter-grid > .field")
    assert "max-width: 240px" in base, "short text filters must cap at 240px"
    wide = rule(css, ".filter-grid > .field-wide")
    assert "max-width: 360px" in wide, "enum selects must cap at 360px"
    assert "grid-template-columns" not in grid, "filter rows are flex, not grid"


def test_AC_UI_009_filter_actions_align_right() -> None:
    """Given the filter row, then 查询 / 清空筛选 / 验证哈希链 sit at the right edge."""
    actions = rule(read_css(), ".filter-actions")
    assert "display: flex" in actions
    assert "margin-left: auto" in actions, "action buttons must align to the right edge"


def test_AC_UI_009_records_use_shared_filter_row() -> None:
    """Given both log tabs, then they reuse the shared filter row and mark wide selects."""
    source = read_records()
    assert source.count('class: "filter-grid"') == 2, "audit and send rows are missing"
    assert source.count('class: "filter-actions"') == 2, "both tabs need an action area"
    for call in [
        'wideField("动作", action)',
        'wideField("对象类型", entityType)',
        'wideField("阶段", phase)',
        'wideField("结果", outcome)',
        'wideField("原因代码", reason)',
    ]:
        assert call in source, f"select field is not marked wide: {call}"
    assert 'field-wide' in source, "the wide field modifier class is missing"


def test_AC_UI_009_filter_row_is_responsive() -> None:
    """Given narrow screens, then fields reflow to two columns and then one."""
    css = read_css()
    assert ".form-grid, .filter-grid" not in css, (
        "the old grid override for .filter-grid must be removed"
    )
    narrow = re.search(r"@media \(max-width: 1020px\) \{(.*?)\n\}", css, re.S)
    assert narrow, "1020px breakpoint is missing"
    assert "flex: 1 1 calc(50% - 7px)" in narrow.group(1), (
        "under 1020px the filter fields must go two per row"
    )
    tiny = re.search(r"@media \(max-width: 560px\) \{(.*?)\n\}", css, re.S)
    assert tiny, "560px breakpoint is missing"
    assert "flex: 1 1 100%" in tiny.group(1), "under 560px the filter fields stack"

"""Static checks for the lead list table in the admin UI (AC-UI-003)."""

from __future__ import annotations

from pathlib import Path

ADMIN_APP = Path(__file__).resolve().parents[2] / "app" / "static" / "admin" / "app"
LEADS_JS = ADMIN_APP / "pages" / "leads.js"


def test_AC_UI_003_lead_table_type_filter_and_page_size() -> None:
    """Given the lead workspace, then leads are shown as a filtered, paged table."""
    source = LEADS_JS.read_text(encoding="utf-8")
    assert "线索类型：" in source, "type filter label is missing"
    for status in ["NEW", "PENDING_REVIEW", "APPROVED", "REJECTED", "DISCARDED"]:
        assert f'"{status}"' in source, f"type filter option missing: {status}"
    assert "PAGE_SIZES = [10, 20, 50, 100]" in source, "page size options are missing"
    assert "每页 ${sizeOption} 条" in source, "page size labels are missing"
    assert "status: state.board.status" in source, "status filter is not sent to the API"
    assert "page_size: state.board.size" in source, "page size is not sent to the API"


def test_AC_UI_003_lead_table_rows_and_review_actions() -> None:
    """Given a lead row, then score, reasons, masked phone and review actions are present."""
    source = LEADS_JS.read_text(encoding="utf-8")
    assert '["线索", "状态", "评分", "地区 / 语言", "号码", "操作"]' in source
    assert "phone_masked" in source
    assert "reasonChips(lead.score_reasons" in source
    assert '"通过"' in source and '"拒绝"' in source
    assert "共 ${total} 条" in source, "pager total is missing"


def test_AC_UI_003_lead_table_replaces_card_columns() -> None:
    """Given the redesigned list, then the old multi-column card board is gone."""
    source = LEADS_JS.read_text(encoding="utf-8")
    assert "board-column" not in source
    assert "lead-card" not in source

"""Admin static page serving (AC-UI-001)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_AC_UI_001_admin_page_and_assets_are_served_without_external_resources(
    anon_client: TestClient,
) -> None:
    """Given the app, when /admin/ is opened, then the page and local assets load."""
    page = anon_client.get("/admin/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "app.js" in page.text
    assert "style.css" in page.text
    for label in ("概览", "线索", "任务", "合规", "配置", "日志"):
        assert label in page.text

    for name, content_type in (
        ("labels.js", "javascript"),
        ("core.js", "javascript"),
        ("pages-overview.js", "javascript"),
        ("pages-leads.js", "javascript"),
        ("pages-tasks.js", "javascript"),
        ("pages-system.js", "javascript"),
        ("app.js", "javascript"),
        ("style.css", "text/css"),
    ):
        asset = anon_client.get(f"/admin/{name}")
        assert asset.status_code == 200
        assert content_type in asset.headers["content-type"]
        assert "http://" not in asset.text
        assert "https://" not in asset.text

    assert "http://" not in page.text
    assert "https://" not in page.text


def test_AC_UI_001_admin_without_slash_redirects(anon_client: TestClient) -> None:
    """Given /admin without the trailing slash, when requested, then it redirects."""
    response = anon_client.get("/admin", follow_redirects=False)
    assert response.status_code in (301, 307)
    assert response.headers["location"].endswith("/admin/")

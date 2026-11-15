"""Admin static page serving (AC-UI-001)."""

from __future__ import annotations

from fastapi.testclient import TestClient

ASSETS = [
    "app/main.js",
    "app/api.js",
    "app/store.js",
    "app/router.js",
    "app/labels.js",
    "app/ui.js",
    "app/charts.js",
    "app/wizard.js",
    "app/pages/dashboard.js",
    "app/pages/leads.js",
    "app/pages/tasks.js",
    "app/pages/task-detail.js",
    "app/pages/compliance.js",
    "app/pages/records.js",
    "app/pages/settings.js",
    "style.css",
]


def test_AC_UI_001_admin_page_and_assets_are_served_without_external_resources(
    anon_client: TestClient,
) -> None:
    """Given the app, when /admin/ is opened, then the page and local assets load."""
    page = anon_client.get("/admin/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "app/main.js" in page.text
    assert "style.css" in page.text
    for label in ("Beauty Outreach", "触达指挥台", "驾驶舱", "搜索 / 跳转"):
        assert label in page.text

    main = anon_client.get("/admin/app/main.js")
    assert main.status_code == 200
    for label in ("驾驶舱", "线索", "任务", "合规", "记录", "配置"):
        assert label in main.text

    for name in ASSETS:
        asset = anon_client.get(f"/admin/{name}")
        assert asset.status_code == 200, name
        content_type = "text/css" if name.endswith(".css") else "javascript"
        assert content_type in asset.headers["content-type"]
        text = asset.text.replace("http://www.w3.org/2000/svg", "")
        assert "http://" not in text, name
        assert "https://" not in text, name

    text = page.text
    assert "http://" not in text
    assert "https://" not in text


def test_AC_UI_001_admin_without_slash_redirects(anon_client: TestClient) -> None:
    """Given /admin without the trailing slash, when requested, then it redirects."""
    response = anon_client.get("/admin", follow_redirects=False)
    assert response.status_code in (301, 307)
    assert response.headers["location"].endswith("/admin/")

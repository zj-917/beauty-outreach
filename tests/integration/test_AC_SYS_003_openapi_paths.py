"""OpenAPI availability tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.core.config import Settings
from app.main import create_app


def test_AC_SYS_003_docs_and_openapi_available(settings: Settings, clock: FakeClock) -> None:
    """Given the app, when /docs and /openapi.json are requested, then both are served."""
    app = create_app(settings=settings, clock=clock)
    with TestClient(app) as client:
        docs = client.get("/docs")
        spec = client.get("/openapi.json")
    assert docs.status_code == 200
    assert spec.status_code == 200
    document = spec.json()
    assert document["info"]["title"] == "Beauty Outreach"
    assert "/healthz" in document["paths"]

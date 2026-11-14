"""E2E-10: a failing audit write leaves no business rows behind."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuditLog, Lead, LeadBatch


def test_e2e_10_audit_failure_rolls_back_the_whole_import(
    anon_client: TestClient,
    app: FastAPI,
    db: Engine,
    settings: Settings,
    monkeypatch,
) -> None:
    """Covers: AC-AUD-002, AC-AUD-005.

    Given the audit writer raises mid-import, when the API responds, then the
    batch, its leads and any audit rows are all rolled back together.
    """

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(app.state.audit_service, "record", boom)

    response = anon_client.post(
        "/api/v1/lead-batches/import",
        json={"source": "mock"},
        headers={"X-Admin-Token": settings.admin_token},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "audit write failed" not in response.text

    with Session(db) as session:
        assert session.scalar(select(func.count()).select_from(LeadBatch)) == 0
        assert session.scalar(select(func.count()).select_from(Lead)) == 0
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 0

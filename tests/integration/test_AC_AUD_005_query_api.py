"""Audit query and verification API tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.clock import FakeClock
from app.services.audit_service import AuditService


def _seed(app: FastAPI, clock: FakeClock) -> None:
    service = AuditService(clock)
    session = app.state.session_factory()
    try:
        for index in range(5):
            service.record(
                session,
                actor="alice" if index < 3 else "bob",
                action="LEAD_IMPORTED" if index < 2 else "LEAD_REVIEWED",
                entity_type="lead",
                entity_id=str(index + 1),
            )
            clock.advance(60)
        session.commit()
    finally:
        session.close()


def test_AC_AUD_005_list_is_newest_first_and_paginated(
    app: FastAPI, clock: FakeClock, client: TestClient
) -> None:
    """Given five records, when listed, then order, timestamps and paging are correct."""
    _seed(app, clock)
    body = client.get("/api/v1/audit-logs").json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert [item["entity_id"] for item in body["items"]] == ["5", "4", "3", "2", "1"]
    assert all(item["ts"].endswith("Z") for item in body["items"])
    assert body["items"][0]["ts"] == "2026-11-14T09:04:00Z"

    page_two = client.get(
        "/api/v1/audit-logs", params={"page": 2, "page_size": 2}
    ).json()
    assert page_two["total"] == 5
    assert [item["entity_id"] for item in page_two["items"]] == ["3", "2"]


def test_AC_AUD_005_filters_by_all_supported_fields(
    app: FastAPI, clock: FakeClock, client: TestClient
) -> None:
    """Given five records, when filtered, then actor/action/entity/time filters apply."""
    _seed(app, clock)
    assert client.get("/api/v1/audit-logs", params={"actor": "alice"}).json()["total"] == 3
    assert (
        client.get("/api/v1/audit-logs", params={"action": "LEAD_REVIEWED"}).json()["total"]
        == 3
    )
    assert (
        client.get("/api/v1/audit-logs", params={"entity_type": "lead"}).json()["total"] == 5
    )
    entity = client.get("/api/v1/audit-logs", params={"entity_id": "3"}).json()
    assert entity["total"] == 1
    window = client.get(
        "/api/v1/audit-logs",
        params={"from": "2026-11-14T09:02:00Z", "to": "2026-11-14T09:03:00Z"},
    ).json()
    assert [item["entity_id"] for item in window["items"]] == ["4", "3"]


def test_AC_AUD_004_verify_endpoint_reports_ok_and_tampering(
    app: FastAPI, clock: FakeClock, client: TestClient
) -> None:
    """Given a valid chain then a tampered row, when verified via API, then results match."""
    _seed(app, clock)
    assert client.get("/api/v1/audit-logs/verify").json() == {"ok": True, "count": 5}
    with app.state.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER audit_log_no_update")
        connection.exec_driver_sql("UPDATE audit_log SET actor = 'mallory' WHERE id = 2")
    assert client.get("/api/v1/audit-logs/verify").json() == {
        "ok": False,
        "first_broken_id": 2,
    }

"""E2E-5: after the full flow, no output surface holds a complete phone number."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import Lead
from app.providers.messenger.mock import MockMessenger


def _database_files(database_url: str) -> list[Path]:
    path = Path(database_url.removeprefix("sqlite:///"))
    return [
        candidate
        for candidate in (
            path,
            path.with_name(path.name + "-wal"),
            path.with_name(path.name + "-shm"),
        )
        if candidate.exists()
    ]


def test_e2e_05_no_full_phone_leaks_from_any_surface(
    client: TestClient,
    app: FastAPI,
    db: Engine,
    clock: FakeClock,
    template_id: int,
    messenger: MockMessenger,
    make_worker: Callable[..., object],
    run_until_complete: Callable[..., str],
    caplog,
) -> None:
    """Covers: AC-AUD-007, AC-AUD-008, AC-LEAD-008.

    Given the whole import → screen → send flow, when API responses, logs,
    audit_log, send_log, last_error_message and the database files are scanned,
    then none of them contains a complete phone number.
    """
    caplog.set_level(logging.DEBUG)

    client.post("/api/v1/lead-batches/import", json={"source": "mock"})
    client.post("/api/v1/leads/screen", json={})
    campaign = client.post(
        "/api/v1/campaigns",
        json={"name": "e2e leak scan", "template_id": template_id, "selection": {}},
    ).json()
    campaign_id = campaign["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
    worker = make_worker(messenger, receipts=True)
    assert run_until_complete(worker, campaign_id) == "COMPLETED"
    clock.advance(10)
    worker.tick()
    client.post("/demo/flush-receipts")

    with Session(db) as session:
        encrypted = session.scalars(select(Lead.phone_enc)).all()
    phones = [
        app.state.phone_cipher.decrypt(value) for value in encrypted if value is not None
    ]
    assert phones, "the flow must have imported phone numbers to scan for"

    surfaces: dict[str, str] = {}
    paths = [
        path
        for path, operations in client.get("/openapi.json").json()["paths"].items()
        if "get" in operations
        and "{" not in path
        and path.startswith(("/api/v1", "/healthz"))
    ]
    paths += [
        f"/api/v1/campaigns/{campaign_id}",
        f"/api/v1/campaigns/{campaign_id}/stats",
        f"/api/v1/campaigns/{campaign_id}/timeline",
        f"/api/v1/campaigns/{campaign_id}/items?page_size=100",
        "/api/v1/send-logs?page_size=100",
        "/api/v1/audit-logs?page_size=100",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        surfaces[f"api {path}"] = response.text

    surfaces["logs"] = caplog.text
    with app.state.engine.connect() as connection:
        for table in (
            "audit_log",
            "send_log",
            "task_item",
            "lead",
            "suppression",
            "contact_consent",
        ):
            rows = connection.exec_driver_sql(f"SELECT * FROM {table}").fetchall()
            surfaces[f"table {table}"] = json.dumps([list(row) for row in rows], default=str)
    for path in _database_files(app.state.settings.database_url):
        surfaces[f"file {path.name}"] = path.read_bytes().decode("latin-1")

    for phone in phones:
        for variant in {phone, phone.lstrip("+")}:
            for surface, text in surfaces.items():
                assert variant not in text, f"{variant} leaked into {surface}"

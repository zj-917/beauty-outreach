"""Graceful shutdown stops the worker thread within five seconds (AC-SYS-010)."""

from __future__ import annotations

import contextlib
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.clock import FakeClock
from app.core.config import Settings
from app.domain.masking import mask_phone
from app.main import create_app
from app.models import CampaignTask, ContactConsent, Lead, LeadBatch, TaskItem
from app.providers.messenger.base import Receipt, ResultKind, SendResult
from app.services.seed_service import seed_defaults

FERNET_TEST_KEY = "ZmDfcTF7_60GrrY167zsiPd67pEvs0ouEkuFfKjGmS0="
LEAD_COUNT = 8


class _SlowMessenger:
    """Provider double that blocks each call so the tick spans many seconds."""

    name = "slow"

    def __init__(self) -> None:
        self.started = threading.Event()
        self.calls = 0

    def send(self, request) -> SendResult:
        self.calls += 1
        self.started.set()
        threading.Event().wait(1.0)
        return SendResult(kind=ResultKind.ACCEPTED, provider_message_id=f"slow-{self.calls}")

    def poll_receipts(self) -> list[Receipt]:
        return []


def _settings(database: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{database.as_posix()}",
        admin_token="test-admin-token",
        phone_enc_key=FERNET_TEST_KEY,
        phone_hash_key="test-phone-hash-key",
        webhook_secret="test-webhook-secret",
        messenger_provider="mock",
        worker_enabled=True,
        tick_seconds=0.05,
        demo_mode=False,
        seed_defaults=False,
        log_level="WARNING",
    )


def _insert_leads(app: FastAPI, clock: FakeClock) -> None:
    """Add one batch with GRANTED targets so a campaign has work to do."""
    cipher = app.state.phone_cipher
    now = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
    with app.state.session_factory() as session:
        seed_defaults(session, clock, cipher=cipher)
        batch = LeadBatch(
            source_type="MOCK",
            source_name="shutdown",
            total_rows=LEAD_COUNT,
            imported=LEAD_COUNT,
            duplicates=0,
            invalid=0,
            warnings=0,
            errors=[],
            created_by="test",
            created_at=now,
        )
        session.add(batch)
        session.flush()
        for index in range(LEAD_COUNT):
            phone = f"+15555550{310 + index}"
            session.add(
                Lead(
                    batch_id=batch.id,
                    username=f"shutdown_{index}",
                    display_name=f"shutdown_{index}",
                    bio="beauty skincare enthusiast",
                    region="US",
                    language="en",
                    source_url=None,
                    phone_enc=cipher.encrypt(phone),
                    phone_hash=cipher.hash_phone(phone),
                    phone_masked=mask_phone(phone),
                    status="APPROVED",
                    score=80,
                    score_reasons=[],
                    top_keyword="serum",
                    decision_source="AUTO",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                ContactConsent(
                    phone_hash=cipher.hash_phone(phone),
                    phone_masked=mask_phone(phone),
                    status="GRANTED",
                    source="test",
                    evidence_ref="test-evidence",
                    granted_at=now,
                    updated_at=now,
                    updated_by="test",
                )
            )
        session.commit()


def test_AC_SYS_010_shutdown_stops_the_worker_within_five_seconds(
    tmp_path: Path, clock: FakeClock
) -> None:
    """Given a worker processing a long tick, when the app shuts down, then it stops."""
    messenger = _SlowMessenger()
    app = create_app(
        settings=_settings(tmp_path / "shutdown.db"), clock=clock, messenger=messenger
    )
    with contextlib.ExitStack() as stack:
        client = stack.enter_context(
            TestClient(app, headers={"X-Admin-Token": "test-admin-token"})
        )
        _insert_leads(app, clock)
        template_id = next(
            item["id"]
            for item in client.get("/api/v1/templates").json()
            if item["name"] == "greeting"
        )
        campaign = client.post(
            "/api/v1/campaigns",
            json={"name": "shutdown", "template_id": template_id, "selection": {}},
        ).json()
        campaign_id = campaign["id"]
        assert campaign["total_items"] == LEAD_COUNT
        assert client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200
        assert messenger.started.wait(5), "the worker never started sending"

        shutdown_started = time.monotonic()
        stack.close()
        elapsed = time.monotonic() - shutdown_started

    thread = app.state.worker_thread
    assert thread is not None
    assert not thread.is_alive()
    assert app.state.worker_status == "stopped"
    assert elapsed < 5

    with app.state.session_factory() as session:
        rows = session.scalars(select(TaskItem)).all()
        statuses = [row.status for row in rows]
        assert "SENDING" not in statuses
        assert statuses.count("SENT") >= 1
        for row in rows:
            if row.status == "PENDING":
                assert row.locked_at is not None
        task = session.get(CampaignTask, campaign_id)
        assert task is not None
        assert task.status == "RUNNING"

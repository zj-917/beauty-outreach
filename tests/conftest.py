"""Shared deterministic test fixtures."""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.core.config import Settings
from app.core.db import build_engine
from app.domain.masking import mask_phone
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.main import create_app
from app.models import ContactConsent, Lead, LeadBatch, create_schema
from app.providers.messenger.mock import MockMessenger

FERNET_TEST_KEY = "ZmDfcTF7_60GrrY167zsiPd67pEvs0ouEkuFfKjGmS0="


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block outbound sockets, DNS lookups and datagrams for every test."""
    allowed = {"127.0.0.1", "::1", "localhost", "testserver"}

    def check_host(host: object) -> None:
        if isinstance(host, str) and host in allowed:
            return
        raise RuntimeError("network access is disabled in tests")

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self: socket.socket, address: object) -> None:
        check_host(address[0] if isinstance(address, tuple) else address)
        original_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: object) -> int:
        check_host(address[0] if isinstance(address, tuple) else address)
        return original_connect_ex(self, address)

    def guarded_sendto(self: socket.socket, data: bytes, *args: object) -> int:
        last = args[-1]
        check_host(last[0] if isinstance(last, tuple) else last)
        return original_sendto(self, data, *args)

    def guarded_getaddrinfo(host: object, *args: object, **kwargs: object):
        if host is not None:
            check_host(host)
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)


@pytest.fixture
def clock() -> FakeClock:
    """Fixed clock so time-dependent behaviour is deterministic."""
    return FakeClock(datetime(2026, 11, 14, 9, 0, tzinfo=UTC))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Test settings backed by a fresh temporary SQLite database."""
    database = (tmp_path / "test.db").as_posix()
    return Settings(
        database_url=f"sqlite:///{database}",
        admin_token="test-admin-token",
        phone_enc_key=FERNET_TEST_KEY,
        phone_hash_key="test-phone-hash-key",
        webhook_secret="test-webhook-secret",
        messenger_provider="mock",
        worker_enabled=False,
        tick_seconds=0.01,
        demo_mode=True,
        log_level="INFO",
    )


@pytest.fixture
def app(settings: Settings, clock: FakeClock) -> FastAPI:
    """Application instance with injected fake clock and disabled worker."""
    return create_app(settings=settings, clock=clock)


@pytest.fixture
def db(settings: Settings) -> Iterator[Engine]:
    """Fresh SQLite database with all tables, indexes and triggers."""
    engine = build_engine(settings)
    create_schema(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def client(app: FastAPI, settings: Settings) -> Iterator[TestClient]:
    """Authenticated test client."""
    with TestClient(app, headers={"X-Admin-Token": settings.admin_token}) as test_client:
        yield test_client


@pytest.fixture
def anon_client(app: FastAPI) -> Iterator[TestClient]:
    """Test client without default authentication headers."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def messenger(clock: FakeClock) -> MockMessenger:
    """Deterministic messenger shared by engine tests."""
    return MockMessenger(clock)


@pytest.fixture
def processor(app: FastAPI, clock: FakeClock, messenger: MockMessenger) -> Processor:
    """Processor wired to the test application's cipher and audit services."""
    return Processor(
        clock,
        app.state.phone_cipher,
        messenger,
        worker_id="worker-test",
        audit=app.state.audit_service,
    )


@pytest.fixture
def worker(app: FastAPI, clock: FakeClock, processor: Processor) -> Worker:
    """Worker driven manually through ``tick()`` in tests."""
    return Worker(
        app.state.session_factory, clock, processor, worker_id="worker-test"
    )


@pytest.fixture
def make_lead(
    db: Engine, app: FastAPI
) -> Callable[..., int]:
    """Insert an APPROVED lead (optionally with phone and consent) directly."""
    cipher = app.state.phone_cipher
    now = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)

    def _make(
        *,
        username: str,
        phone: str | None = None,
        consent: str | None = "GRANTED",
        status: str = "APPROVED",
        score: int = 80,
        top_keyword: str | None = "serum",
        display_name: str | None = None,
    ) -> int:
        with Session(db) as session:
            batch = session.scalar(select(LeadBatch).order_by(LeadBatch.id))
            if batch is None:
                batch = LeadBatch(
                    source_type="MOCK",
                    source_name="engine-tests",
                    total_rows=0,
                    imported=0,
                    duplicates=0,
                    invalid=0,
                    warnings=0,
                    errors=[],
                    created_by="test",
                    created_at=now,
                )
                session.add(batch)
                session.flush()
            phone_hash = cipher.hash_phone(phone) if phone else None
            phone_masked = mask_phone(phone) if phone else None
            lead = Lead(
                batch_id=batch.id,
                username=username,
                display_name=display_name or username,
                bio="beauty skincare enthusiast",
                region="US",
                language="en",
                source_url=None,
                phone_enc=cipher.encrypt(phone) if phone else None,
                phone_hash=phone_hash,
                phone_masked=phone_masked,
                status=status,
                score=score,
                score_reasons=[],
                top_keyword=top_keyword,
                decision_source="AUTO",
                created_at=now,
                updated_at=now,
            )
            session.add(lead)
            session.flush()
            if phone_hash is not None and consent is not None:
                session.add(
                    ContactConsent(
                        phone_hash=phone_hash,
                        phone_masked=phone_masked or "",
                        status=consent,
                        source="test",
                        evidence_ref="test-evidence",
                        granted_at=now if consent == "GRANTED" else None,
                        updated_at=now,
                        updated_by="test",
                    )
                )
            session.commit()
            return lead.id

    return _make

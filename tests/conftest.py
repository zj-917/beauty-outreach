"""Shared deterministic test fixtures."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.core.clock import FakeClock
from app.core.config import Settings
from app.core.db import build_engine
from app.main import create_app
from app.models import create_schema

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

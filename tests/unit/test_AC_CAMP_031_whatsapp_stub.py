"""WhatsAppCloudStub safety tests."""

from __future__ import annotations

import socket

import pytest

from app.providers.messenger import (
    ProviderNotEnabled,
    SendRequest,
    WhatsAppCloudStub,
)


def _request() -> SendRequest:
    return SendRequest(
        idempotency_key="stub-key",
        to_phone="+15555550100",
        body="Hi",
        template_name="greeting",
        language="en",
    )


@pytest.mark.parametrize("enabled", [False, True])
def test_AC_CAMP_031_stub_never_sends(enabled: bool) -> None:
    """Given the stub, when sent, then ProviderNotEnabled is raised and no receipts exist."""
    stub = WhatsAppCloudStub(enabled=enabled)

    with pytest.raises(ProviderNotEnabled):
        stub.send(_request())

    assert stub.poll_receipts() == []


def test_AC_CAMP_031_stub_makes_no_network_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given the stub, when sent, then no socket or DNS call is attempted."""
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)

    with pytest.raises(ProviderNotEnabled):
        WhatsAppCloudStub().send(_request())

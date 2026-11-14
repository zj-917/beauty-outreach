"""Shared Messenger contract tests."""

from __future__ import annotations

import pytest

from app.core.clock import FakeClock
from app.providers.messenger import (
    Messenger,
    MockMessenger,
    ProviderNotEnabled,
    ResultKind,
    SendRequest,
    SendResult,
    WhatsAppCloudStub,
)


@pytest.fixture(params=["mock", "stub"])
def messenger(request: pytest.FixtureRequest, clock: FakeClock) -> Messenger:
    """Return each Messenger implementation for the same contract suite."""
    if request.param == "mock":
        return MockMessenger(clock)
    return WhatsAppCloudStub()


def _request() -> SendRequest:
    return SendRequest(
        idempotency_key="contract-key",
        to_phone="+15555550000",
        body="Hi",
        template_name="greeting",
        language="en",
    )


def test_AC_CAMP_031_messenger_contract_shape(messenger: Messenger) -> None:
    """Given each implementation, then it exposes the Messenger protocol shape."""
    assert isinstance(messenger, Messenger)
    assert isinstance(messenger.name, str)
    assert messenger.name
    assert isinstance(messenger.poll_receipts(), list)


def test_AC_CAMP_031_messenger_send_contract(messenger: Messenger) -> None:
    """Given each implementation, then send returns a SendResult or raises ProviderNotEnabled."""
    if isinstance(messenger, WhatsAppCloudStub):
        with pytest.raises(ProviderNotEnabled):
            messenger.send(_request())
        return

    result = messenger.send(_request())

    assert isinstance(result, SendResult)
    assert isinstance(result.kind, ResultKind)
    assert result.provider_message_id is not None

"""Disabled stub for the real WhatsApp Cloud API."""

from __future__ import annotations

from app.providers.messenger.base import (
    ProviderNotEnabled,
    Receipt,
    SendRequest,
    SendResult,
)


class WhatsAppCloudStub:
    """Contract-compatible stub that never performs network I/O.

    A real integration needs business verification, an access token, approved
    templates and webhook verification. This prototype intentionally stops
    before any of those steps.
    """

    name = "whatsapp_cloud"

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def send(self, req: SendRequest) -> SendResult:
        """Always refuse; the real adapter is deliberately not implemented."""
        if self.enabled:
            raise ProviderNotEnabled("WhatsApp Cloud adapter is not implemented")
        raise ProviderNotEnabled("WhatsApp Cloud provider is not enabled")

    def poll_receipts(self) -> list[Receipt]:
        """The stub never produces receipts."""
        return []

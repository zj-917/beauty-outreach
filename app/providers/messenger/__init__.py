"""Messenger adapters: deterministic mock and disabled real-provider stub."""

from __future__ import annotations

from app.providers.messenger.base import (
    Messenger,
    ProviderNotEnabled,
    Receipt,
    ResultKind,
    SendRequest,
    SendResult,
)
from app.providers.messenger.mock import MockMessenger
from app.providers.messenger.whatsapp_cloud import WhatsAppCloudStub

__all__ = [
    "Messenger",
    "MockMessenger",
    "ProviderNotEnabled",
    "Receipt",
    "ResultKind",
    "SendRequest",
    "SendResult",
    "WhatsAppCloudStub",
]

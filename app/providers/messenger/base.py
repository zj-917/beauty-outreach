"""Messenger contract shared by mock and real adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ProviderNotEnabled(RuntimeError):
    """Raised when a real provider is disabled or unimplemented."""


@dataclass(frozen=True)
class SendRequest:
    """One outbound message; the phone exists only in memory."""

    idempotency_key: str
    to_phone: str
    body: str
    template_name: str
    language: str


class ResultKind(StrEnum):
    """Provider outcome classes used by the retry policy."""

    ACCEPTED = "ACCEPTED"
    RETRYABLE = "RETRYABLE"
    PERMANENT = "PERMANENT"


@dataclass(frozen=True)
class SendResult:
    """Classified result of one provider send call."""

    kind: ResultKind
    code: str | None = None
    message: str | None = None
    provider_message_id: str | None = None
    retry_after_seconds: float | None = None


@dataclass(frozen=True)
class Receipt:
    """Delivery, read or failure receipt for a previously accepted message."""

    provider_message_id: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    timestamp: datetime | None = None


@runtime_checkable
class Messenger(Protocol):
    """Provider contract used by the sending engine and contract tests."""

    name: str

    def send(self, req: SendRequest) -> SendResult:
        """Send one message and classify the provider outcome."""
        ...

    def poll_receipts(self) -> list[Receipt]:
        """Return receipts that are due; only the mock produces any."""
        ...

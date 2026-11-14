"""Deterministic in-memory Messenger used by the demo and tests."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from app.core.clock import Clock
from app.providers.messenger.base import (
    Receipt,
    ResultKind,
    SendRequest,
    SendResult,
)

_DELIVERED_DELAY_SECONDS = 2
_READ_DELAY_SECONDS = 5
_FAILED_DELAY_SECONDS = 2


class MockMessenger:
    """Apply the mock-data behavior matrix keyed by the last four phone digits."""

    name = "mock"

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self.calls = 0
        self.unique_messages = 0
        self._accepted: dict[str, str] = {}
        self._attempts: dict[str, int] = {}
        self._receipts: list[tuple[datetime, Receipt]] = []

    def send(self, req: SendRequest) -> SendResult:
        """Send one message; repeated accepted keys return the original message id."""
        self.calls += 1
        accepted_id = self._accepted.get(req.idempotency_key)
        if accepted_id is not None:
            return SendResult(
                kind=ResultKind.ACCEPTED,
                provider_message_id=accepted_id,
            )
        attempt = self._attempts.get(req.idempotency_key, 0) + 1
        self._attempts[req.idempotency_key] = attempt
        suffix = req.to_phone[-4:]
        kind, code, message, retry_after = self._outcome(suffix, attempt)
        if kind is not ResultKind.ACCEPTED:
            return SendResult(
                kind=kind,
                code=code,
                message=message,
                retry_after_seconds=retry_after,
            )
        message_id = self._message_id(req.idempotency_key)
        self._accepted[req.idempotency_key] = message_id
        self.unique_messages += 1
        self._queue_receipts(suffix, message_id)
        return SendResult(kind=kind, provider_message_id=message_id)

    def poll_receipts(self) -> list[Receipt]:
        """Return and remove receipts whose simulated due time has passed."""
        now = self._clock.now()
        due = [entry for entry in self._receipts if entry[0] <= now]
        self._receipts = [entry for entry in self._receipts if entry[0] > now]
        return [receipt for _, receipt in sorted(due, key=lambda entry: entry[0])]

    def flush_receipts(self) -> list[Receipt]:
        """Return every queued receipt immediately, for the demo endpoint."""
        receipts = [
            receipt
            for _, receipt in sorted(self._receipts, key=lambda entry: entry[0])
        ]
        self._receipts.clear()
        return receipts

    @staticmethod
    def _outcome(
        suffix: str, attempt: int
    ) -> tuple[ResultKind, str | None, str | None, float | None]:
        if suffix == "9001":
            if attempt <= 2:
                return (
                    ResultKind.RETRYABLE,
                    "TIMEOUT",
                    "mock request timed out",
                    None,
                )
            return ResultKind.ACCEPTED, None, None, None
        if suffix == "9002":
            return (
                ResultKind.RETRYABLE,
                "SERVER_ERROR",
                "mock server error",
                None,
            )
        if suffix == "9003":
            return (
                ResultKind.PERMANENT,
                "INVALID_NUMBER",
                "mock invalid number",
                None,
            )
        if suffix == "9004":
            if attempt == 1:
                return (
                    ResultKind.RETRYABLE,
                    "RATE_LIMITED",
                    "mock rate limited",
                    3.0,
                )
            return ResultKind.ACCEPTED, None, None, None
        return ResultKind.ACCEPTED, None, None, None

    @staticmethod
    def _message_id(idempotency_key: str) -> str:
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return f"mock-msg-{digest[:16]}"

    def _queue_receipts(self, suffix: str, message_id: str) -> None:
        now = self._clock.now()
        if suffix == "9005":
            failed_at = now + timedelta(seconds=_FAILED_DELAY_SECONDS)
            self._receipts.append(
                (
                    failed_at,
                    Receipt(
                        provider_message_id=message_id,
                        status="failed",
                        error_code="DELIVERY_FAILED",
                        error_message="mock delivery failed",
                        timestamp=failed_at,
                    ),
                )
            )
            return
        delivered_at = now + timedelta(seconds=_DELIVERED_DELAY_SECONDS)
        self._receipts.append(
            (
                delivered_at,
                Receipt(
                    provider_message_id=message_id,
                    status="delivered",
                    timestamp=delivered_at,
                ),
            )
        )
        if suffix.isdigit() and int(suffix[-1]) % 2 == 0:
            read_at = now + timedelta(seconds=_READ_DELAY_SECONDS)
            self._receipts.append(
                (
                    read_at,
                    Receipt(
                        provider_message_id=message_id,
                        status="read",
                        timestamp=read_at,
                    ),
                )
            )

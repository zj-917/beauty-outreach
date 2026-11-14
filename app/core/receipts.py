"""Structural interface for receipt polling injected into the worker."""

from __future__ import annotations

from typing import Protocol


class ReceiptPoller(Protocol):
    """Apply provider receipts; returns how many receipts changed an item."""

    def poll_and_apply(self) -> int:
        """Fetch and apply any receipts currently due."""
        ...

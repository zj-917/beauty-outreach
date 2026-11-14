"""Pure exponential backoff with bounded jitter (campaign.md §7.3)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BackoffPolicy:
    """Backoff parameters mirrored from the settings registry."""

    base_seconds: float
    cap_seconds: float
    jitter: float
    max_attempts: int

    @classmethod
    def from_settings(cls, values: Mapping[str, Any]) -> BackoffPolicy:
        """Build the policy from merged runtime settings."""
        return cls(
            base_seconds=float(values["sending.backoff_base_seconds"]),
            cap_seconds=float(values["sending.backoff_cap_seconds"]),
            jitter=float(values["sending.backoff_jitter"]),
            max_attempts=int(values["sending.max_attempts"]),
        )


def retry_delay(policy: BackoffPolicy, *, attempt: int, u: float) -> float:
    """Return min(base * 2^(attempt-1), cap) scaled by (1 + jitter * u)."""
    if attempt < 1:
        raise ValueError("attempt must be at least 1")
    if not -1.0 <= u <= 1.0:
        raise ValueError("u must be within [-1, 1]")
    raw = min(policy.base_seconds * (2 ** (attempt - 1)), policy.cap_seconds)
    return raw * (1.0 + policy.jitter * u)

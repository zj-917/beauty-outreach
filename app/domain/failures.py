"""Provider failure classification shared by the sender (campaign.md §7)."""

from __future__ import annotations

AUTH_ERROR_CODE = "AUTH_ERROR"
RATE_LIMITED_CODE = "RATE_LIMITED"
CIRCUIT_BREAKING_CODES = frozenset({"TIMEOUT", "NETWORK_ERROR", "SERVER_ERROR"})


def breaks_circuit(code: str | None) -> bool:
    """Return whether a retryable failure counts towards the circuit breaker."""
    return code in CIRCUIT_BREAKING_CODES

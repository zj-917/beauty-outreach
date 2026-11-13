"""Authentication helpers."""

from __future__ import annotations

import hmac


def verify_admin_token(provided: str | None, expected: str) -> bool:
    """Compare the admin token in constant time."""
    if provided is None:
        return False
    return hmac.compare_digest(provided, expected)

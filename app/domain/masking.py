"""Pure masking helpers for phone numbers, audit snapshots and log lines."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SENSITIVE_FIELD_NAMES = frozenset(
    {"body", "rendered_body", "token", "secret", "password", "key"}
)
_PHONE_LIKE = re.compile(r"\+?\d[\d\s\-]{7,}\d")
_SENSITIVE_HEADER = re.compile(
    r"(?i)\b(x-admin-token|authorization|x-hub-signature-256)\b"
    r"\s*[:=]\s*(?:bearer\s+)?\S+"
)


def mask_phone(value: object) -> str:
    """Mask a phone number, keeping the first four and last four characters."""
    if not isinstance(value, str) or not value:
        return ""
    if len(value) < 10:
        keep = min(2, len(value))
        return "*" * (len(value) - keep) + value[-keep:]
    return f"{value[:4]}****{value[-4:]}"


def redact_text(text: str) -> str:
    """Mask phone-like digit sequences inside free text."""
    return _PHONE_LIKE.sub(lambda match: mask_phone(match.group(0)), text)


def redact_log_text(text: str) -> str:
    """Mask sensitive header values and phone-like sequences in a log line."""
    text = _SENSITIVE_HEADER.sub(lambda match: f"{match.group(1)}: ***", text)
    return redact_text(text)


def redact(value: Any) -> Any:
    """Recursively mask phone-like strings and drop sensitive field names."""
    if isinstance(value, str):
        return redact_log_text(value)
    if isinstance(value, Mapping):
        return {
            key: redact(item)
            for key, item in value.items()
            if str(key).lower() not in SENSITIVE_FIELD_NAMES
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value

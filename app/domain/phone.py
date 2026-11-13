"""E.164 phone normalization, the single entry point for raw phone input."""

from __future__ import annotations

import re

E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_PHONE_SEPARATORS = re.compile(r"[\s\-()]")


def normalize_phone(raw: object) -> str | None:
    """Strip separators and return E.164, or None when the value is not a valid phone."""
    if not isinstance(raw, str):
        return None
    candidate = _PHONE_SEPARATORS.sub("", raw)
    return candidate if E164_PATTERN.fullmatch(candidate) else None

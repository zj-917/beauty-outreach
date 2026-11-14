"""Pure normalization helpers for imported lead fields."""

from __future__ import annotations

import re
import unicodedata

USERNAME_PATTERN = re.compile(r"^[a-z0-9._]{1,30}$")
_REGION_PATTERN = re.compile(r"^[A-Z]{2}$")
_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}$")
_INSTAGRAM_URL = re.compile(r"^https://(?:www\.)?instagram\.com/", re.IGNORECASE)
_MAX_DISPLAY_NAME = 100
_MAX_BIO = 2000


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return unicodedata.normalize("NFKC", value).strip()


def normalize_username(value: object) -> str:
    """NFKC-normalize, strip, drop a leading @ and lower-case a username."""
    text = _text(value)
    if not text:
        return ""
    return text.removeprefix("@").lower()


def normalize_display_name(value: object) -> str | None:
    """Normalize a display name and truncate it to 100 characters."""
    text = _text(value)
    return text[:_MAX_DISPLAY_NAME] if text else None


def normalize_bio(value: object) -> str | None:
    """Normalize a bio and truncate it to 2000 characters."""
    text = _text(value)
    return text[:_MAX_BIO] if text else None


def normalize_region(value: object) -> tuple[str | None, bool]:
    """Return (region, valid); blank input is valid and yields None."""
    text = _text(value)
    if not text:
        return None, True
    upper = text.upper()
    return (upper, True) if _REGION_PATTERN.fullmatch(upper) else (None, False)


def normalize_language(value: object) -> tuple[str | None, bool]:
    """Return (primary language subtag, valid); blank input is valid and yields None."""
    text = _text(value)
    if not text:
        return None, True
    primary = re.split(r"[-_]", text.lower(), maxsplit=1)[0]
    return (primary, True) if _LANGUAGE_PATTERN.fullmatch(primary) else (None, False)


def normalize_source_url(value: object) -> tuple[str | None, bool]:
    """Return (url, valid); only https instagram.com links are accepted."""
    text = _text(value)
    if not text:
        return None, True
    return (text, True) if _INSTAGRAM_URL.match(text) else (None, False)

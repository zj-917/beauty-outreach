"""Lead field normalization unit tests."""

from __future__ import annotations

from app.domain.lead import (
    normalize_display_name,
    normalize_language,
    normalize_region,
    normalize_source_url,
    normalize_username,
)


def test_AC_LEAD_003_username_region_language_are_normalized() -> None:
    """Given decorated username, lower region and BCP-47 language, then each is normalized."""
    assert normalize_username(" @Glow.Mia ") == "glow.mia"
    assert normalize_username("＠FullWidth.Name") == "fullwidth.name"
    assert normalize_region("us") == ("US", True)
    assert normalize_region(" USA ") == (None, False)
    assert normalize_language("en-US") == ("en", True)
    assert normalize_language("zh_CN") == ("zh", True)
    assert normalize_language("e") == (None, False)


def test_AC_LEAD_003_optional_fields_normalize_to_null() -> None:
    """Given blank optional fields, then display name and region become null."""
    assert normalize_display_name("   ") is None
    assert normalize_display_name("x" * 120) == "x" * 100
    assert normalize_region("") == (None, True)
    assert normalize_language(None) == (None, True)
    assert normalize_source_url("") == (None, True)


def test_AC_LEAD_010_source_url_must_be_instagram_https() -> None:
    """Given instagram https links or other URLs, then only the former are accepted."""
    assert normalize_source_url("https://www.instagram.com/glow/")[1] is True
    assert normalize_source_url("https://instagram.com/glow")[1] is True
    assert normalize_source_url("http://instagram.com/glow") == (None, False)
    assert normalize_source_url("https://example.com/glow") == (None, False)

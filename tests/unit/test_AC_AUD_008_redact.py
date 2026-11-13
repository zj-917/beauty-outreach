"""Audit snapshot redaction tests."""

from __future__ import annotations

from app.domain.masking import redact, redact_text


def test_AC_AUD_008_redact_drops_sensitive_fields_and_masks_phones() -> None:
    """Given secrets and phones, when redacted, then only masked safe data remains."""
    snapshot = {
        "phone": "+15555550101",
        "body": "hello",
        "rendered_body": "hello",
        "token": "secret-token",
        "secret": "s",
        "password": "p",
        "key": "k",
        "nested": {
            "phone_masked": "+155****0101",
            "note": "call +15555550101 or pass Authorization: Bearer top-secret",
        },
        "items": ["+8613812345678", 42],
    }
    result = redact(snapshot)
    assert set(result) == {"phone", "nested", "items"}
    assert result["phone"] == "+155****0101"
    assert result["nested"]["phone_masked"] == "+155****0101"
    assert result["nested"]["note"] == "call +155****0101 or pass Authorization: ***"
    assert result["items"] == ["+861****5678", 42]


def test_AC_AUD_008_redact_text_masks_phone_like_sequences() -> None:
    """Given free text with a phone-like sequence, when redacted, then the digits are masked."""
    assert redact_text("call +1 555-555-0101 now") == "call +1 5****0101 now"
    assert redact_text("order 12345") == "order 12345"

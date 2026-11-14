"""Audit snapshot redaction tests."""

from __future__ import annotations

from app.domain.masking import redact, redact_log_text, redact_text


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


def test_AC_AUD_008_redact_text_keeps_iso_timestamps() -> None:
    """Given ISO timestamps, when redacted, then date-like runs are left intact."""
    assert redact_text("2026-11-14T09:00:00Z") == "2026-11-14T09:00:00Z"
    assert redact_text("2026-11-14 09:00:00") == "2026-11-14 09:00:00"


def test_AC_AUD_008_redact_text_keeps_request_ids() -> None:
    """Given a hex id or UUID, when redacted, then the id survives intact."""
    hex_id = "fd6310fd8ad3411b9dd2da1153423259"
    uuid = "123e4567-e89b-12d3-a456-426614174000"
    assert redact_text(f"request_id={hex_id}") == f"request_id={hex_id}"
    assert redact_text(f"request_id={uuid}") == f"request_id={uuid}"
    assert redact_text("call +1 555-555-0101 now") == "call +1 5****0101 now"


def test_AC_AUD_008_redact_text_keeps_date_and_masks_adjacent_phone() -> None:
    """Given a date next to a phone, when redacted, then only the phone is masked."""
    assert redact_text("2026-11-14") == "2026-11-14"
    assert redact_text("2026-11-14 555-555-0101") == "2026-11-14 555-****0101"
    assert redact_text("555-555-0101") == "555-****0101"


def test_AC_AUD_008_redact_log_text_masks_the_whole_header_value() -> None:
    """Given a header value with spaces, when redacted, then the entire value is masked."""
    assert redact_log_text("Authorization: Bearer abc def ghi") == "Authorization: ***"
    assert redact_log_text("x-admin-token=abc def") == "x-admin-token: ***"

"""Phone normalization tests."""

from __future__ import annotations

import pytest

from app.domain.phone import normalize_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+15555550101", "+15555550101"),
        (" +1 (555) 555-0101 ", "+15555550101"),
        ("+86 138 1234 5678", "+8613812345678"),
        ("+12345678", "+12345678"),
        ("15555550101", None),
        ("+0123456789", None),
        ("+1234567", None),
        ("+1234567890123456", None),
        ("", None),
        ("   ", None),
        (None, None),
        (12345, None),
    ],
)
def test_AC_LEAD_003_normalize_phone(raw: object, expected: str | None) -> None:
    """Covers: AC-LEAD-003, AC-LEAD-007.

    Given raw phone values, when normalized, then E.164 is returned or None.
    """
    assert normalize_phone(raw) == expected

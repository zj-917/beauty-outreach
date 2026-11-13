"""Phone masking tests."""

from __future__ import annotations

import pytest

from app.domain.masking import mask_phone


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("+8613812345678", "+861****5678"),
        ("+15555550101", "+155****0101"),
        ("+123456789", "+123****6789"),
        ("+12345678", "*******78"),
        ("+123456", "*****56"),
        ("+155****0101", "+155****0101"),
        ("", ""),
        (None, ""),
        (12345, ""),
    ],
)
def test_AC_AUD_007_mask_phone(value: object, expected: str) -> None:
    """Given long, short, masked, empty or non-string input, when masked, then §6.1 holds."""
    assert mask_phone(value) == expected

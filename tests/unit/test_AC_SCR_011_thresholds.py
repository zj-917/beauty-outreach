"""Threshold setting validation tests."""

from __future__ import annotations

import pytest

from app.domain.settings import (
    SettingValidationError,
    default_settings,
    validate_settings_patch,
)


def test_AC_SCR_011_low_must_be_below_high() -> None:
    """Given low >= high after the merge, when validated, then it is rejected."""
    with pytest.raises(SettingValidationError):
        validate_settings_patch(default_settings(), {"screening.threshold_low": 70})


def test_AC_SCR_011_out_of_range_threshold_is_rejected() -> None:
    """Given an out-of-range threshold, when validated, then it is rejected."""
    with pytest.raises(SettingValidationError):
        validate_settings_patch(default_settings(), {"screening.threshold_high": 0})

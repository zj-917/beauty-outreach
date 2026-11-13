"""Setting registry coverage tests."""

from __future__ import annotations

import pytest

from app.domain.settings import SETTING_SPECS, SettingValidationError


@pytest.mark.parametrize("key", sorted(SETTING_SPECS))
def test_AC_CFG_003_defaults_are_valid_and_wrong_types_are_rejected(key: str) -> None:
    """Given every registered key, when parsed, then its default passes and garbage fails."""
    spec = SETTING_SPECS[key]
    assert spec.parser(spec.default) == spec.default
    with pytest.raises(SettingValidationError):
        spec.parser(object())

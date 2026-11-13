"""Environment validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import (
    ConfigurationError,
    Settings,
    load_settings,
    validate_runtime_settings,
)

REQUIRED_ENV = ("ADMIN_TOKEN", "PHONE_ENC_KEY", "PHONE_HASH_KEY", "WEBHOOK_SECRET")
VALID_KEY = "ZmDfcTF7_60GrrY167zsiPd67pEvs0ouEkuFfKjGmS0="


def _valid_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "admin_token": "token",
        "phone_enc_key": VALID_KEY,
        "phone_hash_key": "hash",
        "webhook_secret": "secret",
    }
    values.update(overrides)
    return Settings(**values)


def test_AC_CFG_007_missing_env_names_each_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Given missing required variables, when loaded, then the error names each one."""
    for name in REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()
    message = str(exc_info.value)
    for name in REQUIRED_ENV:
        assert name in message


def test_AC_CFG_007_invalid_fernet_key_is_named() -> None:
    """Given an invalid PHONE_ENC_KEY, when validated, then the error names it."""
    settings = _valid_settings(phone_enc_key="not-a-key")
    with pytest.raises(ConfigurationError, match="PHONE_ENC_KEY"):
        validate_runtime_settings(settings)

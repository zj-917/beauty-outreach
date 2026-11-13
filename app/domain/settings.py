"""Runtime setting registry and validation."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class SettingValidationError(ValueError):
    """Raised when a setting key or value is invalid."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SettingValidationError(message)


def _as_bool(value: Any) -> bool:
    _require(isinstance(value, bool), "expected a boolean")
    return value


def _as_int(low: int, high: int) -> Callable[[Any], int]:
    def parse(value: Any) -> int:
        _require(isinstance(value, int) and not isinstance(value, bool), "expected an integer")
        _require(low <= value <= high, f"must be between {low} and {high}")
        return value

    return parse


def _as_float(low: float, high: float) -> Callable[[Any], float]:
    def parse(value: Any) -> float:
        _require(
            isinstance(value, (int, float)) and not isinstance(value, bool),
            "expected a number",
        )
        _require(low <= float(value) <= high, f"must be between {low} and {high}")
        return float(value)

    return parse


def _as_text(low: int, high: int) -> Callable[[Any], str]:
    def parse(value: Any) -> str:
        _require(isinstance(value, str), "expected a string")
        _require(low <= len(value) <= high, f"length must be between {low} and {high}")
        return value

    return parse


_REGION_RE = re.compile(r"^[A-Z]{2}$")
_LANGUAGE_RE = re.compile(r"^[a-z]{2,3}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _as_region_list(value: Any) -> list[str]:
    _require(isinstance(value, list), "expected a list")
    for item in value:
        _require(
            isinstance(item, str) and bool(_REGION_RE.fullmatch(item)),
            "expected uppercase ISO-3166 alpha-2 codes",
        )
    return list(value)


def _as_language_list(value: Any) -> list[str]:
    _require(isinstance(value, list), "expected a list")
    for item in value:
        _require(
            isinstance(item, str) and bool(_LANGUAGE_RE.fullmatch(item)),
            "expected lowercase 2-3 letter language codes",
        )
    return list(value)


def _as_time(value: Any) -> str:
    _require(isinstance(value, str) and bool(_TIME_RE.fullmatch(value)), "expected HH:MM")
    return value


def _as_timezone(value: Any) -> str:
    _require(isinstance(value, str), "expected an IANA timezone name")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise SettingValidationError("unknown IANA timezone") from None
    return value


def _as_stop_keywords(value: Any) -> list[str]:
    _require(isinstance(value, list) and bool(value), "expected a non-empty list")
    for item in value:
        _require(isinstance(item, str) and 1 <= len(item) <= 20, "invalid stop keyword")
    return list(value)


@dataclass(frozen=True)
class SettingSpec:
    """Default value and parser for one setting key."""

    default: Any
    parser: Callable[[Any], Any]


SETTING_SPECS: dict[str, SettingSpec] = {
    "screening.auto_approve_enabled": SettingSpec(True, _as_bool),
    "screening.threshold_high": SettingSpec(70, _as_int(1, 100)),
    "screening.threshold_low": SettingSpec(40, _as_int(0, 99)),
    "screening.allowed_regions": SettingSpec(
        ["US", "GB", "CA", "AU", "SG", "MY", "HK", "TW"], _as_region_list
    ),
    "screening.allowed_languages": SettingSpec(["en", "zh"], _as_language_list),
    "screening.region_bonus": SettingSpec(10, _as_int(0, 50)),
    "screening.region_penalty": SettingSpec(20, _as_int(0, 50)),
    "screening.language_bonus": SettingSpec(5, _as_int(0, 50)),
    "screening.language_penalty": SettingSpec(10, _as_int(0, 50)),
    "screening.short_bio_min_len": SettingSpec(10, _as_int(0, 200)),
    "screening.short_bio_penalty": SettingSpec(10, _as_int(0, 50)),
    "sending.max_attempts": SettingSpec(3, _as_int(1, 10)),
    "sending.backoff_base_seconds": SettingSpec(2.0, _as_float(0.1, 3600)),
    "sending.backoff_cap_seconds": SettingSpec(60.0, _as_float(0.1, 86400)),
    "sending.backoff_jitter": SettingSpec(0.2, _as_float(0, 0.5)),
    "sending.claim_batch_size": SettingSpec(10, _as_int(1, 100)),
    "sending.lease_seconds": SettingSpec(60, _as_int(5, 3600)),
    "sending.provider_timeout_seconds": SettingSpec(10.0, _as_float(0.5, 120)),
    "sending.circuit_breaker_threshold": SettingSpec(5, _as_int(1, 100)),
    "sending.quiet_hours_enabled": SettingSpec(False, _as_bool),
    "sending.quiet_hours_start": SettingSpec("22:00", _as_time),
    "sending.quiet_hours_end": SettingSpec("08:00", _as_time),
    "sending.quiet_hours_tz": SettingSpec("UTC", _as_timezone),
    "message.brand": SettingSpec("GlowLab", _as_text(1, 40)),
    "message.optout_text": SettingSpec(
        "Reply STOP to unsubscribe. 回复 STOP 退订。", _as_text(1, 160)
    ),
    "compliance.stop_keywords": SettingSpec(
        ["stop", "unsubscribe", "cancel", "end", "quit", "退订", "取消订阅"],
        _as_stop_keywords,
    ),
}

DEFAULT_SETTINGS: dict[str, Any] = {
    key: spec.default for key, spec in SETTING_SPECS.items()
}


def default_settings() -> dict[str, Any]:
    """Return a deep copy of the registry defaults."""
    return copy.deepcopy(DEFAULT_SETTINGS)


def _validate_cross_field(values: dict[str, Any]) -> None:
    if values["screening.threshold_low"] >= values["screening.threshold_high"]:
        raise SettingValidationError(
            "screening.threshold_low must be lower than screening.threshold_high"
        )
    if values["sending.backoff_cap_seconds"] < values["sending.backoff_base_seconds"]:
        raise SettingValidationError(
            "sending.backoff_cap_seconds must be at least sending.backoff_base_seconds"
        )
    if values["sending.quiet_hours_start"] == values["sending.quiet_hours_end"]:
        raise SettingValidationError(
            "sending.quiet_hours_start and sending.quiet_hours_end must differ"
        )


def validate_settings_patch(
    current: dict[str, Any], updates: dict[str, Any]
) -> dict[str, Any]:
    """Validate a partial settings update against the merged current values."""
    unknown = sorted(set(updates) - set(SETTING_SPECS))
    if unknown:
        raise SettingValidationError(
            "Unknown setting keys", details={"unknown_keys": unknown}
        )
    merged = dict(current)
    errors: dict[str, str] = {}
    normalized: dict[str, Any] = {}
    for key, value in updates.items():
        try:
            normalized[key] = SETTING_SPECS[key].parser(value)
        except SettingValidationError as exc:
            errors[key] = str(exc)
    if errors:
        raise SettingValidationError("Invalid setting values", details={"errors": errors})
    merged.update(normalized)
    try:
        _validate_cross_field(merged)
    except SettingValidationError as exc:
        raise SettingValidationError(
            str(exc), details={"errors": {"cross_field": str(exc)}}
        ) from exc
    return normalized

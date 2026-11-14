"""Phone gate tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.gates import ComplianceSnapshot, Skip, evaluate

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


def _snapshot(**overrides: object) -> ComplianceSnapshot:
    base: dict[str, object] = {
        "has_phone": True,
        "phone_valid": True,
        "consent": "GRANTED",
        "now": NOW,
    }
    base.update(overrides)
    return ComplianceSnapshot(**base)  # type: ignore[arg-type]


def test_AC_COMP_010_missing_phone_skips() -> None:
    """Given no phone, when gated, then the lead is skipped with NO_PHONE."""
    assert evaluate(_snapshot(has_phone=False, phone_valid=False)) == Skip("NO_PHONE")


def test_AC_COMP_010_invalid_phone_skips() -> None:
    """Given a decrypted phone that is not E.164, when gated, then INVALID_PHONE is returned."""
    assert evaluate(_snapshot(phone_valid=False)) == Skip("INVALID_PHONE")


def test_AC_COMP_010_phone_gate_precedes_consent() -> None:
    """Given no phone and no consent, when gated, then NO_PHONE wins."""
    assert evaluate(
        _snapshot(has_phone=False, phone_valid=False, consent=None)
    ) == Skip("NO_PHONE")

"""Missing and revoked consent gate tests."""

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


def test_AC_COMP_002_missing_consent_skips() -> None:
    """Given no consent record, when gated, then the lead is skipped with NO_CONSENT."""
    assert evaluate(_snapshot(consent=None)) == Skip("NO_CONSENT")


def test_AC_COMP_003_revoked_consent_skips() -> None:
    """Given revoked consent, when gated, then the lead is skipped with CONSENT_REVOKED."""
    assert evaluate(_snapshot(consent="REVOKED")) == Skip("CONSENT_REVOKED")

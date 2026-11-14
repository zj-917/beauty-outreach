"""Pool readiness mapping tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.gates import (
    READINESS_VALUES,
    ComplianceSnapshot,
    QuietHours,
    readiness,
)

NOW = datetime(2026, 11, 14, 23, 0, tzinfo=UTC)


def _snapshot(**overrides: object) -> ComplianceSnapshot:
    base: dict[str, object] = {
        "has_phone": True,
        "phone_valid": True,
        "consent": "GRANTED",
        "now": NOW,
    }
    base.update(overrides)
    return ComplianceSnapshot(**base)  # type: ignore[arg-type]


def test_AC_POOL_006_readiness_maps_gate_results() -> None:
    """Given gate snapshots, when mapped, then readiness uses the pool's fixed vocabulary."""
    assert set(READINESS_VALUES) == {
        "READY",
        "BLACKLISTED",
        "UNSUBSCRIBED",
        "NO_PHONE",
        "NO_CONSENT",
        "CONSENT_REVOKED",
    }
    assert readiness(_snapshot()) == "READY"
    assert readiness(
        _snapshot(quiet_hours=QuietHours(enabled=True))
    ) == "READY"
    assert readiness(_snapshot(suppression=frozenset({"BLACKLIST"}))) == "BLACKLISTED"
    assert readiness(_snapshot(suppression=frozenset({"UNSUBSCRIBE"}))) == "UNSUBSCRIBED"
    assert readiness(_snapshot(has_phone=False, phone_valid=False)) == "NO_PHONE"
    assert readiness(_snapshot(phone_valid=False)) == "NO_PHONE"
    assert readiness(_snapshot(consent=None)) == "NO_CONSENT"
    assert readiness(_snapshot(consent="REVOKED")) == "CONSENT_REVOKED"

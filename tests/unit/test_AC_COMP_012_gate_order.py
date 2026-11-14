"""Fixed gate ordering and purity tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.gates import (
    ComplianceSnapshot,
    Defer,
    QuietHours,
    Skip,
    evaluate,
)

NOW = datetime(2026, 11, 14, 23, 0, tzinfo=UTC)
IN_WINDOW = QuietHours(enabled=True)


def _snapshot(**overrides: object) -> ComplianceSnapshot:
    base: dict[str, object] = {
        "has_phone": True,
        "phone_valid": True,
        "consent": "GRANTED",
        "now": NOW,
        "quiet_hours": IN_WINDOW,
    }
    base.update(overrides)
    return ComplianceSnapshot(**base)  # type: ignore[arg-type]


def test_AC_COMP_012_first_non_pass_gate_decides() -> None:
    """Given every combination, then suppression, phone, consent, quiet hours decide in order."""
    assert evaluate(
        _snapshot(
            has_phone=False,
            phone_valid=False,
            consent=None,
            suppression=frozenset({"BLACKLIST"}),
        )
    ) == Skip("BLACKLISTED")
    assert evaluate(
        _snapshot(has_phone=False, phone_valid=False, consent=None)
    ) == Skip("NO_PHONE")
    assert evaluate(_snapshot(consent=None)) == Skip("NO_CONSENT")
    assert evaluate(_snapshot(consent="REVOKED")) == Skip("CONSENT_REVOKED")
    assert evaluate(_snapshot()) == Defer(
        datetime(2026, 11, 15, 8, 0, tzinfo=UTC), "QUIET_HOURS"
    )


def test_AC_COMP_012_evaluation_is_deterministic() -> None:
    """Given the same snapshot, when evaluated twice, then both results are identical."""
    snapshot = _snapshot(suppression=frozenset({"UNSUBSCRIBE"}))

    assert evaluate(snapshot) == evaluate(snapshot)

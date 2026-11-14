"""Suppression precedence gate tests."""

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


def test_AC_COMP_005_blacklist_beats_granted_consent() -> None:
    """Given GRANTED consent and a blacklist hit, when gated, then BLACKLISTED wins."""
    snapshot = _snapshot(suppression=frozenset({"BLACKLIST"}))

    assert evaluate(snapshot) == Skip("BLACKLISTED")


def test_AC_COMP_005_unsubscribe_beats_blacklist() -> None:
    """Given both suppression types, when gated, then UNSUBSCRIBED wins."""
    snapshot = _snapshot(suppression=frozenset({"BLACKLIST", "UNSUBSCRIBE"}))

    assert evaluate(snapshot) == Skip("UNSUBSCRIBED")


def test_AC_COMP_005_suppression_runs_before_phone_and_consent() -> None:
    """Given no phone, no consent and a suppression hit, when gated, then suppression wins."""
    blacklisted = _snapshot(
        has_phone=False,
        phone_valid=False,
        consent=None,
        suppression=frozenset({"BLACKLIST"}),
    )
    unsubscribed = _snapshot(
        has_phone=False,
        phone_valid=False,
        consent=None,
        suppression=frozenset({"UNSUBSCRIBE"}),
    )

    assert evaluate(blacklisted) == Skip("BLACKLISTED")
    assert evaluate(unsubscribed) == Skip("UNSUBSCRIBED")

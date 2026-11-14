"""Full send gate chain ordering tests (AC-CAMP-010)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from app.domain.gates import (
    ComplianceSnapshot,
    Defer,
    Pass,
    QuietHours,
    Release,
    SendContext,
    Skip,
    send_decision,
)

NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)


def _snapshot(**overrides) -> ComplianceSnapshot:
    base = ComplianceSnapshot(
        has_phone=True, phone_valid=True, consent="GRANTED", now=NOW
    )
    return replace(base, **overrides)


def _context(**overrides) -> SendContext:
    base = SendContext(
        task_running=True,
        compliance=_snapshot(),
        template_approved=True,
        render_failed=None,
        already_contacted=False,
        recipient_rate_limited=False,
        global_rate_until=None,
    )
    return replace(base, **overrides)


def test_AC_CAMP_010_all_gates_pass() -> None:
    """Given every gate is clear, when evaluated, then the decision is Pass."""
    assert send_decision(_context()) == Pass()


def test_AC_CAMP_010_gate_one_releases_when_task_inactive() -> None:
    """Given the task is not RUNNING, when evaluated, then gate 1 releases the lease."""
    result = send_decision(
        _context(
            task_running=False,
            compliance=_snapshot(suppression=frozenset({"UNSUBSCRIBE"})),
        )
    )
    assert result == Release()


def test_AC_CAMP_010_gates_two_to_four_come_from_compliance() -> None:
    """Given suppression, phone or consent problems, when evaluated, then compliance wins."""
    assert send_decision(
        _context(
            compliance=_snapshot(
                suppression=frozenset({"BLACKLIST", "UNSUBSCRIBE"})
            )
        )
    ) == Skip("UNSUBSCRIBED")
    assert send_decision(
        _context(compliance=_snapshot(suppression=frozenset({"BLACKLIST"})))
    ) == Skip("BLACKLISTED")
    assert send_decision(
        _context(compliance=_snapshot(has_phone=False))
    ) == Skip("NO_PHONE")
    assert send_decision(
        _context(compliance=_snapshot(phone_valid=False))
    ) == Skip("INVALID_PHONE")
    assert send_decision(
        _context(compliance=_snapshot(consent=None))
    ) == Skip("NO_CONSENT")
    assert send_decision(
        _context(compliance=_snapshot(consent="REVOKED"))
    ) == Skip("CONSENT_REVOKED")


def test_AC_CAMP_010_gate_five_covers_template_and_render() -> None:
    """Given an unapproved template or a render failure, when evaluated, then gate 5 skips."""
    assert send_decision(_context(template_approved=False)) == Skip(
        "TEMPLATE_NOT_APPROVED"
    )
    assert send_decision(_context(render_failed="TEMPLATE_VARIABLE_MISSING")) == Skip(
        "TEMPLATE_VARIABLE_MISSING"
    )


def test_AC_CAMP_010_gates_six_and_seven_skip() -> None:
    """Given a duplicate contact or a per-recipient limit, when evaluated, then skips apply."""
    assert send_decision(_context(already_contacted=True)) == Skip(
        "ALREADY_CONTACTED"
    )
    assert send_decision(_context(recipient_rate_limited=True)) == Skip(
        "RECIPIENT_RATE_LIMITED"
    )


def test_AC_CAMP_010_gates_eight_and_nine_defer() -> None:
    """Given quiet hours or a global limit, when evaluated, then the item defers."""
    quiet = _context(
        compliance=_snapshot(
            now=datetime(2026, 11, 14, 23, 0, tzinfo=UTC),
            quiet_hours=QuietHours(enabled=True, start="22:00", end="08:00"),
        )
    )
    assert send_decision(quiet) == Defer(
        until=datetime(2026, 11, 15, 8, 0, tzinfo=UTC), reason="QUIET_HOURS"
    )
    until = datetime(2026, 11, 14, 9, 0, 10, tzinfo=UTC)
    assert send_decision(_context(global_rate_until=until)) == Defer(
        until=until, reason="RATE_LIMIT_GLOBAL"
    )


def test_AC_CAMP_010_first_non_pass_gate_decides() -> None:
    """Given several gates trip at once, when evaluated, then the earliest one decides."""
    everything = _context(
        compliance=_snapshot(
            suppression=frozenset({"UNSUBSCRIBE"}),
            has_phone=False,
            consent=None,
        ),
        template_approved=False,
        render_failed="TEMPLATE_VARIABLE_MISSING",
        already_contacted=True,
        recipient_rate_limited=True,
        global_rate_until=NOW,
    )
    assert send_decision(everything) == Skip("UNSUBSCRIBED")

    assert send_decision(
        _context(
            template_approved=False,
            already_contacted=True,
            recipient_rate_limited=True,
        )
    ) == Skip("TEMPLATE_NOT_APPROVED")
    assert send_decision(
        _context(
            already_contacted=True,
            recipient_rate_limited=True,
            global_rate_until=NOW,
        )
    ) == Skip("ALREADY_CONTACTED")
    assert send_decision(
        _context(recipient_rate_limited=True, global_rate_until=NOW)
    ) == Skip("RECIPIENT_RATE_LIMITED")
    assert send_decision(
        _context(
            compliance=_snapshot(
                now=datetime(2026, 11, 14, 23, 0, tzinfo=UTC),
                quiet_hours=QuietHours(enabled=True, start="22:00", end="08:00"),
            ),
            global_rate_until=NOW,
        )
    ) == Defer(
        until=datetime(2026, 11, 15, 8, 0, tzinfo=UTC), reason="QUIET_HOURS"
    )

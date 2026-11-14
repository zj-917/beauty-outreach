"""Quiet-hours deferral tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.gates import ComplianceSnapshot, Defer, Pass, QuietHours, evaluate


def _snapshot(now: datetime, **quiet_hours: object) -> ComplianceSnapshot:
    return ComplianceSnapshot(
        has_phone=True,
        phone_valid=True,
        consent="GRANTED",
        now=now,
        quiet_hours=QuietHours(enabled=True, **quiet_hours),  # type: ignore[arg-type]
    )


def test_AC_COMP_011_disabled_quiet_hours_passes() -> None:
    """Given quiet hours disabled, when gated, then the lead passes."""
    snapshot = ComplianceSnapshot(
        has_phone=True,
        phone_valid=True,
        consent="GRANTED",
        now=datetime(2026, 11, 14, 23, 0, tzinfo=UTC),
        quiet_hours=QuietHours(enabled=False),
    )

    assert evaluate(snapshot) == Pass()


def test_AC_COMP_011_cross_midnight_window_defers_until_window_end() -> None:
    """Given a 22:00-08:00 window, when late or early, then defer to the next 08:00."""
    late = _snapshot(datetime(2026, 11, 14, 23, 0, tzinfo=UTC))
    early = _snapshot(datetime(2026, 11, 14, 7, 0, tzinfo=UTC))

    assert evaluate(late) == Defer(
        datetime(2026, 11, 15, 8, 0, tzinfo=UTC), "QUIET_HOURS"
    )
    assert evaluate(early) == Defer(
        datetime(2026, 11, 14, 8, 0, tzinfo=UTC), "QUIET_HOURS"
    )


def test_AC_COMP_011_daytime_window_and_outside_window() -> None:
    """Given a 09:00-17:00 window, when inside defer; when outside pass."""
    window = {"start": "09:00", "end": "17:00"}

    assert evaluate(
        _snapshot(datetime(2026, 11, 14, 10, 0, tzinfo=UTC), **window)
    ) == Defer(datetime(2026, 11, 14, 17, 0, tzinfo=UTC), "QUIET_HOURS")
    assert evaluate(
        _snapshot(datetime(2026, 11, 14, 18, 0, tzinfo=UTC), **window)
    ) == Pass()


def test_AC_COMP_011_converts_the_configured_timezone_to_utc() -> None:
    """Given Asia/Shanghai quiet hours, when local time is 23:00, then until is 00:00 UTC."""
    snapshot = _snapshot(
        datetime(2026, 11, 14, 15, 0, tzinfo=UTC),
        tz="Asia/Shanghai",
    )

    assert evaluate(snapshot) == Defer(
        datetime(2026, 11, 15, 0, 0, tzinfo=UTC), "QUIET_HOURS"
    )


def test_AC_COMP_011_window_boundaries() -> None:
    """Given a cross-midnight window, then start is included and end is excluded."""
    assert evaluate(
        _snapshot(datetime(2026, 11, 14, 22, 0, tzinfo=UTC))
    ) == Defer(datetime(2026, 11, 15, 8, 0, tzinfo=UTC), "QUIET_HOURS")
    assert evaluate(_snapshot(datetime(2026, 11, 14, 8, 0, tzinfo=UTC))) == Pass()

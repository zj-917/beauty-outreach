"""Pure compliance gate decisions shared by the sender and the pool."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

READINESS_VALUES = (
    "READY",
    "BLACKLISTED",
    "UNSUBSCRIBED",
    "NO_PHONE",
    "NO_CONSENT",
    "CONSENT_REVOKED",
)


@dataclass(frozen=True)
class QuietHours:
    """Quiet-hours window expressed in a named timezone."""

    enabled: bool = False
    start: str = "22:00"
    end: str = "08:00"
    tz: str = "UTC"


@dataclass(frozen=True)
class ComplianceSnapshot:
    """Pre-fetched compliance facts for one recipient."""

    has_phone: bool
    phone_valid: bool
    consent: str | None
    now: datetime
    suppression: frozenset[str] = field(default_factory=frozenset)
    quiet_hours: QuietHours = field(default_factory=QuietHours)


@dataclass(frozen=True)
class Pass:
    """The gate allows the message to proceed."""


@dataclass(frozen=True)
class Skip:
    """The gate blocks the recipient for this attempt."""

    reason: str


@dataclass(frozen=True)
class Defer:
    """The gate asks the caller to retry after `until`."""

    until: datetime
    reason: str


GateResult = Pass | Skip | Defer


def suppression_gate(snapshot: ComplianceSnapshot) -> GateResult:
    """Skip unsubscribed recipients, then blacklisted ones."""
    if "UNSUBSCRIBE" in snapshot.suppression:
        return Skip("UNSUBSCRIBED")
    if "BLACKLIST" in snapshot.suppression:
        return Skip("BLACKLISTED")
    return Pass()


def phone_gate(snapshot: ComplianceSnapshot) -> GateResult:
    """Skip leads without a usable phone."""
    if not snapshot.has_phone:
        return Skip("NO_PHONE")
    if not snapshot.phone_valid:
        return Skip("INVALID_PHONE")
    return Pass()


def consent_gate(snapshot: ComplianceSnapshot) -> GateResult:
    """Skip leads without granted consent."""
    if snapshot.consent is None:
        return Skip("NO_CONSENT")
    if snapshot.consent == "REVOKED":
        return Skip("CONSENT_REVOKED")
    return Pass()


def quiet_hours_gate(snapshot: ComplianceSnapshot) -> GateResult:
    """Defer when the current local time falls inside the quiet-hours window."""
    if not snapshot.quiet_hours.enabled:
        return Pass()
    until = _quiet_hours_until(snapshot)
    if until is None:
        return Pass()
    return Defer(until, "QUIET_HOURS")


def evaluate(snapshot: ComplianceSnapshot) -> GateResult:
    """Apply the compliance gates in their fixed order."""
    for gate in (suppression_gate, phone_gate, consent_gate, quiet_hours_gate):
        result = gate(snapshot)
        if not isinstance(result, Pass):
            return result
    return Pass()


def readiness(snapshot: ComplianceSnapshot) -> str:
    """Map gates 2-4 to the pool vocabulary; invalid phones count as NO_PHONE."""
    for gate in (suppression_gate, phone_gate, consent_gate):
        result = gate(snapshot)
        if isinstance(result, Skip):
            return "NO_PHONE" if result.reason == "INVALID_PHONE" else result.reason
    return "READY"


def _quiet_hours_until(snapshot: ComplianceSnapshot) -> datetime | None:
    quiet = snapshot.quiet_hours
    try:
        zone = ZoneInfo(quiet.tz)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    start = time.fromisoformat(quiet.start)
    end = time.fromisoformat(quiet.end)
    if start == end:
        return None
    local = snapshot.now.astimezone(zone)
    current = local.time()
    if start < end:
        if start <= current < end:
            return _local_to_utc(local.date(), end, zone)
        return None
    if current >= start:
        return _local_to_utc(local.date() + timedelta(days=1), end, zone)
    if current < end:
        return _local_to_utc(local.date(), end, zone)
    return None


def _local_to_utc(day, at: time, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, at, tzinfo=zone).astimezone(UTC)

"""Pure campaign control state machine (§4 of the campaign spec)."""

from __future__ import annotations

from dataclasses import dataclass

CAMPAIGN_STATUSES = ("DRAFT", "RUNNING", "PAUSED", "COMPLETED", "CANCELLED")
CONTROL_ACTIONS = ("start", "pause", "resume", "cancel")

_TRANSITIONS: dict[str, dict[str, tuple[str, bool]]] = {
    "start": {
        "DRAFT": ("RUNNING", False),
        "RUNNING": ("RUNNING", True),
    },
    "pause": {"RUNNING": ("PAUSED", False)},
    "resume": {"PAUSED": ("RUNNING", False)},
    "cancel": {
        "DRAFT": ("CANCELLED", False),
        "RUNNING": ("CANCELLED", False),
        "PAUSED": ("CANCELLED", False),
    },
}


@dataclass(frozen=True)
class Transition:
    """Outcome of a legal control action; ``noop`` marks an idempotent repeat."""

    target: str
    noop: bool = False


def transition(status: str, action: str) -> Transition | None:
    """Return the transition for a status/action pair, or None when illegal."""
    if action not in _TRANSITIONS:
        raise ValueError(f"unknown campaign action: {action}")
    match = _TRANSITIONS[action].get(status)
    if match is None:
        return None
    return Transition(target=match[0], noop=match[1])

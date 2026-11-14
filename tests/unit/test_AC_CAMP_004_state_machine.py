"""Campaign state machine policy tests."""

from __future__ import annotations

import pytest

from app.domain.state import (
    CAMPAIGN_STATUSES,
    CONTROL_ACTIONS,
    Transition,
    transition,
)


def test_AC_CAMP_004_state_machine_defines_full_matrix() -> None:
    """Given the spec tables, when imported, then all statuses and actions are known."""
    assert set(CAMPAIGN_STATUSES) == {
        "DRAFT",
        "RUNNING",
        "PAUSED",
        "COMPLETED",
        "CANCELLED",
    }
    assert set(CONTROL_ACTIONS) == {"start", "pause", "resume", "cancel"}


@pytest.mark.parametrize(
    ("status", "action", "target", "noop"),
    [
        ("DRAFT", "start", "RUNNING", False),
        ("DRAFT", "pause", None, False),
        ("DRAFT", "resume", None, False),
        ("DRAFT", "cancel", "CANCELLED", False),
        ("RUNNING", "start", "RUNNING", True),
        ("RUNNING", "pause", "PAUSED", False),
        ("RUNNING", "resume", None, False),
        ("RUNNING", "cancel", "CANCELLED", False),
        ("PAUSED", "start", None, False),
        ("PAUSED", "pause", None, False),
        ("PAUSED", "resume", "RUNNING", False),
        ("PAUSED", "cancel", "CANCELLED", False),
        ("COMPLETED", "start", None, False),
        ("COMPLETED", "pause", None, False),
        ("COMPLETED", "resume", None, False),
        ("COMPLETED", "cancel", None, False),
        ("CANCELLED", "start", None, False),
        ("CANCELLED", "pause", None, False),
        ("CANCELLED", "resume", None, False),
        ("CANCELLED", "cancel", None, False),
    ],
)
def test_AC_CAMP_004_transition_matrix(
    status: str, action: str, target: str | None, noop: bool
) -> None:
    """Given each of the 5x4 combinations, when evaluated, then §4 is applied exactly."""
    result = transition(status, action)
    if target is None:
        assert result is None
    else:
        assert result == Transition(target=target, noop=noop)


def test_AC_CAMP_004_unknown_action_is_a_programming_error() -> None:
    """Given an action outside the table, when evaluated, then it raises ValueError."""
    with pytest.raises(ValueError):
        transition("DRAFT", "explode")

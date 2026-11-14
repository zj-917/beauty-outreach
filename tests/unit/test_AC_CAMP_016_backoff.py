"""Exponential backoff formula tests (AC-CAMP-016)."""

from __future__ import annotations

import pytest

from app.domain.backoff import BackoffPolicy, retry_delay

POLICY = BackoffPolicy(
    base_seconds=2.0, cap_seconds=60.0, jitter=0.2, max_attempts=3
)


def test_AC_CAMP_016_delay_doubles_until_the_cap() -> None:
    """Given no jitter, when attempts grow, then delay doubles and sticks at the cap."""
    assert retry_delay(POLICY, attempt=1, u=0.0) == 2.0
    assert retry_delay(POLICY, attempt=2, u=0.0) == 4.0
    assert retry_delay(POLICY, attempt=3, u=0.0) == 8.0
    assert retry_delay(POLICY, attempt=10, u=0.0) == 60.0


def test_AC_CAMP_016_jitter_scales_the_delay() -> None:
    """Given the injected RNG extremes, when computing delay, then jitter applies."""
    assert retry_delay(POLICY, attempt=1, u=1.0) == pytest.approx(2.4)
    assert retry_delay(POLICY, attempt=1, u=-1.0) == pytest.approx(1.6)
    assert retry_delay(POLICY, attempt=2, u=0.5) == pytest.approx(4.4)


def test_AC_CAMP_016_invalid_inputs_are_rejected() -> None:
    """Given an impossible attempt or RNG value, when computing, then it raises."""
    with pytest.raises(ValueError):
        retry_delay(POLICY, attempt=0, u=0.0)
    with pytest.raises(ValueError):
        retry_delay(POLICY, attempt=1, u=1.5)


def test_AC_CAMP_016_policy_reads_the_settings_registry() -> None:
    """Given runtime settings, when building a policy, then every field maps across."""
    values = {
        "sending.max_attempts": 4,
        "sending.backoff_base_seconds": 3.0,
        "sending.backoff_cap_seconds": 30.0,
        "sending.backoff_jitter": 0.1,
    }
    policy = BackoffPolicy.from_settings(values)
    assert policy == BackoffPolicy(
        base_seconds=3.0, cap_seconds=30.0, jitter=0.1, max_attempts=4
    )

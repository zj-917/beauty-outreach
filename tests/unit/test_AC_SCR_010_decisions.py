"""Decision rule tests."""

from __future__ import annotations

from app.domain.scoring import DecisionConfig, decide
from app.domain.settings import default_settings


def _config(**overrides: object) -> DecisionConfig:
    values = default_settings()
    values.update(overrides)
    return DecisionConfig.from_mapping(values)


def test_AC_SCR_010_default_thresholds_map_to_three_buckets() -> None:
    """Given default thresholds, then high/middle/low scores land in the right buckets."""
    config = _config()
    assert decide(90, config) == ("APPROVED", "AUTO")
    assert decide(55, config) == ("PENDING_REVIEW", "AUTO")
    assert decide(10, config) == ("DISCARDED", "AUTO")


def test_AC_SCR_010_scores_equal_to_thresholds_take_the_higher_bucket() -> None:
    """Given scores exactly at a threshold, then the higher bucket wins."""
    config = _config()
    assert decide(70, config) == ("APPROVED", "AUTO")
    assert decide(40, config) == ("PENDING_REVIEW", "AUTO")


def test_AC_SCR_010_auto_approve_disabled_downgrades_high_scores() -> None:
    """Given auto-approve off, then high scores wait for review instead."""
    config = _config(**{"screening.auto_approve_enabled": False})
    assert decide(90, config) == ("PENDING_REVIEW", "AUTO")
    assert decide(10, config) == ("DISCARDED", "AUTO")

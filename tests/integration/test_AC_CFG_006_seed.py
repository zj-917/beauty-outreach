"""Seed completeness and idempotency tests."""

from __future__ import annotations

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import Keyword, RateRule, SystemSetting, Template
from app.services.seed_service import seed_defaults

EXPECTED = {"settings": 26, "keywords": 25, "rate_rules": 2, "templates": 1}


def _counts(db: Engine) -> dict[str, int]:
    with Session(db) as session:
        settings = session.scalar(select(func.count()).select_from(SystemSetting)) or 0
        keywords = session.scalar(select(func.count()).select_from(Keyword)) or 0
        rules = session.scalar(select(func.count()).select_from(RateRule)) or 0
        templates = session.scalar(select(func.count()).select_from(Template)) or 0
    return {
        "settings": settings,
        "keywords": keywords,
        "rate_rules": rules,
        "templates": templates,
    }


def test_AC_CFG_006_seed_is_complete_and_idempotent(
    db: Engine, clock: FakeClock
) -> None:
    """Given an empty database, when seeded twice, then all defaults exist without duplicates."""
    with Session(db) as session:
        first = seed_defaults(session, clock)
    assert first == EXPECTED
    assert _counts(db) == EXPECTED

    with Session(db) as session:
        second = seed_defaults(session, clock)
    assert second == {"settings": 0, "keywords": 0, "rate_rules": 0, "templates": 0}
    assert _counts(db) == EXPECTED

    with Session(db) as session:
        high = session.get(SystemSetting, "screening.threshold_high")
        template = session.scalar(select(Template))
    assert high is not None
    assert high.value == 70
    assert template is not None
    assert (template.name, template.version, template.status) == (
        "greeting",
        1,
        "APPROVED",
    )

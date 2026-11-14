"""Seed completeness and idempotency tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.core.config import Settings
from app.main import create_app
from app.models import Keyword, RateRule, Suppression, SystemSetting, Template
from app.services.seed_service import seed_defaults

EXPECTED = {
    "settings": 26,
    "keywords": 25,
    "rate_rules": 2,
    "templates": 1,
    "suppressions": 0,
}

EXPECTED_KEYWORDS = {
    ("美容仪", "POSITIVE", 30),
    ("beauty device", "POSITIVE", 30),
    ("skincare device", "POSITIVE", 30),
    ("导入仪", "POSITIVE", 25),
    ("led mask", "POSITIVE", 25),
    ("microcurrent", "POSITIVE", 25),
    ("射频", "POSITIVE", 20),
    ("radio frequency", "POSITIVE", 20),
    ("face massager", "POSITIVE", 20),
    ("red light therapy", "POSITIVE", 20),
    ("skincare", "POSITIVE", 15),
    ("抗衰", "POSITIVE", 12),
    ("anti-aging", "POSITIVE", 12),
    ("护肤", "POSITIVE", 12),
    ("beauty", "POSITIVE", 10),
    ("美妆", "POSITIVE", 8),
    ("wholesale", "NEGATIVE", 30),
    ("dropship", "NEGATIVE", 30),
    ("批发", "NEGATIVE", 30),
    ("代购", "NEGATIVE", 30),
    ("招代理", "NEGATIVE", 30),
    ("reseller", "NEGATIVE", 25),
    ("giveaway", "NEGATIVE", 20),
    ("follow4follow", "NEGATIVE", 40),
    ("f4f", "NEGATIVE", 40),
}

EXPECTED_RULES = {
    ("global_default", "GLOBAL", 10, 5),
    ("per_recipient_default", "PER_RECIPIENT", 86400, 1),
}

EXPECTED_TEMPLATE_BODY = (
    "Hi {{name|there}}, greetings from {{brand}}! We noticed you share content "
    "about {{keyword|beauty devices}} and wanted to say hello. Feel free to reply "
    "anytime. {{optout_text}}"
)


def _counts(db: Engine) -> dict[str, int]:
    with Session(db) as session:
        settings = session.scalar(select(func.count()).select_from(SystemSetting)) or 0
        keywords = session.scalar(select(func.count()).select_from(Keyword)) or 0
        rules = session.scalar(select(func.count()).select_from(RateRule)) or 0
        templates = session.scalar(select(func.count()).select_from(Template)) or 0
        suppressions = (
            session.scalar(select(func.count()).select_from(Suppression)) or 0
        )
    return {
        "settings": settings,
        "keywords": keywords,
        "rate_rules": rules,
        "templates": templates,
        "suppressions": suppressions,
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
    assert second == {
        "settings": 0,
        "keywords": 0,
        "rate_rules": 0,
        "templates": 0,
        "suppressions": 0,
    }
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


def test_AC_CFG_006_seed_content_matches_spec(db: Engine, clock: FakeClock) -> None:
    """Given an empty database, when seeded, then keywords, rules and template match spec."""
    with Session(db) as session:
        seed_defaults(session, clock)

    with Session(db) as session:
        keywords = {
            (row.term, row.kind, row.weight) for row in session.scalars(select(Keyword))
        }
        rules = {
            (row.name, row.scope, row.window_seconds, row.max_count)
            for row in session.scalars(select(RateRule))
        }
        template = session.scalar(select(Template))

    assert keywords == EXPECTED_KEYWORDS
    assert rules == EXPECTED_RULES
    assert template is not None
    assert template.body == EXPECTED_TEMPLATE_BODY
    assert template.status == "APPROVED"


def test_AC_CFG_006_startup_seeds_only_empty_database(
    settings: Settings, clock: FakeClock
) -> None:
    """Given SEED_DEFAULTS, when started twice, then only the empty database is seeded."""
    seeded = settings.model_copy(update={"seed_defaults": True})
    headers = {"X-Admin-Token": seeded.admin_token}
    with TestClient(create_app(settings=seeded, clock=clock), headers=headers) as client:
        assert len(client.get("/api/v1/keywords").json()) == len(EXPECTED_KEYWORDS)
    with TestClient(create_app(settings=seeded, clock=clock), headers=headers) as client:
        assert len(client.get("/api/v1/keywords").json()) == len(EXPECTED_KEYWORDS)

"""Idempotent default configuration seeding."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.domain.normalize import normalize_text
from app.domain.settings import default_settings
from app.repositories import config_repo, template_repo

DEFAULT_KEYWORDS: tuple[tuple[str, str, int], ...] = (
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
)

DEFAULT_RATE_RULES: tuple[tuple[str, str, int, int], ...] = (
    ("global_default", "GLOBAL", 10, 5),
    ("per_recipient_default", "PER_RECIPIENT", 86400, 1),
)

DEFAULT_TEMPLATE_BODY = (
    "Hi {{name|there}}, greetings from {{brand}}! We noticed you share content "
    "about {{keyword|beauty devices}} and wanted to say hello. Feel free to reply "
    "anytime. {{optout_text}}"
)


def seed_defaults(session: Session, clock: Clock) -> dict[str, int]:
    """Insert missing defaults and return created row counts per kind."""
    now = clock.now()
    counts = {"settings": 0, "keywords": 0, "rate_rules": 0, "templates": 0}

    for key, value in default_settings().items():
        if config_repo.get_setting(session, key) is None:
            config_repo.upsert_setting(
                session, key, value, updated_at=now, updated_by="system:seed"
            )
            counts["settings"] += 1

    for term, kind, weight in DEFAULT_KEYWORDS:
        normalized = normalize_text(term)
        if config_repo.find_keyword(session, normalized, kind) is None:
            config_repo.create_keyword(
                session,
                term=normalized,
                kind=kind,
                weight=weight,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
            counts["keywords"] += 1

    for name, scope, window_seconds, max_count in DEFAULT_RATE_RULES:
        if config_repo.find_rate_rule_by_name(session, name) is None:
            config_repo.create_rate_rule(
                session,
                name=name,
                scope=scope,
                window_seconds=window_seconds,
                max_count=max_count,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
            counts["rate_rules"] += 1

    if template_repo.find_template(session, "greeting", 1) is None:
        template_repo.create_template(
            session,
            name="greeting",
            version=1,
            language="en",
            body=DEFAULT_TEMPLATE_BODY,
            status="APPROVED",
            created_by="system:seed",
            approved_by="system:seed",
            approved_at=now,
            created_at=now,
        )
        counts["templates"] += 1

    session.commit()
    return counts

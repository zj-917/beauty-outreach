"""Idempotent default configuration seeding."""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.security import PhoneCipher
from app.domain.lead import normalize_username
from app.domain.masking import mask_phone
from app.domain.normalize import normalize_text
from app.domain.phone import normalize_phone
from app.domain.settings import default_settings
from app.repositories import config_repo, suppression_repo, template_repo

BLACKLIST_CSV = Path(__file__).resolve().parents[2] / "data" / "mock_blacklist.csv"

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


def database_is_empty(session: Session) -> bool:
    """Return True when no settings or keywords have been stored yet."""
    return config_repo.is_empty(session)


def seed_defaults(
    session: Session, clock: Clock, *, cipher: PhoneCipher | None = None
) -> dict[str, int]:
    """Insert missing defaults and return created row counts per kind."""
    now = clock.now()
    counts = {"settings": 0, "keywords": 0, "rate_rules": 0, "templates": 0, "suppressions": 0}

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

    if cipher is not None:
        counts["suppressions"] = seed_blacklist(session, cipher, clock)

    session.commit()
    return counts


def seed_blacklist(
    session: Session, cipher: PhoneCipher, clock: Clock, *, path: Path = BLACKLIST_CSV
) -> int:
    """Import the mock blacklist / unsubscribe CSV idempotently; return new rows."""
    if not path.exists():
        return 0
    now = clock.now()
    created = 0
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            entry_type = (row.get("type") or "").strip().upper()
            if entry_type not in {"BLACKLIST", "UNSUBSCRIBE"}:
                continue
            phone = normalize_phone(row.get("phone"))
            username = normalize_username(row.get("username") or "") or None
            phone_hash = cipher.hash_phone(phone) if phone else None
            if phone_hash is not None and suppression_repo.find_by_phone(
                session, type=entry_type, phone_hash=phone_hash
            ):
                continue
            if username is not None and suppression_repo.find_by_username(
                session, type=entry_type, username=username
            ):
                continue
            if phone_hash is None and username is None:
                continue
            suppression_repo.create_suppression(
                session,
                type=entry_type,
                phone_hash=phone_hash,
                phone_masked=mask_phone(phone) if phone else None,
                username=username,
                reason=(row.get("reason") or "").strip() or "seeded blacklist",
                source="IMPORT",
                created_at=now,
                created_by="system:seed",
            )
            created += 1
    return created

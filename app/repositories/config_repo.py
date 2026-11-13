"""Persistence for keywords, rate rules and runtime settings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Keyword, RateRule, SystemSetting


@dataclass(frozen=True)
class KeywordEntry:
    """Detached keyword row."""

    id: int
    term: str
    kind: str
    weight: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RateRuleEntry:
    """Detached rate rule row."""

    id: int
    name: str
    scope: str
    window_seconds: int
    max_count: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


def list_keywords(session: Session) -> list[KeywordEntry]:
    """Return all keywords ordered by id."""
    rows = session.scalars(select(Keyword).order_by(Keyword.id)).all()
    return [_to_keyword(row) for row in rows]


def get_keyword(session: Session, keyword_id: int) -> KeywordEntry | None:
    """Return one keyword by id."""
    row = session.get(Keyword, keyword_id)
    return _to_keyword(row) if row is not None else None


def find_keyword(session: Session, term: str, kind: str) -> KeywordEntry | None:
    """Return a keyword by its unique term and kind."""
    row = session.scalar(select(Keyword).where(Keyword.term == term, Keyword.kind == kind))
    return _to_keyword(row) if row is not None else None


def enabled_keyword_count(session: Session) -> int:
    """Count keywords that participate in scoring."""
    statement = select(func.count()).select_from(Keyword).where(Keyword.enabled.is_(True))
    return session.scalar(statement) or 0


def create_keyword(
    session: Session,
    *,
    term: str,
    kind: str,
    weight: int,
    enabled: bool,
    created_at: datetime,
    updated_at: datetime,
) -> KeywordEntry:
    """Insert a keyword and flush it."""
    row = Keyword(
        term=term,
        kind=kind,
        weight=weight,
        enabled=enabled,
        created_at=created_at,
        updated_at=updated_at,
    )
    session.add(row)
    session.flush()
    return _to_keyword(row)


def update_keyword(
    session: Session,
    keyword_id: int,
    *,
    weight: int,
    enabled: bool,
    updated_at: datetime,
) -> KeywordEntry | None:
    """Update weight/enabled state for one keyword."""
    row = session.get(Keyword, keyword_id)
    if row is None:
        return None
    row.weight = weight
    row.enabled = enabled
    row.updated_at = updated_at
    session.flush()
    return _to_keyword(row)


def delete_keyword(session: Session, keyword_id: int) -> KeywordEntry | None:
    """Delete one keyword and return its previous state."""
    row = session.get(Keyword, keyword_id)
    if row is None:
        return None
    entry = _to_keyword(row)
    session.delete(row)
    session.flush()
    return entry


def list_rate_rules(session: Session) -> list[RateRuleEntry]:
    """Return all rate rules ordered by id."""
    rows = session.scalars(select(RateRule).order_by(RateRule.id)).all()
    return [_to_rate_rule(row) for row in rows]


def get_rate_rule(session: Session, rule_id: int) -> RateRuleEntry | None:
    """Return one rate rule by id."""
    row = session.get(RateRule, rule_id)
    return _to_rate_rule(row) if row is not None else None


def find_rate_rule_by_name(session: Session, name: str) -> RateRuleEntry | None:
    """Return the first rate rule with the given name."""
    row = session.scalar(select(RateRule).where(RateRule.name == name).limit(1))
    return _to_rate_rule(row) if row is not None else None


def count_enabled_rate_rules(session: Session, scope: str) -> int:
    """Count enabled rules for one scope."""
    statement = (
        select(func.count())
        .select_from(RateRule)
        .where(RateRule.scope == scope, RateRule.enabled.is_(True))
    )
    return session.scalar(statement) or 0


def create_rate_rule(
    session: Session,
    *,
    name: str,
    scope: str,
    window_seconds: int,
    max_count: int,
    enabled: bool,
    created_at: datetime,
    updated_at: datetime,
) -> RateRuleEntry:
    """Insert a rate rule and flush it."""
    row = RateRule(
        name=name,
        scope=scope,
        window_seconds=window_seconds,
        max_count=max_count,
        enabled=enabled,
        created_at=created_at,
        updated_at=updated_at,
    )
    session.add(row)
    session.flush()
    return _to_rate_rule(row)


def update_rate_rule(
    session: Session,
    rule_id: int,
    *,
    name: str,
    scope: str,
    window_seconds: int,
    max_count: int,
    enabled: bool,
    updated_at: datetime,
) -> RateRuleEntry | None:
    """Update all mutable fields of one rate rule."""
    row = session.get(RateRule, rule_id)
    if row is None:
        return None
    row.name = name
    row.scope = scope
    row.window_seconds = window_seconds
    row.max_count = max_count
    row.enabled = enabled
    row.updated_at = updated_at
    session.flush()
    return _to_rate_rule(row)


def delete_rate_rule(session: Session, rule_id: int) -> RateRuleEntry | None:
    """Delete one rate rule and return its previous state."""
    row = session.get(RateRule, rule_id)
    if row is None:
        return None
    entry = _to_rate_rule(row)
    session.delete(row)
    session.flush()
    return entry


def get_setting(session: Session, key: str) -> Any | None:
    """Return one runtime setting value."""
    row = session.get(SystemSetting, key)
    return None if row is None else row.value


def list_settings(session: Session) -> dict[str, Any]:
    """Return all stored runtime settings."""
    rows = session.scalars(select(SystemSetting)).all()
    return {row.key: row.value for row in rows}


def upsert_setting(
    session: Session,
    key: str,
    value: Any,
    *,
    updated_at: datetime,
    updated_by: str,
) -> None:
    """Insert or update one runtime setting and flush it."""
    row = session.get(SystemSetting, key)
    if row is None:
        session.add(
            SystemSetting(
                key=key,
                value=value,
                updated_at=updated_at,
                updated_by=updated_by,
            )
        )
    else:
        row.value = value
        row.updated_at = updated_at
        row.updated_by = updated_by
    session.flush()


def _to_keyword(row: Keyword) -> KeywordEntry:
    return KeywordEntry(
        id=row.id,
        term=row.term,
        kind=row.kind,
        weight=row.weight,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_rate_rule(row: RateRule) -> RateRuleEntry:
    return RateRuleEntry(
        id=row.id,
        name=row.name,
        scope=row.scope,
        window_seconds=row.window_seconds,
        max_count=row.max_count,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

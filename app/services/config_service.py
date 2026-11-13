"""Keyword, rate rule and runtime setting management."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import AppError
from app.domain.normalize import normalize_text
from app.domain.settings import (
    SettingValidationError,
    default_settings,
    validate_settings_patch,
)
from app.repositories import config_repo
from app.repositories.config_repo import KeywordEntry, RateRuleEntry
from app.services.audit_service import AuditService

_KINDS = {"POSITIVE", "NEGATIVE"}
_SCOPES = {"GLOBAL", "PER_RECIPIENT"}
_MAX_ENABLED_KEYWORDS = 500


def _normalize_term(term: object) -> str:
    if not isinstance(term, str):
        raise AppError("VALIDATION_ERROR", "term must be a string")
    normalized = normalize_text(term)
    if not 1 <= len(normalized) <= 60:
        raise AppError("VALIDATION_ERROR", "term must be 1-60 characters")
    return normalized


def _require_kind(kind: object) -> None:
    if kind not in _KINDS:
        raise AppError("VALIDATION_ERROR", "kind must be POSITIVE or NEGATIVE")


def _require_weight(weight: object) -> None:
    valid = isinstance(weight, int) and not isinstance(weight, bool) and 1 <= weight <= 50
    if not valid:
        raise AppError("VALIDATION_ERROR", "weight must be between 1 and 50")


def _require_bool(value: object, name: str) -> None:
    if not isinstance(value, bool):
        raise AppError("VALIDATION_ERROR", f"{name} must be a boolean")


def _require_rate_rule_values(
    name: object,
    scope: object,
    window_seconds: object,
    max_count: object,
    enabled: object,
) -> None:
    if not isinstance(name, str) or not 1 <= len(name) <= 80:
        raise AppError("VALIDATION_ERROR", "name must be 1-80 characters")
    if scope not in _SCOPES:
        raise AppError("VALIDATION_ERROR", "scope must be GLOBAL or PER_RECIPIENT")
    if (
        not isinstance(window_seconds, int)
        or isinstance(window_seconds, bool)
        or window_seconds < 1
    ):
        raise AppError("VALIDATION_ERROR", "window_seconds must be at least 1")
    if not isinstance(max_count, int) or isinstance(max_count, bool) or max_count < 1:
        raise AppError("VALIDATION_ERROR", "max_count must be at least 1")
    _require_bool(enabled, "enabled")


def _keyword_snapshot(entry: KeywordEntry) -> dict[str, Any]:
    return {
        "term": entry.term,
        "kind": entry.kind,
        "weight": entry.weight,
        "enabled": entry.enabled,
    }


def _rate_rule_snapshot(entry: RateRuleEntry) -> dict[str, Any]:
    return {
        "name": entry.name,
        "scope": entry.scope,
        "window_seconds": entry.window_seconds,
        "max_count": entry.max_count,
        "enabled": entry.enabled,
    }


class ConfigService:
    """Apply configuration changes atomically with audit records."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._audit = AuditService(clock)

    def list_keywords(self, session: Session) -> list[KeywordEntry]:
        """Return all keywords."""
        return config_repo.list_keywords(session)

    def create_keyword(
        self,
        session: Session,
        *,
        term: str,
        kind: str,
        weight: int,
        enabled: bool,
        actor: str,
        request_id: str | None = None,
    ) -> KeywordEntry:
        """Create a normalized keyword and audit it."""
        normalized = _normalize_term(term)
        _require_kind(kind)
        _require_weight(weight)
        _require_bool(enabled, "enabled")
        if config_repo.find_keyword(session, normalized, kind) is not None:
            raise AppError(
                "CONFLICT",
                "Keyword already exists",
                details={"term": normalized, "kind": kind},
            )
        if enabled and config_repo.enabled_keyword_count(session) >= _MAX_ENABLED_KEYWORDS:
            raise AppError("VALIDATION_ERROR", "Maximum number of enabled keywords reached")
        now = self._clock.now()
        entry = config_repo.create_keyword(
            session,
            term=normalized,
            kind=kind,
            weight=weight,
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )
        self._audit.record(
            session,
            actor=actor,
            action="KEYWORD_CREATED",
            entity_type="keyword",
            entity_id=str(entry.id),
            after=_keyword_snapshot(entry),
            request_id=request_id,
        )
        session.commit()
        return entry

    def update_keyword(
        self,
        session: Session,
        keyword_id: int,
        *,
        weight: int | None = None,
        enabled: bool | None = None,
        actor: str,
        request_id: str | None = None,
    ) -> KeywordEntry:
        """Update weight or enabled state of one keyword."""
        existing = config_repo.get_keyword(session, keyword_id)
        if existing is None:
            raise AppError("NOT_FOUND", "Keyword not found")
        if weight is None and enabled is None:
            return existing
        new_weight = existing.weight if weight is None else weight
        new_enabled = existing.enabled if enabled is None else enabled
        _require_weight(new_weight)
        _require_bool(new_enabled, "enabled")
        if (
            not existing.enabled
            and new_enabled
            and config_repo.enabled_keyword_count(session) >= _MAX_ENABLED_KEYWORDS
        ):
            raise AppError("VALIDATION_ERROR", "Maximum number of enabled keywords reached")
        updated = config_repo.update_keyword(
            session,
            keyword_id,
            weight=new_weight,
            enabled=new_enabled,
            updated_at=self._clock.now(),
        )
        if updated is None:
            raise AppError("NOT_FOUND", "Keyword not found")
        self._audit.record(
            session,
            actor=actor,
            action="KEYWORD_UPDATED",
            entity_type="keyword",
            entity_id=str(keyword_id),
            before={"weight": existing.weight, "enabled": existing.enabled},
            after={"weight": new_weight, "enabled": new_enabled},
            request_id=request_id,
        )
        session.commit()
        return updated

    def delete_keyword(
        self,
        session: Session,
        keyword_id: int,
        *,
        actor: str,
        request_id: str | None = None,
    ) -> None:
        """Delete one keyword and audit its previous state."""
        existing = config_repo.delete_keyword(session, keyword_id)
        if existing is None:
            raise AppError("NOT_FOUND", "Keyword not found")
        self._audit.record(
            session,
            actor=actor,
            action="KEYWORD_DELETED",
            entity_type="keyword",
            entity_id=str(keyword_id),
            before=_keyword_snapshot(existing),
            request_id=request_id,
        )
        session.commit()

    def list_rate_rules(self, session: Session) -> list[RateRuleEntry]:
        """Return all rate rules."""
        return config_repo.list_rate_rules(session)

    def create_rate_rule(
        self,
        session: Session,
        *,
        name: str,
        scope: str,
        window_seconds: int,
        max_count: int,
        enabled: bool,
        actor: str,
        request_id: str | None = None,
    ) -> RateRuleEntry:
        """Create a rate rule and audit it."""
        _require_rate_rule_values(name, scope, window_seconds, max_count, enabled)
        now = self._clock.now()
        entry = config_repo.create_rate_rule(
            session,
            name=name,
            scope=scope,
            window_seconds=window_seconds,
            max_count=max_count,
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )
        self._audit.record(
            session,
            actor=actor,
            action="RATE_RULE_CREATED",
            entity_type="rate_rule",
            entity_id=str(entry.id),
            after=_rate_rule_snapshot(entry),
            request_id=request_id,
        )
        session.commit()
        return entry

    def update_rate_rule(
        self,
        session: Session,
        rule_id: int,
        *,
        name: str | None = None,
        scope: str | None = None,
        window_seconds: int | None = None,
        max_count: int | None = None,
        enabled: bool | None = None,
        actor: str,
        request_id: str | None = None,
    ) -> RateRuleEntry:
        """Update one rate rule while keeping every scope covered."""
        existing = config_repo.get_rate_rule(session, rule_id)
        if existing is None:
            raise AppError("NOT_FOUND", "Rate rule not found")
        if all(
            value is None
            for value in (name, scope, window_seconds, max_count, enabled)
        ):
            return existing
        new_name = existing.name if name is None else name
        new_scope = existing.scope if scope is None else scope
        new_window = existing.window_seconds if window_seconds is None else window_seconds
        new_max = existing.max_count if max_count is None else max_count
        new_enabled = existing.enabled if enabled is None else enabled
        _require_rate_rule_values(new_name, new_scope, new_window, new_max, new_enabled)
        if existing.enabled and (not new_enabled or new_scope != existing.scope):
            remaining = config_repo.count_enabled_rate_rules(session, existing.scope)
            if remaining <= 1:
                raise AppError(
                    "CFG_LAST_RATE_RULE",
                    "At least one enabled rule per scope is required",
                    details={"scope": existing.scope},
                )
        updated = config_repo.update_rate_rule(
            session,
            rule_id,
            name=new_name,
            scope=new_scope,
            window_seconds=new_window,
            max_count=new_max,
            enabled=new_enabled,
            updated_at=self._clock.now(),
        )
        if updated is None:
            raise AppError("NOT_FOUND", "Rate rule not found")
        self._audit.record(
            session,
            actor=actor,
            action="RATE_RULE_UPDATED",
            entity_type="rate_rule",
            entity_id=str(rule_id),
            before=_rate_rule_snapshot(existing),
            after=_rate_rule_snapshot(updated),
            request_id=request_id,
        )
        session.commit()
        return updated

    def delete_rate_rule(
        self,
        session: Session,
        rule_id: int,
        *,
        actor: str,
        request_id: str | None = None,
    ) -> None:
        """Delete one rate rule while keeping every scope covered."""
        existing = config_repo.get_rate_rule(session, rule_id)
        if existing is None:
            raise AppError("NOT_FOUND", "Rate rule not found")
        if existing.enabled:
            remaining = config_repo.count_enabled_rate_rules(session, existing.scope)
            if remaining <= 1:
                raise AppError(
                    "CFG_LAST_RATE_RULE",
                    "At least one enabled rule per scope is required",
                    details={"scope": existing.scope},
                )
        deleted = config_repo.delete_rate_rule(session, rule_id)
        if deleted is None:
            raise AppError("NOT_FOUND", "Rate rule not found")
        self._audit.record(
            session,
            actor=actor,
            action="RATE_RULE_DELETED",
            entity_type="rate_rule",
            entity_id=str(rule_id),
            before=_rate_rule_snapshot(deleted),
            request_id=request_id,
        )
        session.commit()

    def get_settings(self, session: Session) -> dict[str, Any]:
        """Return registry defaults merged with stored overrides."""
        values = default_settings()
        values.update(config_repo.list_settings(session))
        return values

    def update_settings(
        self,
        session: Session,
        updates: dict[str, Any],
        *,
        actor: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Validate and apply a partial settings update atomically."""
        current = self.get_settings(session)
        try:
            normalized = validate_settings_patch(current, updates)
        except SettingValidationError as exc:
            raise AppError(
                "VALIDATION_ERROR", str(exc), details=exc.details
            ) from exc
        now = self._clock.now()
        for key, value in normalized.items():
            old = current.get(key)
            if old == value:
                continue
            config_repo.upsert_setting(
                session, key, value, updated_at=now, updated_by=actor
            )
            self._audit.record(
                session,
                actor=actor,
                action="SETTING_UPDATED",
                entity_type="system_setting",
                entity_id=key,
                before={"value": old},
                after={"value": value},
                request_id=request_id,
            )
        session.commit()
        return self.get_settings(session)

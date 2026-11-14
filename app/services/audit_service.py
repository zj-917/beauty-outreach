"""Audit writing, hash chaining and querying."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.domain.masking import redact
from app.repositories import audit_repo
from app.repositories.audit_repo import AuditEntry
from app.schemas.common import iso_z

GENESIS_HASH = "GENESIS"


@dataclass(frozen=True)
class ChainCheck:
    """Result of verifying the audit hash chain."""

    ok: bool
    count: int | None = None
    first_broken_id: int | None = None


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_payload(prev_hash: str, payload: dict[str, Any]) -> str:
    material = prev_hash + _canonical_json(payload)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class AuditService:
    """Append audit records in the caller's transaction and read them back."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def record(
        self,
        session: Session,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        """Append one redacted audit row; the caller owns commit and rollback."""
        ts = self._clock.now().astimezone(UTC)
        redacted_before = redact(before) if before is not None else None
        redacted_after = redact(after) if after is not None else None
        prev_hash = audit_repo.last_hash(session) or GENESIS_HASH
        payload = {
            "ts": iso_z(ts),
            "actor": actor,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "before": redacted_before,
            "after": redacted_after,
            "request_id": request_id,
        }
        digest = _hash_payload(prev_hash, payload)
        audit_repo.append(
            session,
            ts=ts,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=redacted_before,
            after=redacted_after,
            request_id=request_id,
            prev_hash=prev_hash,
            hash_value=digest,
        )

    def list_logs(
        self,
        session: Session,
        *,
        actor: str | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AuditEntry], int]:
        """Return one page of audit entries matching the filters."""
        return audit_repo.list_entries(
            session,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            from_ts=_as_utc(from_ts),
            to_ts=_as_utc(to_ts),
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    def verify_chain(self, session: Session) -> ChainCheck:
        """Recompute the hash chain and report the first broken row."""
        entries = audit_repo.all_entries(session)
        expected_prev = GENESIS_HASH
        for entry in entries:
            if entry.hash is None or entry.prev_hash != expected_prev:
                return ChainCheck(ok=False, first_broken_id=entry.id)
            payload = {
                "ts": iso_z(entry.ts),
                "actor": entry.actor,
                "action": entry.action,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "before": entry.before,
                "after": entry.after,
                "request_id": entry.request_id,
            }
            if _hash_payload(expected_prev, payload) != entry.hash:
                return ChainCheck(ok=False, first_broken_id=entry.id)
            expected_prev = entry.hash
        return ChainCheck(ok=True, count=len(entries))

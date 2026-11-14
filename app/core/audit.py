"""Structural interface for the audit writer injected into the engine."""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session


class AuditWriter(Protocol):
    """Minimal audit surface the engine needs for state-change records."""

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
        """Append one audit row inside the caller's transaction."""
        ...

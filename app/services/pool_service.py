"""Goal-pool queries and manual lead review."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import AppError
from app.repositories import lead_repo
from app.repositories.lead_repo import LeadEntry
from app.services.audit_service import AuditService

_DECISIONS = frozenset({"APPROVE", "REJECT"})
_TRANSITIONS: dict[str, dict[str, str]] = {
    "PENDING_REVIEW": {"APPROVE": "APPROVED", "REJECT": "REJECTED"},
    "APPROVED": {"APPROVE": "APPROVED", "REJECT": "REJECTED"},
    "REJECTED": {"APPROVE": "APPROVED", "REJECT": "REJECTED"},
    "DISCARDED": {"APPROVE": "APPROVED", "REJECT": "REJECTED"},
}
_NOTE_REQUIRED = frozenset({("REJECTED", "APPROVE"), ("DISCARDED", "APPROVE")})


@dataclass(frozen=True)
class ReviewCommand:
    """One lead review requested inside a bulk call."""

    lead_id: int
    decision: str
    note: str | None = None


@dataclass(frozen=True)
class ReviewOutcome:
    """Per-item result of a bulk review."""

    lead_id: int
    ok: bool
    error_code: str | None = None
    error_message: str | None = None


class PoolService:
    """Query the approved pool and apply manual review decisions."""

    def __init__(self, clock: Clock, audit: AuditService | None = None) -> None:
        self._clock = clock
        self._audit = audit or AuditService(clock)

    def list_pool(
        self, session: Session, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[LeadEntry], int]:
        """Return one page of APPROVED leads, highest score first."""
        return lead_repo.list_pool(
            session, offset=(page - 1) * page_size, limit=page_size
        )

    def review(
        self,
        session: Session,
        lead_id: int,
        *,
        decision: str,
        note: str | None,
        operator: str,
        request_id: str | None = None,
        commit: bool = True,
    ) -> LeadEntry:
        """Apply one manual decision, record review metadata and append LEAD_REVIEWED."""
        lead = lead_repo.get_lead(session, lead_id)
        if lead is None:
            raise AppError("NOT_FOUND", "Lead not found")
        target, review_note = self._target(lead, decision, note)
        before = {"status": lead.status, "note": lead.review_note}
        reviewed_at = self._clock.now()
        lead_repo.update_review(
            session,
            lead_id,
            status=target,
            decision_source="MANUAL",
            reviewed_by=operator,
            reviewed_at=reviewed_at,
            review_note=review_note,
        )
        self._audit.record(
            session,
            actor=operator,
            action="LEAD_REVIEWED",
            entity_type="lead",
            entity_id=str(lead_id),
            before=before,
            after={"status": target, "note": review_note, "decision": decision},
            request_id=request_id,
        )
        if commit:
            session.commit()
        updated = lead_repo.get_lead(session, lead_id)
        assert updated is not None
        return updated

    def review_bulk(
        self,
        session: Session,
        commands: list[ReviewCommand],
        *,
        operator: str,
        request_id: str | None = None,
    ) -> list[ReviewOutcome]:
        """Review each command independently; one failure never stops later items."""
        outcomes: list[ReviewOutcome] = []
        for command in commands:
            try:
                self.review(
                    session,
                    command.lead_id,
                    decision=command.decision,
                    note=command.note,
                    operator=operator,
                    request_id=request_id,
                )
            except AppError as exc:
                session.rollback()
                outcomes.append(
                    ReviewOutcome(
                        lead_id=command.lead_id,
                        ok=False,
                        error_code=exc.code,
                        error_message=exc.message,
                    )
                )
            else:
                outcomes.append(ReviewOutcome(lead_id=command.lead_id, ok=True))
        return outcomes

    @staticmethod
    def _target(
        lead: LeadEntry, decision: str, note: str | None
    ) -> tuple[str, str | None]:
        """Return the target status and note for one review, or raise."""
        if decision not in _DECISIONS:
            raise AppError(
                "VALIDATION_ERROR", "decision must be APPROVE or REJECT"
            )
        if lead.status == "NEW":
            raise AppError(
                "CONFLICT",
                "Lead must be screened before review",
                details={"current_status": lead.status},
            )
        targets = _TRANSITIONS.get(lead.status)
        if targets is None:
            raise AppError(
                "CONFLICT",
                "Lead status cannot be reviewed",
                details={"current_status": lead.status},
            )
        target = targets[decision]
        cleaned = (note or "").strip() or None
        if (lead.status, decision) in _NOTE_REQUIRED and cleaned is None:
            raise AppError(
                "VALIDATION_ERROR",
                "note is required when restoring a lead to the pool",
                details={"field": "note"},
            )
        if target == lead.status and cleaned is None:
            cleaned = lead.review_note
        return target, cleaned

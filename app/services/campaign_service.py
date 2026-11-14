"""Campaign creation, target snapshot and state-machine control."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import AppError
from app.domain.state import Transition, transition
from app.repositories import campaign_repo, lead_repo, template_repo
from app.repositories.campaign_repo import CampaignEntry, ItemEntry
from app.services.audit_service import AuditService

_SUCCESS_STATUSES = ("SENT", "DELIVERED", "READ")
_IN_PROGRESS_STATUSES = ("PENDING", "SENDING", "RETRY_WAIT")


@dataclass(frozen=True)
class CampaignReport:
    """One campaign task with its item status summary."""

    campaign: CampaignEntry
    counts: dict[str, Any]


class CampaignService:
    """Create snapshot campaigns and drive their state machine."""

    def __init__(self, clock: Clock, audit: AuditService | None = None) -> None:
        self._clock = clock
        self._audit = audit or AuditService(clock)

    def create(
        self,
        session: Session,
        *,
        name: str,
        template_id: int,
        min_score: int | None,
        batch_id: int | None,
        lead_ids: list[int] | None,
        operator: str,
        request_id: str | None = None,
    ) -> CampaignReport:
        """Create a DRAFT task plus PENDING items for every selected pool lead."""
        clean_name = self._clean_name(name)
        template = template_repo.get_template(session, template_id)
        if template is None:
            raise AppError("NOT_FOUND", "Template not found")
        if template.status != "APPROVED":
            raise AppError(
                "TEMPLATE_NOT_APPROVED",
                "Template is not approved",
                details={"template_id": template_id, "template_status": template.status},
            )
        selection = {
            "min_score": min_score,
            "batch_id": batch_id,
            "lead_ids": lead_ids,
        }
        targets = lead_repo.list_pool_targets(
            session, min_score=min_score, batch_id=batch_id, lead_ids=lead_ids
        )
        if not targets:
            raise AppError(
                "CAMPAIGN_EMPTY_TARGET",
                "Selection matched no approved lead",
                details={"selection": selection},
            )
        now = self._clock.now()
        campaign = campaign_repo.create_campaign(
            session,
            name=clean_name,
            template_id=template.id,
            selection=selection,
            total_items=len(targets),
            created_by=operator,
            created_at=now,
        )
        for lead in targets:
            campaign_repo.insert_item(
                session,
                task_id=campaign.id,
                lead_id=lead.id,
                idempotency_key=self.idempotency_key(campaign.id, lead.id, template.id),
                phone_hash=lead.phone_hash,
                phone_masked=lead.phone_masked,
                created_at=now,
                updated_at=now,
            )
        self._audit.record(
            session,
            actor=operator,
            action="CAMPAIGN_CREATED",
            entity_type="campaign",
            entity_id=str(campaign.id),
            before=None,
            after={
                "name": clean_name,
                "template_id": template.id,
                "status": "DRAFT",
                "selection": selection,
                "total_items": len(targets),
            },
            request_id=request_id,
        )
        session.commit()
        return CampaignReport(
            campaign=campaign,
            counts=_summary(len(targets), {"PENDING": len(targets)}),
        )

    def list_campaigns(
        self, session: Session, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[CampaignReport], int]:
        """Return one page of campaigns with per-task summary counts."""
        entries, total = campaign_repo.list_campaigns(
            session, offset=(page - 1) * page_size, limit=page_size
        )
        counts = campaign_repo.counts_for_tasks(session, [entry.id for entry in entries])
        reports = [
            CampaignReport(
                campaign=entry,
                counts=_summary(entry.total_items, counts[entry.id]),
            )
            for entry in entries
        ]
        return reports, total

    def get_campaign(self, session: Session, campaign_id: int) -> CampaignReport:
        """Return one campaign with its counts or raise NOT_FOUND."""
        campaign = self._require(session, campaign_id)
        counts = campaign_repo.counts_for_tasks(session, [campaign.id])[campaign.id]
        return CampaignReport(
            campaign=campaign, counts=_summary(campaign.total_items, counts)
        )

    def list_items(
        self,
        session: Session,
        campaign_id: int,
        *,
        status: str | None,
        reason_code: str | None,
        q: str | None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ItemEntry], int]:
        """Return one page of a campaign's items after checking it exists."""
        self._require(session, campaign_id)
        return campaign_repo.list_items(
            session,
            campaign_id,
            status=status,
            reason_code=reason_code,
            q=q,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    def start(
        self,
        session: Session,
        campaign_id: int,
        *,
        operator: str,
        provider_available: bool,
        request_id: str | None = None,
    ) -> CampaignEntry:
        """Move DRAFT to RUNNING after the Q-11 prechecks; RUNNING repeats are no-ops."""
        campaign = self._require(session, campaign_id)
        decision = self._transition(campaign, "start")
        if decision.noop:
            return campaign
        template = template_repo.get_template(session, campaign.template_id)
        if template is None or template.status != "APPROVED":
            raise AppError(
                "TEMPLATE_NOT_APPROVED",
                "Template is not approved",
                details={"template_id": campaign.template_id},
            )
        if not campaign_repo.has_open_items(session, campaign_id):
            raise AppError(
                "CAMPAIGN_EMPTY_TARGET",
                "Campaign has no open task item",
                details={"campaign_id": campaign_id},
            )
        if not provider_available:
            raise AppError(
                "PROVIDER_NOT_ENABLED", "Messenger provider is not enabled"
            )
        now = self._clock.now()
        campaign_repo.update_campaign(
            session, campaign_id, status="RUNNING", started_at=now, updated_at=now
        )
        self._audit.record(
            session,
            actor=operator,
            action="CAMPAIGN_STARTED",
            entity_type="campaign",
            entity_id=str(campaign_id),
            before={"status": campaign.status},
            after={"status": "RUNNING"},
            request_id=request_id,
        )
        session.commit()
        return self._require(session, campaign_id)

    def pause(
        self,
        session: Session,
        campaign_id: int,
        *,
        operator: str,
        request_id: str | None = None,
    ) -> CampaignEntry:
        """Move RUNNING to PAUSED with pause_reason=MANUAL."""
        campaign = self._require(session, campaign_id)
        self._transition(campaign, "pause")
        now = self._clock.now()
        campaign_repo.update_campaign(
            session,
            campaign_id,
            status="PAUSED",
            pause_reason="MANUAL",
            paused_at=now,
            updated_at=now,
        )
        self._audit.record(
            session,
            actor=operator,
            action="CAMPAIGN_PAUSED",
            entity_type="campaign",
            entity_id=str(campaign_id),
            before={"status": campaign.status},
            after={"status": "PAUSED", "pause_reason": "MANUAL"},
            request_id=request_id,
        )
        session.commit()
        return self._require(session, campaign_id)

    def resume(
        self,
        session: Session,
        campaign_id: int,
        *,
        operator: str,
        request_id: str | None = None,
    ) -> CampaignEntry:
        """Move PAUSED to RUNNING and clear the circuit-breaker counter."""
        campaign = self._require(session, campaign_id)
        self._transition(campaign, "resume")
        now = self._clock.now()
        campaign_repo.update_campaign(
            session,
            campaign_id,
            status="RUNNING",
            pause_reason=None,
            consecutive_failures=0,
            updated_at=now,
        )
        self._audit.record(
            session,
            actor=operator,
            action="CAMPAIGN_RESUMED",
            entity_type="campaign",
            entity_id=str(campaign_id),
            before={
                "status": campaign.status,
                "consecutive_failures": campaign.consecutive_failures,
            },
            after={"status": "RUNNING", "consecutive_failures": 0},
            request_id=request_id,
        )
        session.commit()
        return self._require(session, campaign_id)

    def cancel(
        self,
        session: Session,
        campaign_id: int,
        *,
        operator: str,
        request_id: str | None = None,
    ) -> CampaignEntry:
        """Move any non-terminal task to CANCELLED and skip its open items."""
        campaign = self._require(session, campaign_id)
        self._transition(campaign, "cancel")
        now = self._clock.now()
        campaign_repo.update_campaign(
            session, campaign_id, status="CANCELLED", finished_at=now, updated_at=now
        )
        skipped = campaign_repo.skip_open_items(
            session, campaign_id, reason_code="TASK_CANCELLED", updated_at=now
        )
        self._audit.record(
            session,
            actor=operator,
            action="CAMPAIGN_CANCELLED",
            entity_type="campaign",
            entity_id=str(campaign_id),
            before={"status": campaign.status},
            after={"status": "CANCELLED", "skipped_items": skipped},
            request_id=request_id,
        )
        session.commit()
        return self._require(session, campaign_id)

    @staticmethod
    def idempotency_key(task_id: int, lead_id: int, template_id: int) -> str:
        """Return the global idempotency key for one item."""
        material = f"{task_id}:{lead_id}:{template_id}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _require(self, session: Session, campaign_id: int) -> CampaignEntry:
        campaign = campaign_repo.get_campaign(session, campaign_id)
        if campaign is None:
            raise AppError("NOT_FOUND", "Campaign not found")
        return campaign

    @staticmethod
    def _transition(campaign: CampaignEntry, action: str) -> Transition:
        decision = transition(campaign.status, action)
        if decision is None:
            raise AppError(
                "CAMPAIGN_INVALID_STATE",
                "Campaign status does not allow this action",
                details={"status": campaign.status, "action": action},
            )
        return decision

    @staticmethod
    def _clean_name(name: str) -> str:
        clean = name.strip()
        if not clean:
            raise AppError(
                "VALIDATION_ERROR", "name must not be blank", details={"field": "name"}
            )
        return clean


def _summary(total_items: int, by_status: dict[str, int]) -> dict[str, Any]:
    """Build the CAMP-029 / STAT-007 summary block from per-status counts."""
    return {
        "total": total_items,
        "success": sum(by_status.get(status, 0) for status in _SUCCESS_STATUSES),
        "failed": by_status.get("FAILED", 0),
        "skipped": by_status.get("SKIPPED", 0),
        "in_progress": sum(
            by_status.get(status, 0) for status in _IN_PROGRESS_STATUSES
        ),
        "by_status": dict(by_status),
    }

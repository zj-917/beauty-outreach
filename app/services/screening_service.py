"""Screening runs: score machine-decided leads and record one audit row."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.domain.scoring import (
    DecisionConfig,
    KeywordRule,
    LeadFields,
    ScreeningConfig,
    decide,
    score_lead,
)
from app.repositories import config_repo, lead_repo
from app.services.audit_service import AuditService
from app.services.config_service import ConfigService


@dataclass(frozen=True)
class ScreeningReport:
    """Counters returned by one screening run."""

    processed: int
    approved: int
    pending_review: int
    discarded: int
    unchanged: int
    warning: str | None = None


class ScreeningService:
    """Apply the rule scorer to NEW, PENDING_REVIEW and DISCARDED leads."""

    def __init__(self, clock: Clock, audit: AuditService | None = None) -> None:
        self._clock = clock
        self._audit = audit or AuditService(clock)

    def run(
        self,
        session: Session,
        *,
        batch_id: int | None = None,
        lead_ids: list[int] | None = None,
        operator: str,
        request_id: str | None = None,
    ) -> ScreeningReport:
        """Rescore the selected leads and write exactly one LEAD_SCREENING_RUN audit."""
        settings = ConfigService(self._clock).get_settings(session)
        rules = [
            KeywordRule(term=entry.term, kind=entry.kind, weight=entry.weight)
            for entry in config_repo.list_keywords(session)
            if entry.enabled
        ]
        score_config = ScreeningConfig.from_mapping(settings)
        decision_config = DecisionConfig.from_mapping(settings)
        leads = lead_repo.list_for_screening(
            session, batch_id=batch_id, lead_ids=lead_ids
        )
        now = self._clock.now()
        counters = {"approved": 0, "pending_review": 0, "discarded": 0, "unchanged": 0}
        for lead in leads:
            result = score_lead(
                LeadFields(
                    username=lead.username,
                    display_name=lead.display_name,
                    bio=lead.bio,
                    region=lead.region,
                    language=lead.language,
                ),
                rules,
                score_config,
            )
            status, source = decide(result.score, decision_config)
            if status == lead.status:
                counters["unchanged"] += 1
            counters[status.lower()] += 1
            lead_repo.update_screening(
                session,
                lead.id,
                score=result.score,
                reasons=[
                    {"code": reason.code, "detail": reason.detail, "delta": reason.delta}
                    for reason in result.reasons
                ],
                top_keyword=result.top_keyword,
                status=status,
                decision_source=source,
                updated_at=now,
            )
        warning = None if rules else "NO_ENABLED_KEYWORDS"
        report = ScreeningReport(
            processed=len(leads),
            approved=counters["approved"],
            pending_review=counters["pending_review"],
            discarded=counters["discarded"],
            unchanged=counters["unchanged"],
            warning=warning,
        )
        after = {
            "processed": report.processed,
            "approved": report.approved,
            "pending_review": report.pending_review,
            "discarded": report.discarded,
            "unchanged": report.unchanged,
            "threshold_high": decision_config.threshold_high,
            "threshold_low": decision_config.threshold_low,
            "auto_approve_enabled": decision_config.auto_approve_enabled,
        }
        if warning is not None:
            after["warning"] = warning
        if batch_id is not None:
            after["batch_id"] = batch_id
            entity_type = "lead_batch"
            entity_id = str(batch_id)
        elif lead_ids is not None:
            after["selected"] = len(lead_ids)
            entity_type = "lead"
            entity_id = "selected"
        else:
            entity_type = "lead"
            entity_id = "all"
        self._audit.record(
            session,
            actor=operator,
            action="LEAD_SCREENING_RUN",
            entity_type=entity_type,
            entity_id=entity_id,
            after=after,
            request_id=request_id,
        )
        session.commit()
        return report

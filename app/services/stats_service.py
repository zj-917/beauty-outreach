"""Task and global statistics (§7 of the config-stats spec)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import AppError
from app.domain.state import CAMPAIGN_STATUSES
from app.repositories import campaign_repo, stats_repo
from app.repositories.campaign_repo import ITEM_STATUSES

SUCCESS_STATUSES = ("SENT", "DELIVERED", "READ")
IN_PROGRESS_STATUSES = ("PENDING", "SENDING", "RETRY_WAIT")
LEAD_STATUSES = ("NEW", "PENDING_REVIEW", "APPROVED", "REJECTED", "DISCARDED")
SUPPRESSION_TYPES = ("BLACKLIST", "UNSUBSCRIBE")
CONSENT_STATUSES = ("GRANTED", "REVOKED")


@dataclass(frozen=True)
class TaskStats:
    """One campaign task's result statistics at read time."""

    task_id: int
    status: str
    total: int
    by_status: dict[str, int]
    success: int
    failed: int
    skipped: int
    in_progress: int
    success_rate: float | None
    skip_reasons: dict[str, int]
    failure_reasons: dict[str, int]
    attempts_histogram: dict[int, int]
    retry_total: int
    started_at: datetime | None
    finished_at: datetime | None
    elapsed_seconds: float | None


@dataclass(frozen=True)
class Overview:
    """System-wide counts shown on the dashboard."""

    leads_by_status: dict[str, int]
    pool_size: int
    campaigns_by_status: dict[str, int]
    accepted_last_24h: int
    suppressions_by_type: dict[str, int]
    consents_by_status: dict[str, int]


def item_summary(total_items: int, by_status: dict[str, int]) -> dict[str, Any]:
    """Build the STAT-007 summary block shared by lists, detail and stats."""
    counts = {status: by_status.get(status, 0) for status in ITEM_STATUSES}
    return {
        "total": total_items,
        "success": sum(counts[status] for status in SUCCESS_STATUSES),
        "failed": counts["FAILED"],
        "skipped": counts["SKIPPED"],
        "in_progress": sum(counts[status] for status in IN_PROGRESS_STATUSES),
        "by_status": counts,
    }


def success_rate(success: int, failed: int) -> float | None:
    """Return success / (success + failed), or None when nothing is decided."""
    decided = success + failed
    if decided == 0:
        return None
    return round(success / decided, 4)


def _zero_filled(counts: dict[str, int], statuses: tuple[str, ...]) -> dict[str, int]:
    return {status: counts.get(status, 0) for status in statuses}


class StatsService:
    """Compute statistics live inside the caller's read transaction."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def task_stats(self, session: Session, campaign_id: int) -> TaskStats:
        """Return the current result statistics of one campaign."""
        campaign = campaign_repo.get_campaign(session, campaign_id)
        if campaign is None:
            raise AppError("NOT_FOUND", "Campaign not found")
        counts = campaign_repo.counts_for_tasks(session, [campaign_id])[campaign_id]
        summary = item_summary(campaign.total_items, counts)
        histogram = stats_repo.attempts_histogram(session, campaign_id)
        retry_total = sum(
            (attempts - 1) * count for attempts, count in histogram.items() if attempts >= 1
        )
        return TaskStats(
            task_id=campaign_id,
            status=campaign.status,
            total=summary["total"],
            by_status=summary["by_status"],
            success=summary["success"],
            failed=summary["failed"],
            skipped=summary["skipped"],
            in_progress=summary["in_progress"],
            success_rate=success_rate(summary["success"], summary["failed"]),
            skip_reasons=stats_repo.reason_counts(session, campaign_id, "SKIPPED"),
            failure_reasons=stats_repo.reason_counts(session, campaign_id, "FAILED"),
            attempts_histogram=histogram,
            retry_total=retry_total,
            started_at=campaign.started_at,
            finished_at=campaign.finished_at,
            elapsed_seconds=self._elapsed(campaign.started_at, campaign.finished_at),
        )

    def overview(self, session: Session) -> Overview:
        """Return the global counts used by the dashboard."""
        leads = _zero_filled(stats_repo.lead_status_counts(session), LEAD_STATUSES)
        since = self._clock.now() - timedelta(hours=24)
        return Overview(
            leads_by_status=leads,
            pool_size=leads["APPROVED"],
            campaigns_by_status=_zero_filled(
                stats_repo.campaign_status_counts(session), CAMPAIGN_STATUSES
            ),
            accepted_last_24h=stats_repo.accepted_count_since(session, since),
            suppressions_by_type=_zero_filled(
                stats_repo.suppression_type_counts(session), SUPPRESSION_TYPES
            ),
            consents_by_status=_zero_filled(
                stats_repo.consent_status_counts(session), CONSENT_STATUSES
            ),
        )

    def _elapsed(
        self, started_at: datetime | None, finished_at: datetime | None
    ) -> float | None:
        if started_at is None:
            return None
        end = finished_at or self._clock.now()
        return round((end - started_at).total_seconds(), 1)

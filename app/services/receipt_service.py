"""Apply provider delivery receipts (campaign.md §8)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.domain.masking import redact_text
from app.providers.messenger.base import Messenger, Receipt
from app.repositories import campaign_repo, send_log_repo

logger = logging.getLogger(__name__)

_STATUS_RANK = {"SENT": 1, "DELIVERED": 2, "READ": 3}


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ReceiptService:
    """Advance item states from delivery receipts; never move them backwards."""

    def __init__(
        self,
        clock: Clock,
        *,
        messenger: Messenger | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self._clock = clock
        self._messenger = messenger
        self._session_factory = session_factory

    def apply(
        self,
        session: Session,
        *,
        provider_message_id: str,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        timestamp: datetime | None = None,
    ) -> bool:
        """Apply one receipt; returns False for unknown, duplicate or stale events."""
        item = campaign_repo.find_item_by_provider_message_id(
            session, provider_message_id
        )
        if item is None:
            logger.warning(
                "receipt for unknown message id_prefix=%s",
                provider_message_id[:12],
            )
            return False
        now = self._clock.now()
        if status == "failed":
            if item.status not in ("SENT", "DELIVERED"):
                return False
            campaign_repo.update_item(
                session,
                item.id,
                status="FAILED",
                reason_code="DELIVERY_FAILED",
                last_error_code=error_code or "DELIVERY_FAILED",
                last_error_message=redact_text(error_message)
                if error_message
                else None,
                updated_at=now,
            )
            send_log_repo.insert(
                session,
                task_id=item.task_id,
                item_id=item.id,
                phone_hash=item.phone_hash,
                phone_masked=item.phone_masked,
                phase="RECEIPT",
                outcome="DELIVERY_FAILED",
                reason_code=error_code or "DELIVERY_FAILED",
                provider_message_id=provider_message_id,
                created_at=now,
            )
            session.commit()
            return True
        target = status.upper()
        current_rank = _STATUS_RANK.get(item.status)
        target_rank = _STATUS_RANK.get(target)
        if target_rank is None or current_rank is None or target_rank <= current_rank:
            return False
        applied_at = _as_utc(timestamp) or now
        fields = {"status": target, "updated_at": now}
        if target == "DELIVERED":
            fields["delivered_at"] = applied_at
        else:
            fields["read_at"] = applied_at
        campaign_repo.update_item(session, item.id, **fields)
        send_log_repo.insert(
            session,
            task_id=item.task_id,
            item_id=item.id,
            phone_hash=item.phone_hash,
            phone_masked=item.phone_masked,
            phase="RECEIPT",
            outcome=target,
            provider_message_id=provider_message_id,
            created_at=now,
        )
        session.commit()
        return True

    def poll_and_apply(self) -> int:
        """Fetch and apply any receipts currently due from the messenger."""
        if self._messenger is None or self._session_factory is None:
            return 0
        return self._apply_many(self._messenger.poll_receipts())

    def flush_and_apply(self) -> int:
        """Apply every queued mock receipt immediately, for the demo endpoint."""
        flush = getattr(self._messenger, "flush_receipts", None)
        if flush is None:
            return 0
        return self._apply_many(flush())

    def _apply_many(self, receipts: list[Receipt]) -> int:
        applied = 0
        for receipt in receipts:
            with self._session_factory() as session:
                try:
                    changed = self.apply(
                        session,
                        provider_message_id=receipt.provider_message_id,
                        status=receipt.status,
                        error_code=receipt.error_code,
                        error_message=receipt.error_message,
                        timestamp=receipt.timestamp,
                    )
                except Exception:
                    session.rollback()
                    logger.exception("receipt application failed")
                    continue
            if changed:
                applied += 1
        return applied

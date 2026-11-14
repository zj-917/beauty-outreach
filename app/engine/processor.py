"""Process one claimed task item through the full send gate chain."""

from __future__ import annotations

import logging
import random
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.audit import AuditWriter
from app.core.clock import Clock
from app.core.security import PhoneCipher
from app.domain.backoff import BackoffPolicy, retry_delay
from app.domain.failures import AUTH_ERROR_CODE, RATE_LIMITED_CODE, breaks_circuit
from app.domain.gates import Defer, Pass, Release, Skip, send_decision
from app.domain.masking import redact_text
from app.engine.facts import GateFacts
from app.engine.runtime import load_runtime_settings
from app.providers.messenger.base import (
    Messenger,
    ResultKind,
    SendRequest,
    SendResult,
)
from app.repositories import campaign_repo, lead_repo, send_log_repo, template_repo
from app.repositories.campaign_repo import CampaignEntry, ItemEntry
from app.repositories.lead_repo import LeadEntry
from app.repositories.template_repo import TemplateEntry

logger = logging.getLogger(__name__)


def _iso_z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class Processor:
    """Execute gates 1-9, the provider call and the retry policy for one item."""

    def __init__(
        self,
        clock: Clock,
        cipher: PhoneCipher,
        messenger: Messenger,
        *,
        worker_id: str,
        audit: AuditWriter,
        rng: Callable[[], float] | None = None,
    ) -> None:
        self._clock = clock
        self._cipher = cipher
        self._messenger = messenger
        self._worker_id = worker_id
        self._audit = audit
        self._rng = rng or self._default_rng
        self._facts = GateFacts(clock, cipher)

    @staticmethod
    def _default_rng() -> float:
        return random.uniform(-1.0, 1.0)

    def process(self, session: Session, item_id: int) -> str:
        """Run one item and return the outcome label."""
        item = campaign_repo.get_item(session, item_id)
        if item is None:
            return "NOT_FOUND"
        task = campaign_repo.get_campaign(session, item.task_id)
        if task is None:
            campaign_repo.update_item(
                session,
                item_id,
                locked_by=None,
                locked_at=None,
                updated_at=self._clock.now(),
            )
            session.commit()
            return "RELEASED"
        lead = lead_repo.get_lead(session, item.lead_id)
        template = template_repo.get_template(session, task.template_id)
        settings = self._settings(session)
        now = self._clock.now()
        facts = self._facts.build(
            session,
            item=item,
            task=task,
            lead=lead,
            template=template,
            settings=settings,
        )
        decision = send_decision(facts.context)
        if isinstance(decision, Release):
            campaign_repo.update_item(
                session,
                item_id,
                locked_by=None,
                locked_at=None,
                updated_at=now,
            )
            session.commit()
            return "RELEASED"
        if isinstance(decision, Skip):
            return self._skip(session, item, decision.reason, now)
        if isinstance(decision, Defer):
            return self._defer(session, item, decision, now)
        assert isinstance(decision, Pass)
        return self._send(
            session, item, lead, template, settings, facts.rendered, now
        )

    def complete_if_finished(self, session: Session, task_id: int) -> bool:
        """Complete a RUNNING task with no open items; commits when it applies."""
        completed = self._maybe_complete(session, task_id, self._clock.now())
        if completed:
            session.commit()
        return completed

    def _skip(
        self, session: Session, item: ItemEntry, reason: str, now: datetime
    ) -> str:
        campaign_repo.update_item(
            session,
            item.id,
            status="SKIPPED",
            reason_code=reason,
            locked_by=None,
            locked_at=None,
            updated_at=now,
        )
        send_log_repo.insert(
            session,
            task_id=item.task_id,
            item_id=item.id,
            phone_hash=item.phone_hash,
            phone_masked=item.phone_masked,
            phase="GATE",
            outcome="BLOCKED",
            reason_code=reason,
            created_at=now,
        )
        self._maybe_complete(session, item.task_id, now)
        session.commit()
        return "SKIPPED"

    def _defer(
        self, session: Session, item: ItemEntry, decision: Defer, now: datetime
    ) -> str:
        campaign_repo.update_item(
            session,
            item.id,
            next_attempt_at=decision.until,
            locked_by=None,
            locked_at=None,
            updated_at=now,
        )
        send_log_repo.insert(
            session,
            task_id=item.task_id,
            item_id=item.id,
            phone_hash=item.phone_hash,
            phone_masked=item.phone_masked,
            phase="GATE",
            outcome="DEFERRED",
            reason_code=decision.reason,
            detail={"until": _iso_z(decision.until)},
            created_at=now,
        )
        session.commit()
        return "DEFERRED"

    def _send(
        self,
        session: Session,
        item: ItemEntry,
        lead: LeadEntry | None,
        template: TemplateEntry | None,
        settings: dict[str, Any],
        rendered: str | None,
        now: datetime,
    ) -> str:
        phone = (
            self._cipher.try_decrypt(lead.phone_enc)
            if lead is not None and lead.phone_enc is not None
            else None
        )
        if phone is None or rendered is None or template is None:
            return self._skip(session, item, "NO_PHONE", now)
        attempt_no = item.attempts + 1
        campaign_repo.update_item(
            session,
            item.id,
            status="SENDING",
            attempts=attempt_no,
            rendered_body=rendered,
            updated_at=now,
        )
        session.commit()
        request = SendRequest(
            idempotency_key=item.idempotency_key,
            to_phone=phone,
            body=rendered,
            template_name=template.name,
            language=template.language,
        )
        timeout_seconds = float(settings["sending.provider_timeout_seconds"])
        started = self._clock.monotonic()
        result = self._call_provider(request, timeout_seconds)
        latency_ms = max(0, int((self._clock.monotonic() - started) * 1000))
        return self._write_back(
            session, item, result, attempt_no, latency_ms, settings
        )

    def _call_provider(self, request: SendRequest, timeout_seconds: float) -> SendResult:
        """Call the provider on a daemon thread so runaway calls cannot block a tick."""
        box: list[SendResult] = []
        failures: list[Exception] = []

        def run() -> None:
            try:
                box.append(self._messenger.send(request))
            except Exception as exc:
                failures.append(exc)

        thread = threading.Thread(target=run, name="provider-call", daemon=True)
        thread.start()
        thread.join(timeout_seconds)
        if thread.is_alive():
            logger.warning(
                "provider call timed out key_prefix=%s",
                request.idempotency_key[:8],
            )
            return SendResult(
                kind=ResultKind.RETRYABLE,
                code="TIMEOUT",
                message="provider call timed out",
            )
        if failures or not box:
            logger.warning(
                "provider raised unexpectedly key_prefix=%s",
                request.idempotency_key[:8],
            )
            return SendResult(
                kind=ResultKind.RETRYABLE,
                code="NETWORK_ERROR",
                message="provider raised unexpectedly",
            )
        return box[0]

    def _write_back(
        self,
        session: Session,
        item: ItemEntry,
        result: SendResult,
        attempt_no: int,
        latency_ms: int,
        settings: dict[str, Any],
    ) -> str:
        finished = self._clock.now()
        task = campaign_repo.get_campaign(session, item.task_id)
        message = redact_text(result.message) if result.message else None
        common = {"locked_by": None, "locked_at": None, "updated_at": finished}
        policy = BackoffPolicy.from_settings(settings)
        code = result.code
        if result.kind is ResultKind.ACCEPTED:
            campaign_repo.update_item(
                session,
                item.id,
                status="SENT",
                provider_message_id=result.provider_message_id,
                sent_at=finished,
                next_attempt_at=None,
                last_error_code=None,
                last_error_message=None,
                **common,
            )
            if task is not None and task.consecutive_failures:
                campaign_repo.update_campaign(
                    session, task.id, consecutive_failures=0, updated_at=finished
                )
            outcome, reason = "ACCEPTED", None
        elif result.kind is ResultKind.RETRYABLE:
            self._register_failure(
                session, task, code=code, settings=settings, now=finished
            )
            if task is not None and task.status == "CANCELLED":
                campaign_repo.update_item(
                    session,
                    item.id,
                    status="SKIPPED",
                    reason_code="TASK_CANCELLED",
                    **common,
                )
            elif attempt_no >= policy.max_attempts:
                campaign_repo.update_item(
                    session,
                    item.id,
                    status="FAILED",
                    reason_code="MAX_ATTEMPTS_EXCEEDED",
                    last_error_code=code,
                    last_error_message=message,
                    **common,
                )
            else:
                delay = retry_delay(policy, attempt=attempt_no, u=self._rng())
                if code == RATE_LIMITED_CODE and result.retry_after_seconds is not None:
                    delay = max(delay, float(result.retry_after_seconds))
                campaign_repo.update_item(
                    session,
                    item.id,
                    status="RETRY_WAIT",
                    next_attempt_at=finished + timedelta(seconds=delay),
                    last_error_code=code,
                    last_error_message=message,
                    **common,
                )
            outcome, reason = "RETRYABLE_ERROR", code
        else:
            campaign_repo.update_item(
                session,
                item.id,
                status="FAILED",
                reason_code=code,
                last_error_code=code,
                last_error_message=message,
                **common,
            )
            outcome, reason = "PERMANENT_ERROR", code
            self._register_failure(
                session, task, code=code, settings=settings, now=finished
            )
        send_log_repo.insert(
            session,
            task_id=item.task_id,
            item_id=item.id,
            phone_hash=item.phone_hash,
            phone_masked=item.phone_masked,
            phase="PROVIDER",
            outcome=outcome,
            reason_code=reason,
            attempt_no=attempt_no,
            provider_message_id=result.provider_message_id,
            latency_ms=latency_ms,
            created_at=finished,
        )
        self._maybe_complete(session, item.task_id, finished)
        session.commit()
        return outcome

    def _register_failure(
        self,
        session: Session,
        task: CampaignEntry | None,
        *,
        code: str | None,
        settings: dict[str, Any],
        now: datetime,
    ) -> None:
        if task is None or task.status != "RUNNING":
            return
        if code == AUTH_ERROR_CODE:
            self._open_circuit(
                session, task, failures=task.consecutive_failures, now=now
            )
            return
        if not breaks_circuit(code):
            return
        failures = task.consecutive_failures + 1
        campaign_repo.update_campaign(
            session, task.id, consecutive_failures=failures, updated_at=now
        )
        threshold = int(settings["sending.circuit_breaker_threshold"])
        if failures >= threshold:
            self._open_circuit(session, task, failures=failures, now=now)

    def _open_circuit(
        self,
        session: Session,
        task: CampaignEntry,
        *,
        failures: int,
        now: datetime,
    ) -> None:
        campaign_repo.update_campaign(
            session,
            task.id,
            status="PAUSED",
            pause_reason="CIRCUIT_OPEN",
            paused_at=now,
            updated_at=now,
        )
        self._audit.record(
            session,
            actor="system:worker",
            action="CAMPAIGN_CIRCUIT_OPENED",
            entity_type="campaign",
            entity_id=str(task.id),
            before={
                "status": "RUNNING",
                "consecutive_failures": task.consecutive_failures,
            },
            after={
                "status": "PAUSED",
                "pause_reason": "CIRCUIT_OPEN",
                "consecutive_failures": failures,
            },
        )

    def _maybe_complete(
        self, session: Session, task_id: int, now: datetime
    ) -> bool:
        task = campaign_repo.get_campaign(session, task_id)
        if task is None or task.status != "RUNNING":
            return False
        if campaign_repo.has_open_items(session, task_id):
            return False
        campaign_repo.update_campaign(
            session, task_id, status="COMPLETED", finished_at=now, updated_at=now
        )
        self._audit.record(
            session,
            actor="system:worker",
            action="CAMPAIGN_COMPLETED",
            entity_type="campaign",
            entity_id=str(task_id),
            before={"status": "RUNNING"},
            after={"status": "COMPLETED"},
        )
        return True

    @staticmethod
    def _settings(session: Session) -> dict[str, Any]:
        return load_runtime_settings(session)

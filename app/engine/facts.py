"""Build the immutable gate inputs for one task item (shared with previews)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.security import PhoneCipher
from app.domain.gates import ComplianceSnapshot, QuietHours, SendContext
from app.domain.phone import normalize_phone
from app.domain.render import RenderError, build_values, render
from app.repositories import (
    config_repo,
    lead_repo,
    send_log_repo,
    suppression_repo,
)
from app.repositories.campaign_repo import CampaignEntry, ItemEntry
from app.repositories.lead_repo import LeadEntry
from app.repositories.template_repo import TemplateEntry


@dataclass(frozen=True)
class ItemFacts:
    """Gate context plus the rendered body for one item."""

    context: SendContext
    rendered: str | None


class GateFacts:
    """Assemble suppression, consent, template and rate facts for one item."""

    def __init__(self, clock: Clock, cipher: PhoneCipher) -> None:
        self._clock = clock
        self._cipher = cipher

    def build(
        self,
        session: Session,
        *,
        item: ItemEntry,
        task: CampaignEntry,
        lead: LeadEntry | None,
        template: TemplateEntry | None,
        settings: dict[str, Any],
        include_time_gates: bool = True,
    ) -> ItemFacts:
        """Return the gate inputs; time gates are disabled for dry-run previews."""
        now = self._clock.now()
        snapshot = self._snapshot(
            session, item, lead, settings, now, include_time_gates
        )
        enabled_rules = [
            rule for rule in config_repo.list_rate_rules(session) if rule.enabled
        ]
        recipient_rules = [
            rule for rule in enabled_rules if rule.scope == "PER_RECIPIENT"
        ]
        global_rules = [rule for rule in enabled_rules if rule.scope == "GLOBAL"]
        rendered, render_failed = self._render(template, lead, settings)
        already_contacted = (
            item.phone_hash is not None
            and template is not None
            and send_log_repo.has_accepted_for_template(
                session,
                phone_hash=item.phone_hash,
                template_name=template.name,
                exclude_item_id=item.id,
            )
        )
        recipient_limited = item.phone_hash is not None and self._recipient_limited(
            session, item, recipient_rules, now
        )
        context = SendContext(
            task_running=task.status == "RUNNING",
            compliance=snapshot,
            template_approved=template is not None
            and template.status == "APPROVED",
            render_failed=render_failed,
            already_contacted=already_contacted,
            recipient_rate_limited=recipient_limited,
            global_rate_until=(
                self._global_until(session, global_rules, now)
                if include_time_gates
                else None
            ),
        )
        return ItemFacts(context=context, rendered=rendered)

    def _snapshot(
        self,
        session: Session,
        item: ItemEntry,
        lead: LeadEntry | None,
        settings: dict[str, Any],
        now: datetime,
        include_time_gates: bool,
    ) -> ComplianceSnapshot:
        suppression = suppression_repo.find_types(
            session,
            phone_hash=item.phone_hash,
            username=lead.username if lead is not None else None,
        )
        consent = None
        if item.phone_hash is not None:
            record = lead_repo.find_consent(session, item.phone_hash)
            consent = record.status if record is not None else None
        quiet = (
            QuietHours(
                enabled=settings["sending.quiet_hours_enabled"],
                start=settings["sending.quiet_hours_start"],
                end=settings["sending.quiet_hours_end"],
                tz=settings["sending.quiet_hours_tz"],
            )
            if include_time_gates
            else QuietHours(enabled=False)
        )
        return ComplianceSnapshot(
            has_phone=item.phone_hash is not None,
            phone_valid=self._phone_valid(lead),
            consent=consent,
            now=now,
            suppression=frozenset(suppression),
            quiet_hours=quiet,
        )

    def _phone_valid(self, lead: LeadEntry | None) -> bool:
        if lead is None or lead.phone_enc is None:
            return False
        decrypted = self._cipher.try_decrypt(lead.phone_enc)
        return decrypted is not None and normalize_phone(decrypted) is not None

    def _render(
        self,
        template: TemplateEntry | None,
        lead: LeadEntry | None,
        settings: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        if template is None or lead is None:
            return None, None
        values = build_values(
            display_name=lead.display_name,
            username=lead.username,
            top_keyword=lead.top_keyword,
            brand=settings["message.brand"],
            optout_text=settings["message.optout_text"],
        )
        try:
            return render(template.body, values), None
        except RenderError as exc:
            return None, exc.code

    def _recipient_limited(
        self, session: Session, item: ItemEntry, rules: list[Any], now: datetime
    ) -> bool:
        assert item.phone_hash is not None
        for rule in rules:
            count = send_log_repo.recipient_accepted_count(
                session,
                phone_hash=item.phone_hash,
                window_seconds=rule.window_seconds,
                now=now,
                exclude_item_id=item.id,
            )
            if count >= rule.max_count:
                return True
        return False

    def _global_until(
        self, session: Session, rules: list[Any], now: datetime
    ) -> datetime | None:
        candidates: list[datetime] = []
        for rule in rules:
            count, earliest = send_log_repo.provider_window_stats(
                session, window_seconds=rule.window_seconds, now=now
            )
            if count >= rule.max_count and earliest is not None:
                candidates.append(earliest + timedelta(seconds=rule.window_seconds))
        return max(candidates) if candidates else None

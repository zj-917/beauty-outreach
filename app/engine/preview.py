"""Read-only dry-run preview of gates 1-7 (campaign.md §10)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.security import PhoneCipher
from app.domain.gates import Release, Skip, send_decision
from app.engine.facts import GateFacts
from app.engine.runtime import load_runtime_settings
from app.repositories import campaign_repo, lead_repo, template_repo
from app.repositories.campaign_repo import CampaignEntry


@dataclass(frozen=True)
class PreviewReport:
    """Gate distribution for the open items of one campaign."""

    task_id: int
    total_items: int
    will_attempt: int
    will_release: int
    will_skip: dict[str, int] = field(default_factory=dict)


class Previewer:
    """Evaluate gates 1-7 for open items without any writes or provider calls."""

    def __init__(self, clock: Clock, cipher: PhoneCipher) -> None:
        self._facts = GateFacts(clock, cipher)

    def preview(self, session: Session, task: CampaignEntry) -> PreviewReport:
        """Return how the open items would be decided if processing started now."""
        items = campaign_repo.list_open_items(session, task.id)
        template = template_repo.get_template(session, task.template_id)
        settings = load_runtime_settings(session)
        will_attempt = 0
        will_release = 0
        will_skip: dict[str, int] = {}
        for item in items:
            lead = lead_repo.get_lead(session, item.lead_id)
            facts = self._facts.build(
                session,
                item=item,
                task=task,
                lead=lead,
                template=template,
                settings=settings,
                include_time_gates=False,
            )
            decision = send_decision(facts.context)
            if isinstance(decision, Release):
                will_release += 1
            elif isinstance(decision, Skip):
                will_skip[decision.reason] = will_skip.get(decision.reason, 0) + 1
            else:
                will_attempt += 1
        return PreviewReport(
            task_id=task.id,
            total_items=len(items),
            will_attempt=will_attempt,
            will_release=will_release,
            will_skip=will_skip,
        )

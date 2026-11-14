"""Versioned template management, rendering and preview."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import AppError
from app.domain.render import RenderError, build_values, render, unknown_variables
from app.repositories import lead_repo, template_repo
from app.repositories.template_repo import TemplateEntry
from app.services.audit_service import AuditService
from app.services.config_service import ConfigService

_MAX_BODY_LENGTH = 800
_MAX_NAME_LENGTH = 80
_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}$")


@dataclass(frozen=True)
class _PreviewLead:
    """Minimal lead fields needed by template rendering."""

    display_name: str | None
    username: str
    top_keyword: str | None


_EXAMPLE_LEAD = _PreviewLead(
    display_name="Alex", username="alex_demo", top_keyword="beauty devices"
)


class TemplateService:
    """Create, version, review, render and preview message templates."""

    def __init__(self, clock: Clock, audit: AuditService | None = None) -> None:
        self._clock = clock
        self._audit = audit or AuditService(clock)

    def list_templates(self, session: Session) -> list[TemplateEntry]:
        """Return all template versions, grouped by name with newest first."""
        return template_repo.list_templates(session)

    def get_template(self, session: Session, template_id: int) -> TemplateEntry:
        """Return one template or raise NOT_FOUND."""
        entry = template_repo.get_template(session, template_id)
        if entry is None:
            raise AppError("NOT_FOUND", "Template not found")
        return entry

    def create(
        self,
        session: Session,
        *,
        name: str,
        body: str,
        language: str,
        operator: str,
        request_id: str | None = None,
    ) -> TemplateEntry:
        """Create version 1 of a new template in DRAFT."""
        clean_name = self._clean_name(name)
        clean_body = self._clean_body(body)
        clean_language = self._clean_language(language)
        if template_repo.find_template(session, clean_name, 1) is not None:
            raise AppError(
                "CONFLICT",
                "Template name already exists",
                details={"name": clean_name, "version": 1},
            )
        entry = template_repo.create_template(
            session,
            name=clean_name,
            version=1,
            language=clean_language,
            body=clean_body,
            status="DRAFT",
            created_by=operator,
            approved_by=None,
            approved_at=None,
            created_at=self._clock.now(),
        )
        self._audit.record(
            session,
            actor=operator,
            action="TEMPLATE_CREATED",
            entity_type="template",
            entity_id=str(entry.id),
            after=self._snapshot(entry),
            request_id=request_id,
        )
        session.commit()
        return entry

    def update(
        self,
        session: Session,
        template_id: int,
        *,
        body: str | None,
        language: str | None,
        operator: str,
        request_id: str | None = None,
    ) -> TemplateEntry:
        """Edit a DRAFT body or language; non-draft templates are immutable."""
        existing = self.get_template(session, template_id)
        if existing.status != "DRAFT":
            raise AppError(
                "TEMPLATE_IMMUTABLE",
                "Only DRAFT templates can be edited",
                details={"status": existing.status},
            )
        if body is None and language is None:
            return existing
        new_body = existing.body if body is None else self._clean_body(body)
        new_language = (
            existing.language if language is None else self._clean_language(language)
        )
        if new_body == existing.body and new_language == existing.language:
            return existing
        updated = template_repo.update_template(
            session, template_id, body=new_body, language=new_language
        )
        if updated is None:
            raise AppError("NOT_FOUND", "Template not found")
        self._audit.record(
            session,
            actor=operator,
            action="TEMPLATE_UPDATED",
            entity_type="template",
            entity_id=str(template_id),
            before={
                "language": existing.language,
                "content_length": len(existing.body),
            },
            after={"language": new_language, "content_length": len(new_body)},
            request_id=request_id,
        )
        session.commit()
        return updated

    def new_version(
        self,
        session: Session,
        template_id: int,
        *,
        body: str,
        operator: str,
        request_id: str | None = None,
    ) -> TemplateEntry:
        """Create a DRAFT version+1 from an existing template."""
        source = self.get_template(session, template_id)
        clean_body = self._clean_body(body)
        version = source.version + 1
        if template_repo.find_template(session, source.name, version) is not None:
            raise AppError(
                "CONFLICT",
                "Template version already exists",
                details={"name": source.name, "version": version},
            )
        entry = template_repo.create_template(
            session,
            name=source.name,
            version=version,
            language=source.language,
            body=clean_body,
            status="DRAFT",
            created_by=operator,
            approved_by=None,
            approved_at=None,
            created_at=self._clock.now(),
        )
        self._audit.record(
            session,
            actor=operator,
            action="TEMPLATE_VERSIONED",
            entity_type="template",
            entity_id=str(entry.id),
            before={"name": source.name, "version": source.version},
            after={
                "name": entry.name,
                "version": entry.version,
                "status": "DRAFT",
                "content_length": len(entry.body),
            },
            request_id=request_id,
        )
        session.commit()
        return entry

    def approve(
        self,
        session: Session,
        template_id: int,
        *,
        operator: str,
        request_id: str | None = None,
    ) -> TemplateEntry:
        """Approve a DRAFT template and record the reviewer and time."""
        existing = self.get_template(session, template_id)
        if existing.status != "DRAFT":
            raise AppError(
                "CONFLICT",
                "Only DRAFT templates can be approved",
                details={"status": existing.status},
            )
        updated = template_repo.approve_template(
            session,
            template_id,
            approved_by=operator,
            approved_at=self._clock.now(),
        )
        if updated is None:
            raise AppError("NOT_FOUND", "Template not found")
        self._audit.record(
            session,
            actor=operator,
            action="TEMPLATE_APPROVED",
            entity_type="template",
            entity_id=str(template_id),
            before={"status": existing.status},
            after={"status": "APPROVED", "approved_by": operator},
            request_id=request_id,
        )
        session.commit()
        return updated

    def disable(
        self,
        session: Session,
        template_id: int,
        *,
        operator: str,
        request_id: str | None = None,
    ) -> TemplateEntry:
        """Disable a template; repeating the call is a no-op."""
        existing = self.get_template(session, template_id)
        if existing.status == "DISABLED":
            return existing
        updated = template_repo.disable_template(session, template_id)
        if updated is None:
            raise AppError("NOT_FOUND", "Template not found")
        self._audit.record(
            session,
            actor=operator,
            action="TEMPLATE_DISABLED",
            entity_type="template",
            entity_id=str(template_id),
            before={"status": existing.status},
            after={"status": "DISABLED"},
            request_id=request_id,
        )
        session.commit()
        return updated

    def preview(
        self,
        session: Session,
        *,
        body: str | None = None,
        template_id: int | None = None,
        lead_id: int | None = None,
    ) -> str:
        """Render a body or stored template with a lead, without side effects."""
        if body is None and template_id is None:
            raise AppError("VALIDATION_ERROR", "body or template_id is required")
        if body is None:
            assert template_id is not None
            body = self.get_template(session, template_id).body
        clean_body = self._clean_body(body)
        lead = self._preview_lead(session, lead_id)
        settings = ConfigService(self._clock, self._audit).get_settings(session)
        values = build_values(
            display_name=lead.display_name,
            username=lead.username,
            top_keyword=lead.top_keyword,
            brand=settings["message.brand"],
            optout_text=settings["message.optout_text"],
        )
        try:
            return render(clean_body, values)
        except RenderError as exc:
            raise AppError(
                "VALIDATION_ERROR",
                "Template cannot be rendered",
                details={"reason": exc.code, "detail": exc.detail},
            ) from exc

    @staticmethod
    def _preview_lead(session: Session, lead_id: int | None) -> _PreviewLead:
        if lead_id is None:
            return _EXAMPLE_LEAD
        lead = lead_repo.get_lead(session, lead_id)
        if lead is None:
            raise AppError("NOT_FOUND", "Lead not found")
        return _PreviewLead(
            display_name=lead.display_name,
            username=lead.username,
            top_keyword=lead.top_keyword,
        )

    @staticmethod
    def _clean_name(name: str) -> str:
        clean = (name or "").strip()
        if not 1 <= len(clean) <= _MAX_NAME_LENGTH:
            raise AppError(
                "VALIDATION_ERROR",
                f"name must be 1-{_MAX_NAME_LENGTH} characters",
            )
        return clean

    @staticmethod
    def _clean_body(body: str) -> str:
        if not isinstance(body, str) or not body.strip():
            raise AppError("VALIDATION_ERROR", "body must be a non-empty string")
        if len(body) > _MAX_BODY_LENGTH:
            raise AppError(
                "VALIDATION_ERROR",
                f"body must be at most {_MAX_BODY_LENGTH} characters",
            )
        unknown = unknown_variables(body)
        if unknown:
            raise AppError(
                "TEMPLATE_UNKNOWN_VARIABLE",
                "Template contains unknown variables",
                details={"unknown_variables": unknown},
            )
        return body

    @staticmethod
    def _clean_language(language: str) -> str:
        clean = (language or "").strip().lower()
        if not _LANGUAGE_PATTERN.fullmatch(clean):
            raise AppError(
                "VALIDATION_ERROR",
                "language must be a 2-3 letter primary tag",
            )
        return clean

    @staticmethod
    def _snapshot(entry: TemplateEntry) -> dict[str, object]:
        return {
            "name": entry.name,
            "version": entry.version,
            "language": entry.language,
            "status": entry.status,
            "content_length": len(entry.body),
        }

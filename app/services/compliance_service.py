"""Consent, suppression and compliance gate orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import AppError
from app.core.security import PhoneCipher
from app.domain.gates import (
    ComplianceSnapshot,
    GateResult,
    QuietHours,
    evaluate,
    readiness,
)
from app.domain.lead import normalize_username
from app.domain.masking import mask_phone
from app.domain.normalize import matches_stop_keyword
from app.domain.phone import normalize_phone
from app.repositories import lead_repo, suppression_repo
from app.repositories.lead_repo import ConsentEntry, LeadEntry
from app.repositories.suppression_repo import SuppressionEntry
from app.services.audit_service import AuditService
from app.services.config_service import ConfigService

_CONSENT_STATUSES = frozenset({"GRANTED", "REVOKED"})
_SUPPRESSION_TYPES = frozenset({"BLACKLIST", "UNSUBSCRIBE"})


@dataclass(frozen=True)
class ComplianceFacts:
    """Suppression types and consent status for one recipient."""

    suppression: frozenset[str]
    consent: str | None


class ComplianceService:
    """Manage consent and suppression and evaluate the compliance gates."""

    def __init__(
        self, clock: Clock, cipher: PhoneCipher, audit: AuditService | None = None
    ) -> None:
        self._clock = clock
        self._cipher = cipher
        self._audit = audit or AuditService(clock)

    def list_consents(self, session: Session) -> list[ConsentEntry]:
        """Return all consent records, most recently updated first."""
        return lead_repo.list_consents(session)

    def upsert_consent(
        self,
        session: Session,
        *,
        phone: str,
        status: str,
        source: str,
        evidence_ref: str | None,
        operator: str,
        request_id: str | None = None,
    ) -> ConsentEntry:
        """Insert or update one consent record, always writing an audit row."""
        normalized = normalize_phone(phone)
        if normalized is None:
            raise AppError("VALIDATION_ERROR", "phone must be E.164")
        if status not in _CONSENT_STATUSES:
            raise AppError("VALIDATION_ERROR", "status must be GRANTED or REVOKED")
        clean_source = (source or "").strip()
        if not 1 <= len(clean_source) <= 80:
            raise AppError("VALIDATION_ERROR", "source must be 1-80 characters")
        clean_evidence = (evidence_ref or "").strip() or None
        if status == "GRANTED" and clean_evidence is None:
            raise AppError(
                "VALIDATION_ERROR", "evidence_ref is required for GRANTED consent"
            )
        if clean_evidence is not None and len(clean_evidence) > 200:
            raise AppError(
                "VALIDATION_ERROR", "evidence_ref must be at most 200 characters"
            )
        phone_hash = self._cipher.hash_phone(normalized)
        phone_masked = mask_phone(normalized)
        existing = lead_repo.find_consent(session, phone_hash)
        now = self._clock.now()
        if existing is None:
            lead_repo.create_consent(
                session,
                phone_hash=phone_hash,
                phone_masked=phone_masked,
                status=status,
                source=clean_source,
                evidence_ref=clean_evidence,
                granted_at=now if status == "GRANTED" else None,
                updated_at=now,
                updated_by=operator,
            )
            before = None
        else:
            granted_at = None
            if status == "GRANTED":
                granted_at = (
                    existing.granted_at if existing.status == "GRANTED" else now
                )
            lead_repo.update_consent(
                session,
                existing.id,
                status=status,
                source=clean_source,
                evidence_ref=clean_evidence,
                granted_at=granted_at,
                updated_at=now,
                updated_by=operator,
            )
            before = {
                "phone_masked": existing.phone_masked,
                "status": existing.status,
            }
        updated = lead_repo.find_consent(session, phone_hash)
        assert updated is not None
        self._audit.record(
            session,
            actor=operator,
            action="CONSENT_UPSERTED",
            entity_type="contact_consent",
            entity_id=str(updated.id),
            before=before,
            after={"phone_masked": phone_masked, "status": status},
            request_id=request_id,
        )
        session.commit()
        return updated

    def add_suppression(
        self,
        session: Session,
        *,
        type: str,
        phone: str | None,
        username: str | None,
        reason: str,
        source: str,
        operator: str,
        request_id: str | None = None,
    ) -> SuppressionEntry:
        """Add a blacklist or unsubscribe entry; duplicate registration is idempotent."""
        if type not in _SUPPRESSION_TYPES:
            raise AppError(
                "VALIDATION_ERROR", "type must be BLACKLIST or UNSUBSCRIBE"
            )
        clean_reason = (reason or "").strip()
        if not 1 <= len(clean_reason) <= 200:
            raise AppError("VALIDATION_ERROR", "reason must be 1-200 characters")
        phone_hash = None
        phone_masked = None
        if phone is not None:
            normalized = normalize_phone(phone)
            if normalized is None:
                raise AppError("VALIDATION_ERROR", "phone must be E.164")
            phone_hash = self._cipher.hash_phone(normalized)
            phone_masked = mask_phone(normalized)
        clean_username = normalize_username(username) if username is not None else ""
        if phone_hash is None and not clean_username:
            raise AppError("VALIDATION_ERROR", "phone or username is required")
        existing = None
        if phone_hash is not None:
            existing = suppression_repo.find_by_phone(
                session, type=type, phone_hash=phone_hash
            )
        if existing is None and clean_username:
            existing = suppression_repo.find_by_username(
                session, type=type, username=clean_username
            )
        if existing is not None:
            return existing
        entry = suppression_repo.create_suppression(
            session,
            type=type,
            phone_hash=phone_hash,
            phone_masked=phone_masked,
            username=clean_username or None,
            reason=clean_reason,
            source=source,
            created_at=self._clock.now(),
            created_by=operator,
        )
        self._audit.record(
            session,
            actor=operator,
            action="SUPPRESSION_ADDED",
            entity_type="suppression",
            entity_id=str(entry.id),
            after={
                "type": entry.type,
                "phone_masked": entry.phone_masked,
                "username": entry.username,
            },
            request_id=request_id,
        )
        session.commit()
        return entry

    def remove_suppression(
        self,
        session: Session,
        suppression_id: int,
        *,
        operator: str,
        request_id: str | None = None,
    ) -> None:
        """Delete a blacklist entry; unsubscribe entries are immutable."""
        existing = suppression_repo.get_suppression(session, suppression_id)
        if existing is None:
            raise AppError("NOT_FOUND", "Suppression not found")
        if existing.type == "UNSUBSCRIBE":
            raise AppError(
                "COMP_UNSUBSCRIBE_IMMUTABLE",
                "Unsubscribe entries cannot be removed",
            )
        suppression_repo.delete_suppression(session, suppression_id)
        self._audit.record(
            session,
            actor=operator,
            action="SUPPRESSION_REMOVED",
            entity_type="suppression",
            entity_id=str(suppression_id),
            before={
                "type": existing.type,
                "phone_masked": existing.phone_masked,
                "username": existing.username,
            },
            request_id=request_id,
        )
        session.commit()

    def list_suppressions(
        self, session: Session, *, type: str | None = None
    ) -> list[SuppressionEntry]:
        """Return suppression entries, newest first, optionally filtered by type."""
        return suppression_repo.list_suppressions(session, type=type)

    def lookup(
        self,
        session: Session,
        *,
        phone_hash: str | None,
        username: str | None,
    ) -> ComplianceFacts:
        """Query suppression and consent facts for one recipient in real time."""
        suppression = suppression_repo.find_types(
            session, phone_hash=phone_hash, username=username
        )
        consent = None
        if phone_hash is not None:
            record = lead_repo.find_consent(session, phone_hash)
            consent = record.status if record is not None else None
        return ComplianceFacts(suppression=frozenset(suppression), consent=consent)

    def settings(self, session: Session) -> dict[str, Any]:
        """Return the runtime settings used by the quiet-hours gate."""
        return ConfigService(self._clock, self._audit).get_settings(session)

    def snapshot(
        self,
        session: Session,
        *,
        phone_hash: str | None,
        username: str | None,
        has_phone: bool,
        phone_valid: bool,
        settings: dict[str, Any] | None = None,
    ) -> ComplianceSnapshot:
        """Build the immutable gate input for one recipient."""
        facts = self.lookup(session, phone_hash=phone_hash, username=username)
        values = settings if settings is not None else self.settings(session)
        return ComplianceSnapshot(
            has_phone=has_phone,
            phone_valid=phone_valid,
            consent=facts.consent,
            now=self._clock.now(),
            suppression=facts.suppression,
            quiet_hours=QuietHours(
                enabled=values["sending.quiet_hours_enabled"],
                start=values["sending.quiet_hours_start"],
                end=values["sending.quiet_hours_end"],
                tz=values["sending.quiet_hours_tz"],
            ),
        )

    def snapshot_for_lead(
        self,
        session: Session,
        lead: LeadEntry,
        *,
        settings: dict[str, Any] | None = None,
    ) -> ComplianceSnapshot:
        """Build the gate input for a stored lead, decrypting its phone."""
        return self.snapshot(
            session,
            phone_hash=lead.phone_hash,
            username=lead.username,
            has_phone=lead.phone_hash is not None,
            phone_valid=self._phone_valid(lead),
            settings=settings,
        )

    def evaluate_lead(
        self,
        session: Session,
        lead: LeadEntry,
        *,
        settings: dict[str, Any] | None = None,
    ) -> GateResult:
        """Evaluate the compliance gates for a stored lead."""
        return evaluate(self.snapshot_for_lead(session, lead, settings=settings))

    def readiness_for_lead(
        self,
        session: Session,
        lead: LeadEntry,
        *,
        settings: dict[str, Any] | None = None,
    ) -> str:
        """Return the pool delivery-readiness label for a stored lead."""
        return readiness(self.snapshot_for_lead(session, lead, settings=settings))

    def is_stop_text(self, session: Session, text: str) -> bool:
        """Return True when an inbound text is exactly a configured stop keyword."""
        values = self.settings(session)
        return matches_stop_keyword(text, values["compliance.stop_keywords"])

    def _phone_valid(self, lead: LeadEntry) -> bool:
        if lead.phone_enc is None:
            return False
        decrypted = self._cipher.try_decrypt(lead.phone_enc)
        return decrypted is not None and normalize_phone(decrypted) is not None

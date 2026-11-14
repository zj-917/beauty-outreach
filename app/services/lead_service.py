"""Lead import orchestration and queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import AppError
from app.core.security import PhoneCipher
from app.domain.lead import (
    USERNAME_PATTERN,
    normalize_bio,
    normalize_display_name,
    normalize_language,
    normalize_region,
    normalize_source_url,
    normalize_username,
)
from app.domain.masking import mask_phone
from app.domain.phone import normalize_phone
from app.providers.lead_source import (
    FileLeadSource,
    InstagramApiStub,
    LeadSourceError,
    MockLeadSource,
)
from app.providers.lead_source.base import LeadSource
from app.repositories import lead_repo
from app.repositories.lead_repo import BatchEntry, LeadEntry
from app.services.audit_service import AuditService

_CONSENT_STATUSES = {"GRANTED", "REVOKED"}


@dataclass(frozen=True)
class _RowFields:
    """Normalized fields of one accepted row."""

    username: str
    display_name: str | None
    bio: str | None
    region: str | None
    language: str | None
    source_url: str | None
    phone: str | None
    phone_hash: str | None
    phone_masked: str | None


class LeadService:
    """Import lead batches atomically and expose read models."""

    def __init__(
        self, clock: Clock, cipher: PhoneCipher, audit: AuditService | None = None
    ) -> None:
        self._clock = clock
        self._cipher = cipher
        self._audit = audit or AuditService(clock)

    @staticmethod
    def source_by_name(name: object) -> LeadSource:
        """Build a named source, rejecting anything but mock and instagram_api."""
        if name == "mock":
            return MockLeadSource()
        if name == "instagram_api":
            return InstagramApiStub()
        raise AppError("VALIDATION_ERROR", "source must be 'mock' or 'instagram_api'")

    @staticmethod
    def source_from_upload(filename: str, content: bytes) -> LeadSource:
        """Build a CSV/JSON source from uploaded bytes."""
        try:
            return FileLeadSource(filename, content)
        except LeadSourceError as exc:
            raise AppError("VALIDATION_ERROR", str(exc)) from exc

    def import_batch(
        self,
        session: Session,
        source: LeadSource,
        *,
        operator: str,
        request_id: str | None = None,
    ) -> BatchEntry:
        """Normalize, validate and store every row of one source in a single transaction."""
        rows = source.rows()
        now = self._clock.now()
        batch_id = lead_repo.create_batch(
            session,
            source_type=source.source_type,
            source_name=source.source_name,
            created_by=operator,
            created_at=now,
        )
        counters = {"imported": 0, "duplicates": 0, "invalid": 0, "warnings": 0}
        errors: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            self._process_row(
                session, batch_id, index, row, counters, errors, operator, now
            )
        lead_repo.finish_batch(
            session,
            batch_id,
            total_rows=len(rows),
            imported=counters["imported"],
            duplicates=counters["duplicates"],
            invalid=counters["invalid"],
            warnings=counters["warnings"],
            errors=errors,
        )
        self._audit.record(
            session,
            actor=operator,
            action="LEAD_BATCH_IMPORTED",
            entity_type="lead_batch",
            entity_id=str(batch_id),
            after={
                "source_type": source.source_type,
                "source_name": source.source_name,
                "total_rows": len(rows),
                **counters,
            },
            request_id=request_id,
        )
        session.commit()
        batch = lead_repo.get_batch(session, batch_id)
        assert batch is not None
        return batch

    def list_leads(
        self,
        session: Session,
        *,
        status: str | None = None,
        min_score: int | None = None,
        batch_id: int | None = None,
        q: str | None = None,
        region: str | None = None,
        language: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[LeadEntry], int]:
        """Return one filtered page of leads."""
        return lead_repo.list_leads(
            session,
            status=status or None,
            min_score=min_score,
            batch_id=batch_id,
            q=(q or "").strip() or None,
            region=(region or "").strip().upper() or None,
            language=(language or "").strip().lower() or None,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    def get_lead(self, session: Session, lead_id: int) -> LeadEntry:
        """Return one lead or raise NOT_FOUND."""
        lead = lead_repo.get_lead(session, lead_id)
        if lead is None:
            raise AppError("NOT_FOUND", "Lead not found")
        return lead

    def list_batches(
        self, session: Session, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[BatchEntry], int]:
        """Return one page of import batches."""
        return lead_repo.list_batches(
            session, offset=(page - 1) * page_size, limit=page_size
        )

    def get_batch(self, session: Session, batch_id: int) -> BatchEntry:
        """Return one batch or raise NOT_FOUND."""
        batch = lead_repo.get_batch(session, batch_id)
        if batch is None:
            raise AppError("NOT_FOUND", "Lead batch not found")
        return batch

    def _process_row(
        self,
        session: Session,
        batch_id: int,
        index: int,
        row: dict[str, Any],
        counters: dict[str, int],
        errors: list[dict[str, Any]],
        operator: str,
        now: datetime,
    ) -> None:
        fields = self._normalize_row(index, row, counters, errors)
        if fields is None:
            return
        existing = lead_repo.find_lead_by_username(session, fields.username)
        if existing is not None:
            self._merge_duplicate(
                session,
                index,
                row,
                existing,
                fields,
                counters,
                errors,
                operator,
                now,
            )
            return
        owner = (
            lead_repo.find_lead_by_phone_hash(session, fields.phone_hash)
            if fields.phone_hash
            else None
        )
        if owner is not None:
            counters["duplicates"] += 1
            errors.append(
                {
                    "row": index,
                    "code": "DUPLICATE_PHONE",
                    "detail": "phone is already used by another lead",
                }
            )
            self._apply_consent(
                session, index, row, fields, operator, now, counters, errors
            )
            return
        lead_repo.create_lead(
            session,
            batch_id=batch_id,
            username=fields.username,
            display_name=fields.display_name,
            bio=fields.bio,
            region=fields.region,
            language=fields.language,
            source_url=fields.source_url,
            phone_enc=self._cipher.encrypt(fields.phone) if fields.phone else None,
            phone_hash=fields.phone_hash,
            phone_masked=fields.phone_masked,
            created_at=now,
            updated_at=now,
        )
        counters["imported"] += 1
        self._apply_consent(
            session, index, row, fields, operator, now, counters, errors
        )

    def _normalize_row(
        self,
        index: int,
        row: dict[str, Any],
        counters: dict[str, int],
        errors: list[dict[str, Any]],
    ) -> _RowFields | None:
        username = normalize_username(row.get("username"))
        if not username:
            self._reject(
                counters, errors, index, "MISSING_USERNAME", "username is empty"
            )
            return None
        if not USERNAME_PATTERN.fullmatch(username):
            self._reject(
                counters,
                errors,
                index,
                "INVALID_USERNAME",
                "username must be 1-30 characters of a-z, 0-9, dot or underscore",
            )
            return None
        source_url, url_ok = normalize_source_url(row.get("source_url"))
        if not url_ok:
            self._reject(
                counters,
                errors,
                index,
                "INVALID_SOURCE_URL",
                "source_url must be an https instagram.com link",
            )
            return None

        region, region_ok = normalize_region(row.get("region"))
        language, language_ok = normalize_language(row.get("language"))
        raw_phone = str(row.get("phone") or "").strip()
        phone = normalize_phone(raw_phone) if raw_phone else None
        if not region_ok:
            self._warn(
                counters, errors, index, "INVALID_REGION", "region is not ISO alpha-2"
            )
        if not language_ok:
            self._warn(
                counters,
                errors,
                index,
                "INVALID_LANGUAGE",
                "language is not a valid tag",
            )
        if raw_phone and phone is None:
            self._warn(
                counters,
                errors,
                index,
                "INVALID_PHONE_DROPPED",
                "phone is not E.164; lead kept without a phone",
            )
        return _RowFields(
            username=username,
            display_name=normalize_display_name(row.get("display_name")),
            bio=normalize_bio(row.get("bio")),
            region=region,
            language=language,
            source_url=source_url,
            phone=phone,
            phone_hash=self._cipher.hash_phone(phone) if phone else None,
            phone_masked=mask_phone(phone) if phone else None,
        )

    def _merge_duplicate(
        self,
        session: Session,
        index: int,
        row: dict[str, Any],
        existing: LeadEntry,
        fields: _RowFields,
        counters: dict[str, int],
        errors: list[dict[str, Any]],
        operator: str,
        now: datetime,
    ) -> None:
        different_phone = bool(
            existing.phone_hash
            and fields.phone_hash
            and existing.phone_hash != fields.phone_hash
        )
        other_owner = (
            lead_repo.find_lead_by_phone_hash(session, fields.phone_hash)
            if existing.phone_hash is None and fields.phone_hash
            else None
        )
        conflict = different_phone or (
            other_owner is not None and other_owner.id != existing.id
        )
        counters["duplicates"] += 1
        if different_phone:
            detail = "existing lead keeps its original phone"
        elif conflict:
            detail = "phone already belongs to another lead; not copied"
        else:
            detail = "username already exists"
        errors.append(
            {
                "row": index,
                "code": "IMPORT_CONFLICT" if conflict else "DUPLICATE_USERNAME",
                "detail": detail,
            }
        )
        fill_phone = (
            fields.phone
            if fields.phone_hash and existing.phone_hash is None and not conflict
            else None
        )
        lead_repo.fill_missing_fields(
            session,
            existing.id,
            display_name=fields.display_name,
            bio=fields.bio,
            region=fields.region,
            language=fields.language,
            source_url=fields.source_url,
            phone_enc=self._cipher.encrypt(fill_phone) if fill_phone else None,
            phone_hash=fields.phone_hash if fill_phone else None,
            phone_masked=fields.phone_masked if fill_phone else None,
            updated_at=now,
        )
        if not conflict:
            self._apply_consent(
                session, index, row, fields, operator, now, counters, errors
            )

    def _apply_consent(
        self,
        session: Session,
        index: int,
        row: dict[str, Any],
        fields: _RowFields,
        operator: str,
        now: datetime,
        counters: dict[str, int],
        errors: list[dict[str, Any]],
    ) -> None:
        status = str(row.get("consent_status") or "").strip().upper()
        if not status:
            return
        source = str(row.get("consent_source") or "").strip()
        evidence = str(row.get("consent_evidence") or "").strip() or None
        complete = (
            fields.phone_hash is not None
            and status in _CONSENT_STATUSES
            and (status == "REVOKED" or (source and evidence is not None))
        )
        if not complete:
            self._warn(
                counters,
                errors,
                index,
                "CONSENT_INCOMPLETE",
                "consent needs a valid phone, a known status and source plus evidence",
            )
            return
        assert fields.phone_hash is not None
        existing = lead_repo.find_consent(session, fields.phone_hash)
        if existing is None:
            lead_repo.create_consent(
                session,
                phone_hash=fields.phone_hash,
                phone_masked=fields.phone_masked or "",
                status=status,
                source=source or "import",
                evidence_ref=evidence,
                granted_at=now if status == "GRANTED" else None,
                updated_at=now,
                updated_by=operator,
            )
            return
        if status == "REVOKED":
            lead_repo.update_consent(
                session,
                existing.id,
                status="REVOKED",
                source=source or existing.source,
                evidence_ref=evidence,
                granted_at=None,
                updated_at=now,
                updated_by=operator,
            )

    @staticmethod
    def _reject(
        counters: dict[str, int],
        errors: list[dict[str, Any]],
        index: int,
        code: str,
        detail: str,
    ) -> None:
        counters["invalid"] += 1
        errors.append({"row": index, "code": code, "detail": detail})

    @staticmethod
    def _warn(
        counters: dict[str, int],
        errors: list[dict[str, Any]],
        index: int,
        code: str,
        detail: str,
    ) -> None:
        counters["warnings"] += 1
        errors.append({"row": index, "code": code, "detail": detail})

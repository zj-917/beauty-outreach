"""Persistence for lead batches, leads and consent records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import ContactConsent, Lead, LeadBatch


@dataclass(frozen=True)
class BatchEntry:
    """Detached lead batch row."""

    id: int
    source_type: str
    source_name: str
    total_rows: int
    imported: int
    duplicates: int
    invalid: int
    warnings: int
    errors: list[dict[str, Any]]
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class LeadEntry:
    """Detached lead row with the masked phone only."""

    id: int
    batch_id: int
    username: str
    display_name: str | None
    bio: str | None
    region: str | None
    language: str | None
    source_url: str | None
    phone_enc: str | None
    phone_hash: str | None
    phone_masked: str | None
    status: str
    score: int | None
    score_reasons: list[Any] | None
    top_keyword: str | None
    decision_source: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ConsentEntry:
    """Detached consent row."""

    id: int
    phone_hash: str
    phone_masked: str
    status: str
    source: str
    evidence_ref: str | None
    granted_at: datetime | None
    updated_at: datetime
    updated_by: str


def create_batch(
    session: Session,
    *,
    source_type: str,
    source_name: str,
    created_by: str,
    created_at: datetime,
) -> int:
    """Insert an empty batch row and return its id."""
    row = LeadBatch(
        source_type=source_type,
        source_name=source_name,
        total_rows=0,
        imported=0,
        duplicates=0,
        invalid=0,
        warnings=0,
        errors=[],
        created_by=created_by,
        created_at=created_at,
    )
    session.add(row)
    session.flush()
    return row.id


def finish_batch(
    session: Session,
    batch_id: int,
    *,
    total_rows: int,
    imported: int,
    duplicates: int,
    invalid: int,
    warnings: int,
    errors: list[dict[str, Any]],
) -> None:
    """Write the final counters and report into a batch row."""
    row = session.get(LeadBatch, batch_id)
    if row is None:
        return
    row.total_rows = total_rows
    row.imported = imported
    row.duplicates = duplicates
    row.invalid = invalid
    row.warnings = warnings
    row.errors = errors
    session.flush()


def get_batch(session: Session, batch_id: int) -> BatchEntry | None:
    """Return one batch by id."""
    row = session.get(LeadBatch, batch_id)
    return _to_batch(row) if row is not None else None


def list_batches(
    session: Session, *, offset: int, limit: int
) -> tuple[list[BatchEntry], int]:
    """Return one page of batches, newest first."""
    total = session.scalar(select(func.count()).select_from(LeadBatch)) or 0
    rows = session.scalars(
        select(LeadBatch).order_by(LeadBatch.id.desc()).offset(offset).limit(limit)
    ).all()
    return [_to_batch(row) for row in rows], total


def find_lead_by_username(session: Session, username: str) -> LeadEntry | None:
    """Return a lead by its normalized unique username."""
    row = session.scalar(select(Lead).where(Lead.username == username))
    return _to_lead(row) if row is not None else None


def find_lead_by_phone_hash(session: Session, phone_hash: str) -> LeadEntry | None:
    """Return the lead that owns a phone hash, if any."""
    row = session.scalar(select(Lead).where(Lead.phone_hash == phone_hash))
    return _to_lead(row) if row is not None else None


def create_lead(
    session: Session,
    *,
    batch_id: int,
    username: str,
    display_name: str | None,
    bio: str | None,
    region: str | None,
    language: str | None,
    source_url: str | None,
    phone_enc: str | None,
    phone_hash: str | None,
    phone_masked: str | None,
    created_at: datetime,
    updated_at: datetime,
) -> LeadEntry:
    """Insert a NEW lead and flush it."""
    row = Lead(
        batch_id=batch_id,
        username=username,
        display_name=display_name,
        bio=bio,
        region=region,
        language=language,
        source_url=source_url,
        phone_enc=phone_enc,
        phone_hash=phone_hash,
        phone_masked=phone_masked,
        status="NEW",
        created_at=created_at,
        updated_at=updated_at,
    )
    session.add(row)
    session.flush()
    return _to_lead(row)


def fill_missing_fields(
    session: Session,
    lead_id: int,
    *,
    display_name: str | None,
    bio: str | None,
    region: str | None,
    language: str | None,
    source_url: str | None,
    phone_enc: str | None,
    phone_hash: str | None,
    phone_masked: str | None,
    updated_at: datetime,
) -> LeadEntry | None:
    """Fill only empty lead fields; existing values always win."""
    row = session.get(Lead, lead_id)
    if row is None:
        return None
    values = {
        "display_name": display_name,
        "bio": bio,
        "region": region,
        "language": language,
        "source_url": source_url,
        "phone_enc": phone_enc,
        "phone_hash": phone_hash,
        "phone_masked": phone_masked,
    }
    changed = False
    for name, value in values.items():
        if getattr(row, name) is None and value is not None:
            setattr(row, name, value)
            changed = True
    if changed:
        row.updated_at = updated_at
        session.flush()
    return _to_lead(row)


def get_lead(session: Session, lead_id: int) -> LeadEntry | None:
    """Return one lead by id."""
    row = session.get(Lead, lead_id)
    return _to_lead(row) if row is not None else None


def list_leads(
    session: Session,
    *,
    status: str | None,
    min_score: int | None,
    batch_id: int | None,
    q: str | None,
    region: str | None,
    language: str | None,
    offset: int,
    limit: int,
) -> tuple[list[LeadEntry], int]:
    """Return one page of leads matching every given filter."""
    conditions = []
    if status:
        conditions.append(Lead.status == status)
    if min_score is not None:
        conditions.append(Lead.score >= min_score)
    if batch_id is not None:
        conditions.append(Lead.batch_id == batch_id)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(
                Lead.username.ilike(pattern, escape="\\"),
                Lead.display_name.ilike(pattern, escape="\\"),
                Lead.bio.ilike(pattern, escape="\\"),
            )
        )
    if region:
        conditions.append(Lead.region == region)
    if language:
        conditions.append(Lead.language == language)
    total_statement = select(func.count()).select_from(Lead).where(*conditions)
    total = session.scalar(total_statement) or 0
    if status == "PENDING_REVIEW":
        ordering = (Lead.score.is_(None), Lead.score.desc(), Lead.id.desc())
    else:
        ordering = (Lead.id.desc(),)
    rows = session.scalars(
        select(Lead)
        .where(*conditions)
        .order_by(*ordering)
        .offset(offset)
        .limit(limit)
    ).all()
    return [_to_lead(row) for row in rows], total


def list_pool(
    session: Session, *, offset: int, limit: int
) -> tuple[list[LeadEntry], int]:
    """Return one page of APPROVED leads, highest score first."""
    conditions = [Lead.status == "APPROVED"]
    total = session.scalar(
        select(func.count()).select_from(Lead).where(*conditions)
    ) or 0
    rows = session.scalars(
        select(Lead)
        .where(*conditions)
        .order_by(Lead.score.is_(None), Lead.score.desc(), Lead.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [_to_lead(row) for row in rows], total


def list_all_pool(session: Session) -> list[LeadEntry]:
    """Return every APPROVED lead, highest score first."""
    rows = session.scalars(
        select(Lead)
        .where(Lead.status == "APPROVED")
        .order_by(Lead.score.is_(None), Lead.score.desc(), Lead.id.desc())
    ).all()
    return [_to_lead(row) for row in rows]


def list_pool_targets(
    session: Session,
    *,
    min_score: int | None,
    batch_id: int | None,
    lead_ids: list[int] | None,
) -> list[LeadEntry]:
    """Return APPROVED leads matching every given selection condition."""
    conditions = [Lead.status == "APPROVED"]
    if min_score is not None:
        conditions.append(Lead.score >= min_score)
    if batch_id is not None:
        conditions.append(Lead.batch_id == batch_id)
    if lead_ids is not None:
        conditions.append(Lead.id.in_(lead_ids))
    rows = session.scalars(
        select(Lead)
        .where(*conditions)
        .order_by(Lead.score.is_(None), Lead.score.desc(), Lead.id)
    ).all()
    return [_to_lead(row) for row in rows]


def update_review(
    session: Session,
    lead_id: int,
    *,
    status: str,
    decision_source: str,
    reviewed_by: str,
    reviewed_at: datetime,
    review_note: str | None,
) -> None:
    """Store the outcome and metadata of one manual review."""
    row = session.get(Lead, lead_id)
    if row is None:
        return
    row.status = status
    row.decision_source = decision_source
    row.reviewed_by = reviewed_by
    row.reviewed_at = reviewed_at
    row.review_note = review_note
    row.updated_at = reviewed_at
    session.flush()


def list_for_screening(
    session: Session,
    *,
    batch_id: int | None,
    lead_ids: list[int] | None,
) -> list[LeadEntry]:
    """Return leads that machine scoring may (re)decide."""
    conditions = [Lead.status.in_(("NEW", "PENDING_REVIEW", "DISCARDED"))]
    if batch_id is not None:
        conditions.append(Lead.batch_id == batch_id)
    if lead_ids is not None:
        conditions.append(Lead.id.in_(lead_ids))
    rows = session.scalars(select(Lead).where(*conditions).order_by(Lead.id)).all()
    return [_to_lead(row) for row in rows]


def update_screening(
    session: Session,
    lead_id: int,
    *,
    score: int,
    reasons: list[dict[str, Any]],
    top_keyword: str | None,
    status: str,
    decision_source: str,
    updated_at: datetime,
) -> None:
    """Store one lead's score, explanation and decision."""
    row = session.get(Lead, lead_id)
    if row is None:
        return
    row.score = score
    row.score_reasons = reasons
    row.top_keyword = top_keyword
    row.status = status
    row.decision_source = decision_source
    row.updated_at = updated_at
    session.flush()


def find_consent(session: Session, phone_hash: str) -> ConsentEntry | None:
    """Return a consent record by phone hash."""
    row = session.scalar(
        select(ContactConsent).where(ContactConsent.phone_hash == phone_hash)
    )
    return _to_consent(row) if row is not None else None


def list_consents(session: Session) -> list[ConsentEntry]:
    """Return all consent records, most recently updated first."""
    rows = session.scalars(
        select(ContactConsent).order_by(
            ContactConsent.updated_at.desc(), ContactConsent.id.desc()
        )
    ).all()
    return [_to_consent(row) for row in rows]


def create_consent(
    session: Session,
    *,
    phone_hash: str,
    phone_masked: str,
    status: str,
    source: str,
    evidence_ref: str | None,
    granted_at: datetime | None,
    updated_at: datetime,
    updated_by: str,
) -> None:
    """Insert a consent record and flush it."""
    session.add(
        ContactConsent(
            phone_hash=phone_hash,
            phone_masked=phone_masked,
            status=status,
            source=source,
            evidence_ref=evidence_ref,
            granted_at=granted_at,
            updated_at=updated_at,
            updated_by=updated_by,
        )
    )
    session.flush()


def update_consent(
    session: Session,
    consent_id: int,
    *,
    status: str,
    source: str,
    evidence_ref: str | None,
    granted_at: datetime | None,
    updated_at: datetime,
    updated_by: str,
) -> None:
    """Overwrite a consent record's status and provenance."""
    row = session.get(ContactConsent, consent_id)
    if row is None:
        return
    row.status = status
    row.source = source
    row.evidence_ref = evidence_ref
    row.granted_at = granted_at
    row.updated_at = updated_at
    row.updated_by = updated_by
    session.flush()


def _to_batch(row: LeadBatch) -> BatchEntry:
    return BatchEntry(
        id=row.id,
        source_type=row.source_type,
        source_name=row.source_name,
        total_rows=row.total_rows,
        imported=row.imported,
        duplicates=row.duplicates,
        invalid=row.invalid,
        warnings=row.warnings,
        errors=list(row.errors or []),
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _to_lead(row: Lead) -> LeadEntry:
    return LeadEntry(
        id=row.id,
        batch_id=row.batch_id,
        username=row.username,
        display_name=row.display_name,
        bio=row.bio,
        region=row.region,
        language=row.language,
        source_url=row.source_url,
        phone_enc=row.phone_enc,
        phone_hash=row.phone_hash,
        phone_masked=row.phone_masked,
        status=row.status,
        score=row.score,
        score_reasons=row.score_reasons,
        top_keyword=row.top_keyword,
        decision_source=row.decision_source,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        review_note=row.review_note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_consent(row: ContactConsent) -> ConsentEntry:
    return ConsentEntry(
        id=row.id,
        phone_hash=row.phone_hash,
        phone_masked=row.phone_masked,
        status=row.status,
        source=row.source,
        evidence_ref=row.evidence_ref,
        granted_at=row.granted_at,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )

"""Explainable, deterministic rule-based lead scoring (pure functions)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.domain.normalize import normalize_text

_FIELDS = ("bio", "display_name", "username")


@dataclass(frozen=True)
class KeywordRule:
    """One enabled keyword with its polarity and weight."""

    term: str
    kind: str
    weight: int


@dataclass(frozen=True)
class LeadFields:
    """The fields that participate in scoring."""

    username: str
    display_name: str | None
    bio: str | None
    region: str | None
    language: str | None


@dataclass(frozen=True)
class ScreeningConfig:
    """Scoring-related settings resolved from the settings registry."""

    allowed_regions: tuple[str, ...]
    allowed_languages: tuple[str, ...]
    region_bonus: int
    region_penalty: int
    language_bonus: int
    language_penalty: int
    short_bio_min_len: int
    short_bio_penalty: int

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> ScreeningConfig:
        """Build the config from a settings mapping."""
        return cls(
            allowed_regions=tuple(values["screening.allowed_regions"]),
            allowed_languages=tuple(values["screening.allowed_languages"]),
            region_bonus=values["screening.region_bonus"],
            region_penalty=values["screening.region_penalty"],
            language_bonus=values["screening.language_bonus"],
            language_penalty=values["screening.language_penalty"],
            short_bio_min_len=values["screening.short_bio_min_len"],
            short_bio_penalty=values["screening.short_bio_penalty"],
        )


@dataclass(frozen=True)
class DecisionConfig:
    """Thresholds and the auto-approve switch."""

    threshold_high: int
    threshold_low: int
    auto_approve_enabled: bool

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> DecisionConfig:
        """Build the decision config from a settings mapping."""
        return cls(
            threshold_high=values["screening.threshold_high"],
            threshold_low=values["screening.threshold_low"],
            auto_approve_enabled=values["screening.auto_approve_enabled"],
        )


@dataclass(frozen=True)
class Reason:
    """One explanation row: code, human-readable detail and score delta."""

    code: str
    detail: str
    delta: int


@dataclass(frozen=True)
class ScoreResult:
    """Scoring output; reason deltas always sum to the score."""

    score: int
    reasons: tuple[Reason, ...]
    top_keyword: str | None


@dataclass(frozen=True)
class _Accepted:
    """A keyword match accepted in one field."""

    field: str
    contribution: int
    term: str


@lru_cache(maxsize=1024)
def _ascii_pattern(term: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in term.split()]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<![a-z0-9]){body}(?:s|es)?(?![a-z0-9])")


def _is_ascii(term: str) -> bool:
    return all(ord(char) < 128 for char in term)


def _spans(text: str, term: str) -> list[tuple[int, int]]:
    if not text:
        return []
    if _is_ascii(term):
        return [(match.start(), match.end()) for match in _ascii_pattern(term).finditer(text)]
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        index = text.find(term, start)
        if index < 0:
            return spans
        spans.append((index, index + len(term)))
        start = index + 1


def _take(spans: list[tuple[int, int]], occupied: bytearray) -> bool:
    taken = False
    for start, end in spans:
        if any(occupied[start:end]):
            continue
        occupied[start:end] = b"\x01" * (end - start)
        taken = True
    return taken


def _field_texts(lead: LeadFields) -> dict[str, str]:
    return {
        "bio": normalize_text(lead.bio or ""),
        "display_name": normalize_text(lead.display_name or ""),
        "username": normalize_text(lead.username).replace(".", " ").replace("_", " "),
    }


def _prepare(
    keywords: Sequence[KeywordRule],
) -> tuple[tuple[str, str, int], ...]:
    return _prepare_cached(tuple(keywords))


@lru_cache(maxsize=64)
def _prepare_cached(keywords: tuple[KeywordRule, ...]) -> tuple[tuple[str, str, int], ...]:
    prepared = []
    for rule in keywords:
        term = normalize_text(rule.term)
        if term:
            prepared.append((term, rule.kind, rule.weight))
    prepared.sort(key=lambda item: (-len(item[0]), item[0], item[1]))
    return tuple(prepared)


def _match_keywords(
    texts: dict[str, str], prepared: Sequence[tuple[str, str, int]]
) -> tuple[list[Reason], list[tuple[int, str]]]:
    occupied = {field: bytearray(len(text)) for field, text in texts.items()}
    reasons: list[Reason] = []
    positives: list[tuple[int, str]] = []
    for term, kind, weight in prepared:
        accepted: _Accepted | None = None
        for field in _FIELDS:
            if not _take(_spans(texts[field], term), occupied[field]):
                continue
            contribution = weight if field == "bio" else weight // 2
            if contribution > 0 and (accepted is None or contribution > accepted.contribution):
                accepted = _Accepted(field=field, contribution=contribution, term=term)
        if accepted is None:
            continue
        delta = accepted.contribution if kind == "POSITIVE" else -accepted.contribution
        code = "KW_POS" if kind == "POSITIVE" else "KW_NEG"
        reasons.append(
            Reason(code=code, detail=f"{accepted.field}:{accepted.term}", delta=delta)
        )
        if kind == "POSITIVE":
            positives.append((accepted.contribution, accepted.term))
    return reasons, positives


def _whitelist_reason(
    value: str | None,
    allowed: tuple[str, ...],
    *,
    bonus: int,
    penalty: int,
    match_code: str,
    mismatch_code: str,
) -> Reason | None:
    if not allowed or not value:
        return None
    if value in allowed:
        return Reason(code=match_code, detail=value, delta=bonus)
    return Reason(code=mismatch_code, detail=value, delta=-penalty)


def score_lead(
    lead: LeadFields,
    keywords: Sequence[KeywordRule],
    config: ScreeningConfig,
) -> ScoreResult:
    """Score one lead deterministically and explain every delta."""
    texts = _field_texts(lead)
    reasons, positives = _match_keywords(texts, _prepare(keywords))

    region_reason = _whitelist_reason(
        lead.region,
        config.allowed_regions,
        bonus=config.region_bonus,
        penalty=config.region_penalty,
        match_code="REGION_MATCH",
        mismatch_code="REGION_MISMATCH",
    )
    if region_reason is not None:
        reasons.append(region_reason)
    language_reason = _whitelist_reason(
        lead.language,
        config.allowed_languages,
        bonus=config.language_bonus,
        penalty=config.language_penalty,
        match_code="LANG_MATCH",
        mismatch_code="LANG_MISMATCH",
    )
    if language_reason is not None:
        reasons.append(language_reason)

    bio_length = len((lead.bio or "").strip())
    if bio_length < config.short_bio_min_len:
        reasons.append(
            Reason(
                code="BIO_TOO_SHORT",
                detail=f"bio length {bio_length}",
                delta=-config.short_bio_penalty,
            )
        )

    raw = sum(reason.delta for reason in reasons)
    score = max(0, min(100, raw))
    if score != raw:
        reasons.append(Reason(code="CLAMP", detail="score clamped to [0, 100]", delta=score - raw))

    top_keyword = None
    if positives:
        best = max(contribution for contribution, _ in positives)
        top_keyword = min(term for contribution, term in positives if contribution == best)
    return ScoreResult(score=score, reasons=tuple(reasons), top_keyword=top_keyword)


def decide(score: int, config: DecisionConfig) -> tuple[str, str]:
    """Map a score to (lead status, decision source) using the configured thresholds."""
    if config.auto_approve_enabled and score >= config.threshold_high:
        return "APPROVED", "AUTO"
    if score >= config.threshold_low:
        return "PENDING_REVIEW", "AUTO"
    return "DISCARDED", "AUTO"

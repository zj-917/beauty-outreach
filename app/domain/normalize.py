"""Text normalization helpers shared by config and lead ingestion."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

_EDGE_PUNCTUATION = (
    " \t\r\n.,!?;:'\"()[]{}<>，。！？；：、（）【】《》“”‘’…—–-·"
)


def normalize_text(value: str) -> str:
    """NFKC-normalize, casefold and collapse whitespace."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def normalize_inbound_text(value: str) -> str:
    """NFKC-normalize, casefold and strip surrounding whitespace and punctuation."""
    text = unicodedata.normalize("NFKC", value).casefold().strip()
    return text.strip(_EDGE_PUNCTUATION)


def matches_stop_keyword(value: str, keywords: Iterable[str]) -> bool:
    """Return True when the whole normalized text equals a stop keyword."""
    normalized = normalize_inbound_text(value)
    return any(
        normalized == normalize_inbound_text(keyword) for keyword in keywords
    )

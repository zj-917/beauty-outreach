"""Text normalization helpers shared by config and lead ingestion."""

from __future__ import annotations

import unicodedata


def normalize_text(value: str) -> str:
    """NFKC-normalize, casefold and collapse whitespace."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())

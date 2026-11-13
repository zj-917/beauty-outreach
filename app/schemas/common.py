"""Shared Pydantic annotations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import PlainSerializer


def iso_z(value: datetime) -> str:
    """Serialize a datetime as ISO-8601 with a Z suffix."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[
    datetime, PlainSerializer(iso_z, return_type=str, when_used="json")
]

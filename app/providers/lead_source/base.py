"""Lead source contract shared by all adapters."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class LeadSourceError(ValueError):
    """Raised when a source cannot deliver a parseable list of lead rows."""


@runtime_checkable
class LeadSource(Protocol):
    """A source of raw lead dictionaries with its type and display name."""

    source_type: str
    source_name: str

    def rows(self) -> list[dict[str, Any]]:
        """Return raw rows in file order."""
        ...

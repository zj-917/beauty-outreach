"""Mock dataset adapter reading data/mock_leads.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.providers.lead_source.base import LeadSourceError

DEFAULT_MOCK_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "mock_leads.json"
)


class MockLeadSource:
    """Load the bundled mock lead list."""

    source_type = "MOCK"

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_MOCK_PATH
        self.source_name = self._path.name

    def rows(self) -> list[dict[str, Any]]:
        """Return the dataset rows in file order."""
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LeadSourceError("mock dataset is missing or invalid") from exc
        if not isinstance(payload, list) or not all(
            isinstance(row, dict) for row in payload
        ):
            raise LeadSourceError("mock dataset must be a JSON array of objects")
        return payload

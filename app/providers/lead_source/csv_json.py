"""CSV and JSON upload adapter."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from app.providers.lead_source.base import LeadSourceError


class FileLeadSource:
    """Parse an uploaded .csv or .json file into raw rows."""

    def __init__(self, filename: str, content: bytes) -> None:
        if not content:
            raise LeadSourceError("uploaded file is empty")
        self.source_name = filename or "upload"
        self.source_type = self._source_type(self.source_name)
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise LeadSourceError("file must be UTF-8 encoded") from exc
        self._rows = self._parse(text)

    @staticmethod
    def _source_type(filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix == ".csv":
            return "CSV"
        if suffix == ".json":
            return "JSON"
        raise LeadSourceError("only .csv or .json uploads are supported")

    def _parse(self, text: str) -> list[dict[str, Any]]:
        if self.source_type == "JSON":
            return self._parse_json(text)
        return self._parse_csv(text)

    def _parse_json(self, text: str) -> list[dict[str, Any]]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LeadSourceError("file is not valid JSON") from exc
        if not isinstance(payload, list) or not all(
            isinstance(row, dict) for row in payload
        ):
            raise LeadSourceError("JSON upload must be an array of objects")
        return payload

    def _parse_csv(self, text: str) -> list[dict[str, Any]]:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        fieldnames = [str(name).strip() for name in reader.fieldnames or []]
        if "username" not in fieldnames:
            raise LeadSourceError("CSV requires a username column")
        rows: list[dict[str, Any]] = []
        for row in reader:
            rows.append(
                {(key or "").strip(): value for key, value in row.items()}
            )
        return rows

    def rows(self) -> list[dict[str, Any]]:
        """Return parsed rows in file order."""
        return self._rows

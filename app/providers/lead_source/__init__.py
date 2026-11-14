"""Lead source adapters: mock dataset, CSV/JSON upload, Instagram stub."""

from __future__ import annotations

from pathlib import Path

from app.providers.lead_source.base import LeadSource, LeadSourceError
from app.providers.lead_source.csv_json import FileLeadSource
from app.providers.lead_source.instagram_api import InstagramApiStub
from app.providers.lead_source.mock import MockLeadSource

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
MOCK_LEADS_PATH = DATA_DIR / "mock_leads.json"

__all__ = [
    "DATA_DIR",
    "MOCK_LEADS_PATH",
    "FileLeadSource",
    "InstagramApiStub",
    "LeadSource",
    "LeadSourceError",
    "MockLeadSource",
]

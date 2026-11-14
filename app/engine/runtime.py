"""Load runtime settings inside the engine without the service layer."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.settings import default_settings
from app.repositories import config_repo


def load_runtime_settings(session: Session) -> dict[str, Any]:
    """Return registry defaults merged with stored overrides."""
    values = default_settings()
    values.update(config_repo.list_settings(session))
    return values

"""Disabled Instagram API adapter; the prototype never calls the real API."""

from __future__ import annotations

from typing import Any

from app.core.errors import AppError


class InstagramApiStub:
    """Refuse Instagram API imports without any network activity."""

    source_type = "INSTAGRAM_API"
    source_name = "instagram_api"

    def rows(self) -> list[dict[str, Any]]:
        """Always fail with the provider-disabled error."""
        raise AppError(
            "PROVIDER_NOT_ENABLED",
            "Instagram API import is disabled in this prototype",
        )

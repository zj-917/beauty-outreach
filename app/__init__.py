"""Beauty Outreach application package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    APP_VERSION = version("beauty-outreach")
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled source tree
    APP_VERSION = "0.1.0"

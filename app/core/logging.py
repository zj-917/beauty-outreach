"""Logging setup and request-id propagation."""

from __future__ import annotations

import logging
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure one application log handler, idempotently."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for existing in root.handlers:
        if getattr(existing, "_beauty_outreach", False):
            return
    handler = logging.StreamHandler()
    handler._beauty_outreach = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)

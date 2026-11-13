"""Logging setup, request-id propagation and message redaction."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

Redactor = Callable[[str], str]

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


class RedactionFilter(logging.Filter):
    """Sanitize every log message with the injected redactor."""

    def __init__(self, redactor: Redactor) -> None:
        super().__init__()
        self._redactor = redactor

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redactor(record.getMessage())
        record.args = ()
        return True


def configure_logging(level: str, *, redactor: Redactor) -> None:
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
    handler.addFilter(RedactionFilter(redactor))
    root.addHandler(handler)

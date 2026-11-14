"""Logging redaction formatter tests."""

from __future__ import annotations

import io
import logging

from app.core.logging import RedactingFormatter
from app.domain.masking import redact_log_text


def _logger(name: str, stream: io.StringIO) -> logging.Logger:
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingFormatter("%(message)s", redact_log_text))
    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger


def test_AC_AUD_008_log_filter_masks_phone_and_sensitive_headers() -> None:
    """Given a log line with a phone and secret headers, when formatted, then values are masked."""
    stream = io.StringIO()
    logger = _logger("tests.redaction", stream)
    logger.info(
        "contact +1 555-555-0101\n"
        "X-Admin-Token: admin-secret\n"
        "Authorization: Bearer bearer-secret\n"
        "X-Hub-Signature-256: sha256=deadbeef"
    )
    output = stream.getvalue()
    assert "+1 555-555-0101" not in output
    assert "admin-secret" not in output
    assert "bearer-secret" not in output
    assert "deadbeef" not in output
    assert "X-Admin-Token: ***" in output
    assert "Authorization: ***" in output
    assert "X-Hub-Signature-256: ***" in output


def test_AC_AUD_008_log_formatter_redacts_tracebacks() -> None:
    """Given an exception carrying a phone, when logged, then the traceback is masked too."""
    stream = io.StringIO()
    logger = _logger("tests.redaction.traceback", stream)
    try:
        raise RuntimeError("delivery failed for +1 555-555-0101")
    except RuntimeError:
        logger.exception("outreach failed")
    output = stream.getvalue()
    assert "RuntimeError" in output
    assert "555-555-0101" not in output

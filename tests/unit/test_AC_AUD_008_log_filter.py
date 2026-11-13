"""Logging redaction filter tests."""

from __future__ import annotations

import io
import logging

from app.core.logging import RedactionFilter
from app.domain.masking import redact_log_text


def test_AC_AUD_008_log_filter_masks_phone_and_sensitive_headers() -> None:
    """Given a log line with a phone and secret headers, when filtered, then values are masked."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactionFilter(redact_log_text))
    logger = logging.getLogger("tests.redaction")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.info(
        "contact +1 555-555-0101 X-Admin-Token: admin-secret "
        "Authorization: Bearer bearer-secret X-Hub-Signature-256: sha256=deadbeef"
    )
    output = stream.getvalue()
    assert "+1 555-555-0101" not in output
    assert "admin-secret" not in output
    assert "bearer-secret" not in output
    assert "deadbeef" not in output
    assert "X-Admin-Token: ***" in output
    assert "Authorization: ***" in output
    assert "X-Hub-Signature-256: ***" in output

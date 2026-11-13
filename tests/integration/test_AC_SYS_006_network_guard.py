"""Network guard fixture test."""

from __future__ import annotations

import socket

import pytest


def test_AC_SYS_006_outbound_connections_are_blocked() -> None:
    """Given the autouse guard, when dialing a non-loopback address, then it raises at once."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match="network access is disabled"):
            sock.connect(("203.0.113.1", 80))
    finally:
        sock.close()

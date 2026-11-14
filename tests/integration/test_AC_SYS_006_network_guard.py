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


def test_AC_SYS_006_connect_ex_is_blocked() -> None:
    """Given the autouse guard, when using connect_ex, then it raises at once."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match="network access is disabled"):
            sock.connect_ex(("203.0.113.1", 80))
    finally:
        sock.close()


def test_AC_SYS_006_dns_lookup_is_blocked() -> None:
    """Given the autouse guard, when resolving a public host, then it raises at once."""
    with pytest.raises(RuntimeError, match="network access is disabled"):
        socket.getaddrinfo("example.com", 80)


def test_AC_SYS_006_udp_sendto_is_blocked() -> None:
    """Given the autouse guard, when sending a datagram, then it raises at once."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(RuntimeError, match="network access is disabled"):
            sock.sendto(b"probe", ("203.0.113.1", 53))
    finally:
        sock.close()

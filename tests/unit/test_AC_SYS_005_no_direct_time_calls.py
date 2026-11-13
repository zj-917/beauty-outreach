"""Architecture guard: business code must not read the system clock directly."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

from app.core.clock import FakeClock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
ALLOWED_FILES = {APP / "core" / "clock.py"}

FORBIDDEN_CALLS = {
    "time.time",
    "time.sleep",
    "time.monotonic",
    "time.perf_counter",
    "datetime.datetime.now",
    "datetime.datetime.utcnow",
    "datetime.datetime.today",
    "datetime.date.today",
}


def _aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _call_name(node: ast.AST, aliases: dict[str, str]) -> str:
    parts: list[str] = []
    target = node
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if not isinstance(target, ast.Name):
        return ""
    parts.append(target.id)
    parts.reverse()
    parts[0] = aliases.get(parts[0], parts[0])
    return ".".join(parts)


def test_AC_SYS_005_no_direct_time_calls_outside_clock() -> None:
    """Given app source, when scanned, then only core/clock.py reads the system clock."""
    offenders: list[str] = []
    for path in APP.rglob("*.py"):
        if path in ALLOWED_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = _aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node.func, aliases)
                if name in FORBIDDEN_CALLS:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} {name}")
    assert offenders == []


def test_AC_SYS_005_fake_clock_advances_without_real_time() -> None:
    """Given a FakeClock, when advanced, then now() moves deterministically."""
    clock = FakeClock(datetime(2026, 11, 14, 9, 0, tzinfo=UTC))
    clock.advance(90)
    assert clock.now().isoformat() == "2026-11-14T09:01:30+00:00"
    assert clock.monotonic() == 90.0

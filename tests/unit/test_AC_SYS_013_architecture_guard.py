"""Architecture guard: layers may only depend downward."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"

ALLOWED_LAYER_IMPORTS = {
    "api": {"api", "schemas", "services", "core"},
    "schemas": {"schemas"},
    "services": {"services", "domain", "repositories", "providers", "engine", "core", "schemas"},
    "engine": {"engine", "domain", "repositories", "providers", "core"},
    "repositories": {"repositories", "models", "core"},
    "models": {"models"},
    "providers": {"providers", "domain", "core"},
    "domain": {"domain"},
    "core": {"core"},
}

FORBIDDEN_DOMAIN_IMPORTS = {
    "fastapi",
    "sqlalchemy",
    "httpx",
    "requests",
    "socket",
    "urllib",
    "http",
    "aiohttp",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _layer(path: Path) -> str | None:
    parts = path.relative_to(APP).parts
    return parts[0] if len(parts) > 1 else None


def test_AC_SYS_013_domain_has_no_io_imports() -> None:
    """Given domain modules, when scanned, then no framework, DB or network import exists."""
    for path in (APP / "domain").rglob("*.py"):
        violations = {
            name for name in _imports(path) if name.split(".")[0] in FORBIDDEN_DOMAIN_IMPORTS
        }
        assert not violations, f"{path.relative_to(ROOT)} imports {violations}"


def test_AC_SYS_013_layers_depend_only_downward() -> None:
    """Given each layer, when its app imports are scanned, then only allowed layers are used."""
    violations: list[str] = []
    for path in APP.rglob("*.py"):
        layer = _layer(path)
        if layer not in ALLOWED_LAYER_IMPORTS:
            continue
        for name in _imports(path):
            if not name.startswith("app."):
                continue
            target = name.split(".")[1]
            if target not in ALLOWED_LAYER_IMPORTS[layer]:
                violations.append(f"{path.relative_to(ROOT)} imports {name}")
    assert violations == []

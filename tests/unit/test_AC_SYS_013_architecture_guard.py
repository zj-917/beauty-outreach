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

# Composition-root modules at app/ may import any layer; every other top-level
# module must be added here explicitly.
ROOT_MODULES = {"__init__.py", "main.py"}

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


def _resolve_relative(path: Path, module: str | None, level: int) -> str | None:
    """Resolve a relative ``from`` import against the file's package path."""
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    package = parts[:-1]
    ups = level - 1
    if ups > len(package):
        return None
    base = package[: len(package) - ups] if ups else package
    if module:
        return ".".join([*base, module])
    return ".".join(base)


def _imports_from_source(source: str, path: Path) -> set[str]:
    """Return every imported module name, expanding relative and ``from app import x`` forms."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = (
                node.module
                if node.level == 0
                else _resolve_relative(path, node.module, node.level)
            )
            if module is None:
                continue
            names.add(module)
            if module == "app":
                for alias in node.names:
                    candidate = APP / alias.name
                    if candidate.is_dir() or candidate.with_suffix(".py").exists():
                        names.add(f"app.{alias.name}")
    return names


def _imports(path: Path) -> set[str]:
    return _imports_from_source(path.read_text(encoding="utf-8"), path)


def _layer(path: Path) -> str | None:
    parts = path.relative_to(APP).parts
    return parts[0] if len(parts) > 1 else None


def _layer_violations(path: Path, source: str | None = None) -> list[str]:
    """Return human-readable layer violations for one file, or for probe source."""
    layer = _layer(path)
    if layer is None:
        if path.name in ROOT_MODULES:
            return []
        return [f"{path.relative_to(ROOT)} is a top-level module missing from ROOT_MODULES"]
    if layer not in ALLOWED_LAYER_IMPORTS:
        return []
    allowed = ALLOWED_LAYER_IMPORTS[layer]
    imports = (
        _imports_from_source(source, path) if source is not None else _imports(path)
    )
    violations: list[str] = []
    for name in sorted(imports):
        if not name.startswith("app."):
            continue
        target = name.split(".")[1]
        if target not in allowed:
            violations.append(f"{path.relative_to(ROOT)} imports {name}")
    return violations


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
        violations.extend(_layer_violations(path))
    assert violations == []


def test_AC_SYS_013_guard_resolves_relative_imports() -> None:
    """Given a relative cross-layer import, when probed, then the guard reports it."""
    probe = APP / "domain" / "probe.py"
    assert any(
        "app.api" in item
        for item in _layer_violations(probe, "from ..api import lead\n")
    )


def test_AC_SYS_013_guard_resolves_from_app_imports() -> None:
    """Given ``from app import providers`` inside domain, when probed, then it is reported."""
    probe = APP / "domain" / "probe.py"
    assert any(
        "app.providers" in item
        for item in _layer_violations(probe, "from app import providers\n")
    )


def test_AC_SYS_013_guard_checks_top_level_modules() -> None:
    """Given the composition root, then its imports pass; unknown top-level files are flagged."""
    assert _layer_violations(APP / "main.py", "from app.api import lead\n") == []
    probe = APP / "sandbox.py"
    assert any(
        "missing from ROOT_MODULES" in item for item in _layer_violations(probe, "")
    )

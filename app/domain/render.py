"""Pure template variable extraction, sanitization and rendering."""

from __future__ import annotations

import re
from collections.abc import Mapping

VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-z_]+)\s*(?:\|([^}]*))?\}\}")
ALLOWED_VARIABLES = frozenset({"name", "username", "keyword", "brand", "optout_text"})
LEAD_VARIABLES = frozenset({"name", "username", "keyword"})
MAX_LEAD_VALUE_LENGTH = 60
MAX_RENDER_LENGTH = 1024
_LINE_BREAKS = re.compile(r"[\r\n]+")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\t]")


class RenderError(Exception):
    """Raised when a template cannot be rendered."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(self.detail)


def extract_variables(body: str) -> list[str]:
    """Return distinct variable names in order of first appearance."""
    seen: set[str] = set()
    names: list[str] = []
    for match in VARIABLE_PATTERN.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def unknown_variables(body: str) -> list[str]:
    """Return distinct variables outside the whitelist, in order of appearance."""
    return [name for name in extract_variables(body) if name not in ALLOWED_VARIABLES]


def build_values(
    *,
    display_name: str | None,
    username: str,
    top_keyword: str | None,
    brand: str,
    optout_text: str,
) -> dict[str, str | None]:
    """Map a lead and settings onto the template variable namespace."""
    return {
        "name": display_name or username,
        "username": username,
        "keyword": top_keyword,
        "brand": brand,
        "optout_text": optout_text,
    }


def _sanitize(value: str) -> str:
    text = _LINE_BREAKS.sub(" ", value)
    return _CONTROL_CHARS.sub("", text).strip()


def _clean(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    text = _sanitize(value)
    if name in LEAD_VARIABLES:
        text = text[:MAX_LEAD_VALUE_LENGTH]
    return text or None


def render(body: str, values: Mapping[str, str | None]) -> str:
    """Render one template pass, append the opt-out footer and enforce the length cap."""
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2)
        cleaned = _clean(name, values.get(name))
        if cleaned is not None:
            return cleaned
        if default is not None:
            return _sanitize(default)
        missing.append(name)
        return match.group(0)

    rendered = VARIABLE_PATTERN.sub(replace, body)
    if missing:
        names = ", ".join(dict.fromkeys(missing))
        raise RenderError(
            "TEMPLATE_VARIABLE_MISSING", f"missing values for: {names}"
        )
    if "optout_text" not in extract_variables(body):
        footer = _clean("optout_text", values.get("optout_text"))
        if footer:
            rendered = f"{rendered}\n\n{footer}"
    if len(rendered) > MAX_RENDER_LENGTH:
        raise RenderError(
            "RENDER_TOO_LONG",
            f"rendered body exceeds {MAX_RENDER_LENGTH} characters",
        )
    return rendered

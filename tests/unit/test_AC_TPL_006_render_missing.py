"""Rendering of missing variables and determinism."""

from __future__ import annotations

import pytest

from app.domain.render import RenderError, build_values, render


def _values() -> dict[str, str | None]:
    return build_values(
        display_name="Alex",
        username="alex",
        top_keyword=None,
        brand="GlowLab",
        optout_text="Reply STOP.",
    )


def test_AC_TPL_006_missing_variable_without_default_raises() -> None:
    """Given a missing keyword and no default, when rendered, then RenderError is raised."""
    with pytest.raises(RenderError) as excinfo:
        render("About {{keyword}}.", _values())

    assert excinfo.value.code == "TEMPLATE_VARIABLE_MISSING"
    assert "keyword" in str(excinfo.value)


def test_AC_TPL_006_render_is_deterministic() -> None:
    """Given the same input, when rendered twice, then both results are identical."""
    body = "Hi {{name}} from {{brand}} about {{keyword|beauty}}"

    assert render(body, _values()) == render(body, _values())

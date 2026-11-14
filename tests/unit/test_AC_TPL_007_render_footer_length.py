"""Opt-out footer and rendered length limit tests."""

from __future__ import annotations

import pytest

from app.domain.render import MAX_RENDER_LENGTH, RenderError, build_values, render

OPT_OUT = "Reply STOP."


def _values() -> dict[str, str | None]:
    return build_values(
        display_name="Alex",
        username="alex",
        top_keyword="beauty",
        brand="GlowLab",
        optout_text=OPT_OUT,
    )


def test_AC_TPL_007_appends_footer_when_absent() -> None:
    """Given a body without optout_text, when rendered, then the footer is appended."""
    rendered = render("Hello {{name}}", _values())

    assert rendered == "Hello Alex\n\nReply STOP."


def test_AC_TPL_007_does_not_duplicate_footer_when_present() -> None:
    """Given a body already containing optout_text, when rendered, then no footer is appended."""
    rendered = render("Hello {{name}}. {{ optout_text }}", _values())

    assert rendered == "Hello Alex. Reply STOP."
    assert "Reply STOP.\n\nReply STOP." not in rendered


def test_AC_TPL_007_render_length_boundary() -> None:
    """Given rendered output at 1024 characters, when rendered, then it passes; 1025 fails."""
    at_limit = "a" * (MAX_RENDER_LENGTH - len(OPT_OUT)) + "{{optout_text}}"
    assert len(render(at_limit, _values())) == MAX_RENDER_LENGTH

    over_limit = "a" * (MAX_RENDER_LENGTH - len(OPT_OUT) + 1) + "{{optout_text}}"
    with pytest.raises(RenderError) as excinfo:
        render(over_limit, _values())

    assert excinfo.value.code == "RENDER_TOO_LONG"

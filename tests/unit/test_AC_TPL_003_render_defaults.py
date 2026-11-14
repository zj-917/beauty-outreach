"""Rendering defaults, fallbacks and whitespace syntax."""

from __future__ import annotations

from app.domain.render import build_values, render

OPT_OUT = "Reply STOP."


def _values(**overrides: object) -> dict[str, str | None]:
    base: dict[str, object] = {
        "display_name": "Alex",
        "username": "alex",
        "top_keyword": "beauty devices",
        "brand": "GlowLab",
        "optout_text": OPT_OUT,
    }
    base.update(overrides)
    return build_values(**base)  # type: ignore[arg-type]


def test_AC_TPL_003_name_falls_back_to_username_when_display_name_missing() -> None:
    """Given a lead without display_name, when rendered, then name uses the username."""
    rendered = render("Hi {{name|there}}, welcome!", _values(display_name=None))

    assert rendered == "Hi alex, welcome!\n\nReply STOP."


def test_AC_TPL_003_keyword_default_and_whitespace_syntax() -> None:
    """Given a missing keyword with a default, when rendered, then the default applies."""
    rendered = render(
        "About {{ keyword | beauty devices }} from {{ brand }}.",
        _values(top_keyword=None),
    )

    assert rendered == "About beauty devices from GlowLab.\n\nReply STOP."


def test_AC_TPL_003_display_name_wins_when_present() -> None:
    """Given a display name, when rendered, then name uses it instead of the username."""
    rendered = render("Hi {{name}}!", _values())

    assert rendered == "Hi Alex!\n\nReply STOP."

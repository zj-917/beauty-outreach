"""Lead value sanitization and single-pass rendering tests."""

from __future__ import annotations

from app.domain.render import build_values, render


def _values(**overrides: object) -> dict[str, str | None]:
    base: dict[str, object] = {
        "display_name": "Alex",
        "username": "alex",
        "top_keyword": "beauty",
        "brand": "GlowLab",
        "optout_text": "Reply STOP.",
    }
    base.update(overrides)
    return build_values(**base)  # type: ignore[arg-type]


def test_AC_TPL_008_cleans_newlines_control_chars_and_whitespace() -> None:
    """Given line breaks and control characters, when rendered, then the value is cleaned."""
    rendered = render("Hi {{name}}!", _values(display_name="  Line1\nLine2\x00\x07  "))

    assert rendered.startswith("Hi Line1 Line2!")


def test_AC_TPL_008_truncates_lead_values_to_60_codepoints() -> None:
    """Given overlong lead values, when rendered, then name and keyword stop at 60 characters."""
    rendered = render(
        "{{name}}|{{keyword}}",
        _values(display_name="a" * 70, top_keyword="k" * 70),
    )

    assert rendered == "a" * 60 + "|" + "k" * 60 + "\n\nReply STOP."


def test_AC_TPL_008_truncation_does_not_split_emoji() -> None:
    """Given an emoji display name, when truncated, then code points are not broken."""
    rendered = render("{{name}}", _values(display_name="😀" * 61))

    assert rendered.startswith("😀" * 60 + "\n")
    assert len(rendered.split("\n\n")[0]) == 60


def test_render_does_not_reinterpret_variable_values() -> None:
    """Given a value containing placeholder syntax, when rendered, then it is inserted literally."""
    rendered = render("Hi {{name}}", _values(display_name="{{brand}}"))

    assert rendered.startswith("Hi {{brand}}\n")

"""Inbound stop text detection tests."""

from __future__ import annotations

import pytest

from app.domain.normalize import matches_stop_keyword, normalize_inbound_text
from app.domain.settings import default_settings

KEYWORDS = default_settings()["compliance.stop_keywords"]


@pytest.mark.parametrize(
    "text",
    [
        "STOP",
        " stop. ",
        "Stop!",
        "stop!!!",
        "ＳＴＯＰ",
        "退订",
        "退订。",
        "取消订阅",
        "ＣＡＮＣＥＬ",
    ],
)
def test_inbound_stop_text_matches_whole_words(text: str) -> None:
    """Given punctuation, case or width variants, when normalized, then STOP matches."""
    assert matches_stop_keyword(text, KEYWORDS)


@pytest.mark.parametrize(
    "text",
    ["please don't stop", "stopping", "stop now", "unsubscribe me", "", "   "],
)
def test_inbound_stop_text_rejects_extra_words(text: str) -> None:
    """Given text with extra words, when normalized, then it is not a STOP."""
    assert not matches_stop_keyword(text, KEYWORDS)


def test_normalize_inbound_text_strips_punctuation_and_casefolds() -> None:
    """Given punctuation and full-width letters, when normalized, then it is canonical."""
    assert normalize_inbound_text("  ＳＴＯＰ！ ") == "stop"
    assert normalize_inbound_text("退订。") == "退订"

"""Keyword matching edge-case tests."""

from __future__ import annotations

from app.domain.scoring import KeywordRule, LeadFields, ScreeningConfig, score_lead
from app.domain.settings import default_settings

NEUTRAL_BIO = "nothing relevant here at all"


def _config(allowed_regions: list[str] | None = None) -> ScreeningConfig:
    values = default_settings()
    values["screening.allowed_regions"] = allowed_regions or []
    values["screening.allowed_languages"] = []
    return ScreeningConfig.from_mapping(values)


def _score(term: str, bio: str | None, username: str = "someone", display_name: str | None = None):
    lead = LeadFields(
        username=username,
        display_name=display_name,
        bio=bio,
        region=None,
        language=None,
    )
    return score_lead(lead, [KeywordRule(term, "POSITIVE", 10)], _config())


def test_AC_SCR_004_ascii_terms_need_word_boundaries() -> None:
    """Given a short term, when it appears inside another word, then it does not match."""
    assert _score("rf", "surf & perfume") == _score("rf", NEUTRAL_BIO)
    assert _score("rf", "rf routines").score == 10


def test_AC_SCR_004_plural_forms_match_multiword_terms() -> None:
    """Given a multiword term, when the text uses its plural, then it matches."""
    result = _score("led mask", "LED masks daily")
    assert result.score == 10
    assert result.reasons[0].detail == "bio:led mask"


def test_AC_SCR_004_chinese_terms_match_by_substring() -> None:
    """Given a Chinese term, when it is embedded in Chinese text, then it matches."""
    assert _score("美容仪", "今天聊美容仪器和护肤心得").score == 10
    assert _score("美容仪", "今天聊护肤").score == 0


def test_AC_SCR_004_is_case_and_width_insensitive() -> None:
    """Given full-width or mixed-case text, when normalized, then ASCII terms match."""
    assert _score("beauty device", "ＢＥＡＵＴＹ ＤＥＶＩＣＥ").score == 10
    assert _score("beauty device", "Beauty Devices").score == 10


def test_AC_SCR_004_username_dots_and_underscores_are_spaces() -> None:
    """Given a username with separators, when matched, then separators act as spaces."""
    result = _score("led mask", NEUTRAL_BIO, username="led_mask.daily")
    assert result.score == 5
    assert result.reasons[0].detail == "username:led mask"

"""Keyword contribution tests."""

from __future__ import annotations

from app.domain.scoring import KeywordRule, LeadFields, ScreeningConfig, score_lead
from app.domain.settings import default_settings

NEUTRAL_BIO = "nothing relevant here at all"


def _config() -> ScreeningConfig:
    return ScreeningConfig.from_mapping(default_settings())


def _score(*keywords: KeywordRule, **lead_fields: str | None):
    lead = LeadFields(
        username=lead_fields.get("username", "someone"),
        display_name=lead_fields.get("display_name"),
        bio=lead_fields.get("bio"),
        region=None,
        language=None,
    )
    return score_lead(lead, list(keywords), _config())


def test_AC_SCR_002_bio_counts_full_weight() -> None:
    """Given a bio hit, then the full weight is added once."""
    result = _score(KeywordRule("beauty device", "POSITIVE", 30), bio="beauty device review")
    assert result.score == 30
    assert result.reasons[0].detail == "bio:beauty device"


def test_AC_SCR_002_display_name_and_username_count_half_weight() -> None:
    """Given only a display-name or username hit, then floor(weight/2) is added."""
    display = _score(
        KeywordRule("beauty device", "POSITIVE", 25),
        display_name="beauty device",
        bio=NEUTRAL_BIO,
    )
    assert display.score == 12
    username = _score(
        KeywordRule("led mask", "POSITIVE", 25),
        username="led_mask.daily",
        bio=NEUTRAL_BIO,
    )
    assert username.score == 12
    assert username.reasons[0].detail == "username:led mask"


def test_AC_SCR_002_same_keyword_counts_only_once_across_fields() -> None:
    """Given a term in bio and display name, then only the largest contribution counts."""
    result = _score(
        KeywordRule("beauty device", "POSITIVE", 30),
        display_name="beauty device",
        bio="my beauty device diary",
    )
    assert result.score == 30
    assert [reason.detail for reason in result.reasons] == ["bio:beauty device"]

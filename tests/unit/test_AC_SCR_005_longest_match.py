"""Longest-match precedence tests."""

from __future__ import annotations

from app.domain.scoring import KeywordRule, LeadFields, ScreeningConfig, score_lead
from app.domain.settings import default_settings

RULES = [
    KeywordRule("beauty device", "POSITIVE", 30),
    KeywordRule("beauty", "POSITIVE", 10),
]


def _score(bio: str):
    values = default_settings()
    values["screening.allowed_regions"] = []
    values["screening.allowed_languages"] = []
    lead = LeadFields(
        username="someone",
        display_name=None,
        bio=bio,
        region=None,
        language=None,
    )
    return score_lead(lead, RULES, ScreeningConfig.from_mapping(values))


def test_AC_SCR_005_longer_term_consumes_beauty() -> None:
    """Given both terms, when only the phrase appears, then only the phrase scores."""
    result = _score("beauty device reviews")
    assert result.score == 30
    assert [reason.detail for reason in result.reasons] == ["bio:beauty device"]


def test_AC_SCR_005_standalone_beauty_still_scores() -> None:
    """Given a separate beauty occurrence, then it is counted as its own match."""
    result = _score("beauty device reviews and beauty tips")
    assert result.score == 40
    assert {reason.detail for reason in result.reasons} == {
        "bio:beauty device",
        "bio:beauty",
    }

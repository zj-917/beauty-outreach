"""Negative keyword tests."""

from __future__ import annotations

from app.domain.scoring import KeywordRule, LeadFields, ScreeningConfig, score_lead
from app.domain.settings import default_settings
from app.services.seed_service import DEFAULT_KEYWORDS


def _rules() -> list[KeywordRule]:
    return [KeywordRule(term, kind, weight) for term, kind, weight in DEFAULT_KEYWORDS]


def _config() -> ScreeningConfig:
    return ScreeningConfig.from_mapping(default_settings())


def test_AC_SCR_003_negative_keywords_subtract_weight() -> None:
    """Given wholesale and dropship, when scored, then the example raw score clamps to 0."""
    lead = LeadFields(
        username="wholesale.dev",
        display_name=None,
        bio="Wholesale beauty device supplier — DM for dropship",
        region=None,
        language=None,
    )
    result = score_lead(lead, _rules(), _config())
    assert result.score == 0
    negatives = [reason for reason in result.reasons if reason.code == "KW_NEG"]
    assert {reason.detail for reason in negatives} == {
        "bio:wholesale",
        "bio:dropship",
    }
    assert next(r for r in result.reasons if r.code == "CLAMP").delta == 30
    assert sum(reason.delta for reason in result.reasons) == result.score


def test_AC_SCR_003_first_hand_example_reaches_100() -> None:
    """Given the spec example lead, when scored, then it clamps to 100."""
    lead = LeadFields(
        username="glow.with.mia",
        display_name="Mia",
        bio="Reviewing beauty devices, LED masks & microcurrent tools | skincare nerd",
        region="US",
        language="en",
    )
    result = score_lead(lead, _rules(), _config())
    assert result.score == 100
    assert result.top_keyword == "beauty device"
    assert sum(reason.delta for reason in result.reasons) == 100

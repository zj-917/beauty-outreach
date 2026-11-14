"""Top keyword tests."""

from __future__ import annotations

from app.domain.scoring import KeywordRule, LeadFields, ScreeningConfig, score_lead
from app.domain.settings import default_settings

CONFIG = ScreeningConfig.from_mapping(default_settings())


def _lead(bio: str) -> LeadFields:
    return LeadFields("someone", None, bio, None, None)


def test_AC_SCR_015_top_keyword_is_the_largest_contributor() -> None:
    """Given several positive hits, then the largest weight is selected."""
    rules = [
        KeywordRule("led mask", "POSITIVE", 25),
        KeywordRule("beauty device", "POSITIVE", 30),
        KeywordRule("skincare", "POSITIVE", 15),
    ]
    result = score_lead(_lead("beauty device, led mask and skincare"), rules, CONFIG)
    assert result.top_keyword == "beauty device"


def test_AC_SCR_015_ties_use_lexicographic_order() -> None:
    """Given equal contributions, then the lexicographically smallest term wins."""
    rules = [
        KeywordRule("zebra", "POSITIVE", 20),
        KeywordRule("alpha", "POSITIVE", 20),
    ]
    result = score_lead(_lead("zebra and alpha"), rules, CONFIG)
    assert result.top_keyword == "alpha"


def test_AC_SCR_015_no_positive_hit_means_null() -> None:
    """Given only negative hits, then top_keyword is null."""
    rules = [KeywordRule("wholesale", "NEGATIVE", 30)]
    result = score_lead(_lead("wholesale only"), rules, CONFIG)
    assert result.top_keyword is None


def test_AC_SCR_015_zero_contribution_hits_are_ignored() -> None:
    """Given a weight-1 hit only in display_name, then it adds no reason and no top keyword."""
    rules = [KeywordRule("beauty device", "POSITIVE", 1)]
    lead = LeadFields("someone", "beauty device", "nothing relevant here at all", None, None)
    result = score_lead(lead, rules, CONFIG)
    assert result.score == 0
    assert result.reasons == ()
    assert result.top_keyword is None

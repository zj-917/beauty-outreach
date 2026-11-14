"""Score bound tests."""

from __future__ import annotations

import pytest

from app.domain.scoring import KeywordRule, LeadFields, ScreeningConfig, score_lead
from app.domain.settings import default_settings
from app.services.seed_service import DEFAULT_KEYWORDS

CONFIG = ScreeningConfig.from_mapping(default_settings())
RULES = [KeywordRule(term, kind, weight) for term, kind, weight in DEFAULT_KEYWORDS]


@pytest.mark.parametrize(
    "bio",
    [
        None,
        "",
        "short",
        "beauty",
        "beauty device led mask microcurrent radio frequency red light therapy",
        "wholesale dropship reseller giveaway follow4follow f4f",
        "美容仪 导入仪 射频 抗衰 护肤 美妆",
    ],
)
def test_AC_SCR_008_score_is_an_integer_within_bounds(bio: str | None) -> None:
    """Given varied inputs, then the score is always an integer in [0, 100]."""
    lead = LeadFields(
        username="some.user",
        display_name="Name",
        bio=bio,
        region="US",
        language="en",
    )
    result = score_lead(lead, RULES, CONFIG)
    assert isinstance(result.score, int)
    assert 0 <= result.score <= 100

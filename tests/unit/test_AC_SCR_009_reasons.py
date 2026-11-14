"""Reason structure and delta-sum tests."""

from __future__ import annotations

import json

from app.domain.scoring import KeywordRule, LeadFields, ScreeningConfig, score_lead
from app.domain.settings import default_settings
from app.services.seed_service import DEFAULT_KEYWORDS

CONFIG = ScreeningConfig.from_mapping(default_settings())
RULES = [KeywordRule(term, kind, weight) for term, kind, weight in DEFAULT_KEYWORDS]
ALLOWED_CODES = {
    "KW_POS",
    "KW_NEG",
    "REGION_MATCH",
    "REGION_MISMATCH",
    "LANG_MATCH",
    "LANG_MISMATCH",
    "BIO_TOO_SHORT",
    "CLAMP",
}

LEADS = [
    LeadFields("glow.with.mia", "Mia", "beauty device led mask skincare", "US", "en"),
    LeadFields("wholesale.dev", None, "Wholesale beauty device supplier", None, None),
    LeadFields("someone", None, None, "FR", "de"),
    LeadFields("美妆日记", None, "护肤日常", "TW", "zh"),
]


def test_AC_SCR_009_every_reason_is_well_formed_and_sums_to_score() -> None:
    """Given any result, then each reason has code/detail/delta and the deltas sum to score."""
    for lead in LEADS:
        result = score_lead(lead, RULES, CONFIG)
        assert sum(reason.delta for reason in result.reasons) == result.score
        for reason in result.reasons:
            assert reason.code in ALLOWED_CODES
            assert isinstance(reason.detail, str) and reason.detail
            assert isinstance(reason.delta, int)
        json.dumps([reason.__dict__ for reason in result.reasons])


def test_AC_SCR_009_clamp_only_appears_when_needed() -> None:
    """Given in-range scores, then no CLAMP reason is emitted."""
    lead = LeadFields("someone", None, "beauty device and skincare", "US", "en")
    result = score_lead(lead, RULES, CONFIG)
    assert 0 < result.score < 100
    assert all(reason.code != "CLAMP" for reason in result.reasons)

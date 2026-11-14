"""Scoring determinism tests."""

from __future__ import annotations

import random

from app.domain.scoring import KeywordRule, LeadFields, ScreeningConfig, score_lead
from app.domain.settings import default_settings
from app.services.seed_service import DEFAULT_KEYWORDS


def _rules() -> list[KeywordRule]:
    return [KeywordRule(term, kind, weight) for term, kind, weight in DEFAULT_KEYWORDS]


def test_AC_SCR_001_same_input_scores_identically() -> None:
    """Given the same lead and config, when scored repeatedly, then results are identical."""
    lead = LeadFields(
        username="glow.with.mia",
        display_name="Mia",
        bio="Reviewing beauty devices, LED masks & microcurrent tools | skincare nerd",
        region="US",
        language="en",
    )
    config = ScreeningConfig.from_mapping(default_settings())
    first = score_lead(lead, _rules(), config)
    for _ in range(4):
        assert score_lead(lead, _rules(), config) == first


def test_AC_SCR_001_keyword_order_does_not_matter() -> None:
    """Given shuffled keywords, when scored, then score, reasons and top_keyword match."""
    lead = LeadFields(
        username="beauty.device.fan",
        display_name="Fan",
        bio="beauty device and skincare device lover",
        region="US",
        language="en",
    )
    config = ScreeningConfig.from_mapping(default_settings())
    expected = score_lead(lead, _rules(), config)
    rules = _rules()
    random.Random(7).shuffle(rules)
    assert score_lead(lead, rules, config) == expected

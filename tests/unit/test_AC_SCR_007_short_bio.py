"""Short-bio penalty tests."""

from __future__ import annotations

from app.domain.scoring import LeadFields, ScreeningConfig, score_lead
from app.domain.settings import default_settings


def _score(bio: str | None):
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
    return score_lead(lead, [], ScreeningConfig.from_mapping(values))


def test_AC_SCR_007_empty_or_short_bio_is_penalized() -> None:
    """Given a null or short bio, then the penalty applies and is explained."""
    for bio in (None, "", "short"):
        result = _score(bio)
        assert result.score == 0
        assert any(reason.code == "BIO_TOO_SHORT" for reason in result.reasons)
        assert sum(reason.delta for reason in result.reasons) == 0


def test_AC_SCR_007_bio_at_minimum_length_is_not_penalized() -> None:
    """Given a bio exactly at the minimum length, then no penalty is applied."""
    result = _score("abcdefghij")
    assert result.reasons == ()
    assert result.score == 0

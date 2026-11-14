"""Region and language adjustment tests."""

from __future__ import annotations

from app.domain.scoring import LeadFields, ScreeningConfig, score_lead
from app.domain.settings import default_settings

BIO = "nothing relevant here at all"


def _config(**overrides):
    values = default_settings()
    values.update({"screening.region_bonus": 10, "screening.region_penalty": 20})
    values.update(overrides)
    return ScreeningConfig.from_mapping(values)


def _score(region: str | None, language: str | None, config: ScreeningConfig):
    lead = LeadFields(
        username="someone",
        display_name=None,
        bio=BIO,
        region=region,
        language=language,
    )
    return score_lead(lead, [], config)


def test_AC_SCR_006_allowed_region_adds_bonus() -> None:
    """Given a whitelisted region, then the bonus is added with a reason."""
    result = _score("US", "en", _config())
    assert result.score == 15
    assert {reason.code for reason in result.reasons} == {
        "REGION_MATCH",
        "LANG_MATCH",
    }


def test_AC_SCR_006_other_region_subtracts_penalty() -> None:
    """Given a region outside the list, then the penalty is applied."""
    result = _score("FR", "de", _config())
    assert result.score == 0
    assert {reason.code for reason in result.reasons} == {
        "REGION_MISMATCH",
        "LANG_MISMATCH",
        "CLAMP",
    }
    assert sum(reason.delta for reason in result.reasons) == 0


def test_AC_SCR_006_missing_value_is_neutral() -> None:
    """Given no region or language, then no adjustment reason is emitted."""
    result = _score(None, None, _config())
    assert result.score == 0
    assert result.reasons == ()


def test_AC_SCR_006_empty_whitelist_skips_the_dimension() -> None:
    """Given an empty whitelist, then even a foreign value is not penalized."""
    result = _score(
        "FR",
        "de",
        _config(
            **{
                "screening.allowed_regions": [],
                "screening.allowed_languages": [],
            }
        ),
    )
    assert result.score == 0
    assert result.reasons == ()

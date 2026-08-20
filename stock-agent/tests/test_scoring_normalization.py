from decimal import Decimal

from app.scoring.bands import score_band
from app.scoring.normalization import (
    explain_score,
    normalize_current_ratio,
    normalize_linear_higher_is_better,
    normalize_linear_lower_is_better,
)
from app.scoring.thresholds import LinearBand


def d(value) -> Decimal:
    return Decimal(str(value))


BAND = LinearBand(floor=d(0), target=d(20))


def test_linear_higher_is_better_midpoint():
    assert normalize_linear_higher_is_better(d(10), BAND) == d(50)


def test_linear_higher_is_better_below_floor_clamped_zero():
    assert normalize_linear_higher_is_better(d(-100), BAND) == d(0)


def test_linear_higher_is_better_above_target_clamped_hundred():
    assert normalize_linear_higher_is_better(d(1000), BAND) == d(100)


def test_linear_higher_is_better_at_floor_is_zero():
    assert normalize_linear_higher_is_better(d(0), BAND) == d(0)


def test_linear_higher_is_better_at_target_is_hundred():
    assert normalize_linear_higher_is_better(d(20), BAND) == d(100)


def test_linear_lower_is_better_midpoint():
    assert normalize_linear_lower_is_better(d(10), BAND) == d(50)


def test_linear_lower_is_better_below_floor_clamped_hundred():
    assert normalize_linear_lower_is_better(d(-100), BAND) == d(100)


def test_linear_lower_is_better_above_target_clamped_zero():
    assert normalize_linear_lower_is_better(d(1000), BAND) == d(0)


# --- current ratio sweet spot --------------------------------------------------


def test_current_ratio_zero_is_zero():
    assert normalize_current_ratio(d(0)) == d(0)


def test_current_ratio_negative_clamped_zero():
    assert normalize_current_ratio(d(-1)) == d(0)


def test_current_ratio_danger_zone_below_one():
    assert normalize_current_ratio(d("0.5")) == d(30)  # half of 60


def test_current_ratio_ramps_to_hundred_between_one_and_ideal_low():
    score = normalize_current_ratio(d("1.25"))
    assert d(60) < score < d(100)


def test_current_ratio_ideal_plateau_is_hundred():
    assert normalize_current_ratio(d("1.5")) == d(100)
    assert normalize_current_ratio(d("2.0")) == d(100)
    assert normalize_current_ratio(d("3.0")) == d(100)


def test_current_ratio_excessive_zone_eases_down():
    score = normalize_current_ratio(d("4.5"))
    assert d(70) < score < d(100)


def test_current_ratio_extremely_high_floors_at_seventy_not_zero():
    assert normalize_current_ratio(d(1000)) == d(70)


# --- explain_score ---------------------------------------------------------------


def test_explain_score_high_and_low_tiers_differ():
    high = explain_score("ROE", d(90))
    low = explain_score("ROE", d(5))
    assert high != low
    assert "ROE" in high and "ROE" in low


# --- score bands ------------------------------------------------------------------


def test_score_band_boundaries():
    assert score_band(d(95)).value == "excellent"
    assert score_band(d(90)).value == "excellent"
    assert score_band(d(89)).value == "strong"
    assert score_band(d(80)).value == "strong"
    assert score_band(d(79)).value == "good"
    assert score_band(d(70)).value == "good"
    assert score_band(d(69)).value == "fair"
    assert score_band(d(60)).value == "fair"
    assert score_band(d(59)).value == "weak"
    assert score_band(d(40)).value == "weak"
    assert score_band(d(39)).value == "poor"
    assert score_band(d(0)).value == "poor"

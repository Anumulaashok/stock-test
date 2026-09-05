from app.forecasting.ml.ensemble import ModelOutput, combine, weights_from_mae
from app.forecasting.ml.quality import ForecastQuality, QualityInputs, assess_quality


def test_weights_from_mae_favors_lower_error():
    weights = weights_from_mae({"a": 0.01, "b": 0.05})
    assert weights["a"] > weights["b"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_weights_from_mae_zero_for_missing_or_invalid():
    weights = weights_from_mae({"a": 0.02, "b": None, "c": 0.0})
    assert weights["b"] == 0.0
    assert weights["c"] == 0.0
    assert weights["a"] == 1.0


def test_combine_weighted_average_matches_manual_calculation():
    outputs = [
        ModelOutput("a", point_return=0.10, distribution=None, probability_positive=0.7, weight=0.8),
        ModelOutput("b", point_return=-0.02, distribution=None, probability_positive=0.4, weight=0.2),
    ]
    result = combine(outputs)
    expected = 0.10 * 0.8 + (-0.02) * 0.2
    assert abs(result.expected_return - expected) < 1e-9


def test_combine_falls_back_to_equal_weight_when_all_weights_zero():
    outputs = [
        ModelOutput("a", point_return=0.05, distribution=None, probability_positive=None, weight=0.0),
        ModelOutput("b", point_return=0.15, distribution=None, probability_positive=None, weight=0.0),
    ]
    result = combine(outputs)
    assert abs(result.expected_return - 0.10) < 1e-9  # simple average of 0.05 and 0.15


def test_model_agreement_is_one_when_all_models_agree_on_direction():
    outputs = [
        ModelOutput("a", 0.05, None, None, 1.0),
        ModelOutput("b", 0.02, None, None, 1.0),
        ModelOutput("c", 0.10, None, None, 1.0),
    ]
    result = combine(outputs)
    assert result.model_agreement == 1.0


def test_model_agreement_drops_when_models_disagree():
    outputs = [
        ModelOutput("a", 0.05, None, None, 1.0),
        ModelOutput("b", -0.05, None, None, 1.0),
    ]
    result = combine(outputs)
    assert result.model_agreement == 0.5


def _quality_inputs(**overrides) -> QualityInputs:
    base = dict(
        analog_sample_size=100, model_agreement=0.9, directional_accuracy=0.65,
        interval_width=0.10, annualized_volatility=0.20, feature_completeness=1.0,
        regime_is_unknown=False,
    )
    base.update(overrides)
    return QualityInputs(**base)


def test_strong_inputs_yield_high_quality():
    assessment = assess_quality(_quality_inputs())
    assert assessment.quality == ForecastQuality.HIGH


def test_small_analog_sample_and_disagreement_yield_low_quality():
    assessment = assess_quality(
        _quality_inputs(analog_sample_size=3, model_agreement=0.3, directional_accuracy=0.48, interval_width=0.6, annualized_volatility=0.6)
    )
    assert assessment.quality == ForecastQuality.LOW
    assert any("small" in r.lower() for r in assessment.reasons)
    assert any("disagreement" in r.lower() for r in assessment.reasons)


def test_missing_directional_accuracy_is_noted_not_fabricated():
    assessment = assess_quality(_quality_inputs(directional_accuracy=None))
    assert any("no out-of-sample accuracy" in r.lower() for r in assessment.reasons)

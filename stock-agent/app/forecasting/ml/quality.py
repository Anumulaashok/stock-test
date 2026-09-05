"""Forecast-quality scoring (spec section 23) -- replaces a single
"confidence" number with HIGH/MEDIUM/LOW plus the concrete reasons that
drove the label. Every input here must be a real computed value from the
rest of the pipeline (walk-forward accuracy, analog sample size, model
agreement, quantile width, volatility, feature completeness) -- never a
hand-tuned constant standing in for one of them.
"""

from dataclasses import dataclass
from enum import StrEnum


class ForecastQuality(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class QualityInputs:
    analog_sample_size: int
    model_agreement: float  # 0..1
    directional_accuracy: float | None  # from walk-forward, this horizon
    interval_width: float | None  # p90 - p10, as a return fraction
    annualized_volatility: float | None
    feature_completeness: float  # 0..1, fraction of expected features present
    regime_is_unknown: bool


@dataclass(frozen=True)
class QualityAssessment:
    quality: ForecastQuality
    score: float  # 0..1, informational
    reasons: list[str]


_HIGH_VOL_THRESHOLD = 0.45
_WIDE_INTERVAL_THRESHOLD = 0.35
_MIN_RELIABLE_ANALOG_SAMPLE = 20
_MIN_GOOD_DIRECTIONAL_ACCURACY = 0.55


def assess_quality(inputs: QualityInputs) -> QualityAssessment:
    reasons: list[str] = []
    points = 0.0
    total_weight = 0.0

    def score_component(weight: float, value: float, reason_if_low: str | None) -> None:
        nonlocal points, total_weight
        points += weight * value
        total_weight += weight
        if reason_if_low and value < 0.5:
            reasons.append(reason_if_low)

    score_component(
        0.25, min(inputs.analog_sample_size / (_MIN_RELIABLE_ANALOG_SAMPLE * 2), 1.0),
        "Historical analog sample is small" if inputs.analog_sample_size < _MIN_RELIABLE_ANALOG_SAMPLE else None,
    )
    score_component(
        0.20, inputs.model_agreement,
        "Model disagreement is high" if inputs.model_agreement < 0.6 else None,
    )
    if inputs.directional_accuracy is not None:
        score_component(
            0.25, max(min((inputs.directional_accuracy - 0.45) / 0.25, 1.0), 0.0),
            "Out-of-sample directional accuracy is weak" if inputs.directional_accuracy < _MIN_GOOD_DIRECTIONAL_ACCURACY else None,
        )
    else:
        reasons.append("No out-of-sample accuracy history yet for this horizon")

    if inputs.interval_width is not None:
        width_score = max(1.0 - inputs.interval_width / (_WIDE_INTERVAL_THRESHOLD * 2), 0.0)
        score_component(0.15, width_score, "Prediction interval is wide" if inputs.interval_width > _WIDE_INTERVAL_THRESHOLD else None)

    if inputs.annualized_volatility is not None:
        vol_score = max(1.0 - inputs.annualized_volatility / (_HIGH_VOL_THRESHOLD * 1.5), 0.0)
        score_component(0.10, vol_score, "Volatility is elevated" if inputs.annualized_volatility > _HIGH_VOL_THRESHOLD else None)

    score_component(0.05, inputs.feature_completeness, "Some input data (fundamentals/technicals) is missing" if inputs.feature_completeness < 0.8 else None)

    if inputs.regime_is_unknown:
        reasons.append("Market regime could not be determined (insufficient price history)")

    overall = points / total_weight if total_weight > 0 else 0.0
    if overall >= 0.70 and inputs.analog_sample_size >= _MIN_RELIABLE_ANALOG_SAMPLE:
        quality = ForecastQuality.HIGH
    elif overall >= 0.45:
        quality = ForecastQuality.MEDIUM
    else:
        quality = ForecastQuality.LOW

    if not reasons:
        reasons.append("Sufficient historical sample, models agree, and out-of-sample accuracy is adequate")

    return QualityAssessment(quality=quality, score=overall, reasons=reasons)

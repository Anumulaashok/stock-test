"""Ensemble layer (spec section 19/21).

Weights come from out-of-sample walk-forward performance
(`app.forecasting.ml.validation`), not arbitrary hardcoded confidence:
a model with lower walk-forward MAE for a given horizon gets more say in
that horizon's ensemble. A model that produced no usable walk-forward
folds (e.g. too little history) gets weight 0 rather than an assumed
default, and if every model has weight 0 the ensemble falls back to
equal weighting across whichever models actually produced a prediction
for this row -- never silently drops to a single arbitrary model.
"""

from dataclasses import dataclass

import numpy as np

QUANTILE_KEYS = ["p10", "p25", "p50", "p75", "p90"]


@dataclass(frozen=True)
class ModelOutput:
    model_name: str
    point_return: float
    distribution: dict[str, float] | None  # quantile key -> return
    probability_positive: float | None
    weight: float


@dataclass(frozen=True)
class EnsembleOutput:
    expected_return: float
    quantiles: dict[str, float]
    probability_positive: float
    model_outputs: list[ModelOutput]
    model_agreement: float  # 0..1, how much models agree on direction


def weights_from_mae(mae_by_model: dict[str, float | None]) -> dict[str, float]:
    """Inverse-MAE weighting: `weight_i = (1/mae_i) / sum(1/mae_j)`.
    A model with `None` or non-positive MAE (no valid walk-forward
    result) gets weight 0."""
    usable = {name: mae for name, mae in mae_by_model.items() if mae is not None and mae > 0}
    if not usable:
        return {name: 0.0 for name in mae_by_model}
    inverse = {name: 1.0 / mae for name, mae in usable.items()}
    total = sum(inverse.values())
    weights = {name: inverse.get(name, 0.0) / total for name in mae_by_model}
    return weights


def combine(model_outputs: list[ModelOutput]) -> EnsembleOutput:
    usable = [m for m in model_outputs if m.weight > 0]
    if not usable:
        usable = model_outputs  # fall back to equal weighting across everything available
        usable = [ModelOutput(m.model_name, m.point_return, m.distribution, m.probability_positive, 1.0) for m in usable]

    total_weight = sum(m.weight for m in usable) or 1.0
    expected_return = sum(m.point_return * m.weight for m in usable) / total_weight

    quantiles: dict[str, float] = {}
    for key in QUANTILE_KEYS:
        contributions = [(m.distribution[key], m.weight) for m in usable if m.distribution and key in m.distribution]
        if contributions:
            weight_sum = sum(w for _, w in contributions) or 1.0
            quantiles[key] = sum(v * w for v, w in contributions) / weight_sum

    probability_contributions = [
        (m.probability_positive, m.weight) for m in usable if m.probability_positive is not None
    ]
    if probability_contributions:
        weight_sum = sum(w for _, w in probability_contributions) or 1.0
        probability_positive = sum(v * w for v, w in probability_contributions) / weight_sum
    else:
        probability_positive = float(expected_return > 0)

    directions = np.sign([m.point_return for m in usable if m.point_return != 0])
    if len(directions) == 0:
        agreement = 1.0
    else:
        majority = 1 if (directions > 0).sum() >= (directions < 0).sum() else -1
        agreement = float((directions == majority).mean())

    return EnsembleOutput(
        expected_return=float(expected_return),
        quantiles=quantiles,
        probability_positive=float(probability_positive),
        model_outputs=model_outputs,
        model_agreement=agreement,
    )

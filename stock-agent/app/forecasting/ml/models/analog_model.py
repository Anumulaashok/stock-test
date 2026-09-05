"""Wraps the historical-analog engine (spec section 7) as a
`ForecastModel` (spec section 16, model 6) so the ensemble can weigh it
alongside the tree models without special-casing it.

Unlike the tree models, this one has no real "fit" step in the
scikit-learn sense -- `fit` just remembers the training pool (features +
target) as the candidate library `predict`/`predict_distribution` search
against. It is deliberately not vectorized across rows internally (the
distance search is O(pool size) per query row), which is fine: this
model is evaluated on a handful of prediction dates at a time (walk-
forward folds, or a single live prediction), never dataset-wide.
"""

import numpy as np
import pandas as pd

from app.forecasting.ml.analog import find_analogs
from app.forecasting.ml.horizons import MlHorizon
from app.forecasting.ml.models.base import ForecastModel


class HistoricalAnalogModel(ForecastModel):
    name = "historical_analog"

    def __init__(self, horizon: MlHorizon, k: int = 60) -> None:
        self._horizon = horizon
        self._k = k
        self._pool: pd.DataFrame | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        pool = X.copy()
        pool[f"target_return_{self._horizon.value}"] = y
        self._pool = pool

    def _row_stats(self, row: pd.Series) -> tuple[float | None, dict[str, float] | None, float | None]:
        if self._pool is None:
            return None, None, None
        result = find_analogs(query_features=row, candidate_pool=self._pool, k=self._k)
        stats = result.horizon_stats[self._horizon]
        if not stats.is_reliable:
            return None, None, None
        return stats.mean_return, stats.quantiles, stats.positive_rate

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self._pool is None:
            return np.zeros(len(X))
        out = np.zeros(len(X))
        for i, (_, row) in enumerate(X.iterrows()):
            mean_return, _, _ = self._row_stats(row)
            out[i] = mean_return if mean_return is not None else 0.0
        return out

    def predict_distribution(self, X: pd.DataFrame) -> dict[str, np.ndarray] | None:
        if self._pool is None:
            return None
        keys = ["p10", "p25", "p50", "p75", "p90"]
        columns = {key: np.full(len(X), np.nan) for key in keys}
        any_reliable = False
        for i, (_, row) in enumerate(X.iterrows()):
            _, quantiles, _ = self._row_stats(row)
            if quantiles is None:
                continue
            any_reliable = True
            for key in keys:
                columns[key][i] = quantiles[key]
        return columns if any_reliable else None

    def predict_probability_positive(self, X: pd.DataFrame) -> np.ndarray | None:
        if self._pool is None:
            return None
        out = np.full(len(X), np.nan)
        any_reliable = False
        for i, (_, row) in enumerate(X.iterrows()):
            _, _, positive_rate = self._row_stats(row)
            if positive_rate is None:
                continue
            any_reliable = True
            out[i] = positive_rate
        return out if any_reliable else None

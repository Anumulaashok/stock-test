"""Baseline models (spec section 16, Baseline 1 & 2) -- the floor every
other model must beat in backtesting (spec section 33)."""

import numpy as np
import pandas as pd

from app.forecasting.ml.models.base import ForecastModel


class NaiveReturnModel(ForecastModel):
    """Predicts zero return (i.e. "price stays flat") -- the simplest
    possible baseline, requires no training data at all."""

    name = "naive_zero_return"

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        return None

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.zeros(len(X))


class HistoricalMeanModel(ForecastModel):
    """Predicts the training set's mean historical return for this
    horizon, ignoring the current feature vector entirely -- the second
    baseline spec section 16 calls for."""

    name = "historical_mean_return"

    def __init__(self) -> None:
        self._mean_return: float = 0.0
        self._std_return: float = 0.0

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        clean = y.dropna()
        self._mean_return = float(clean.mean()) if len(clean) else 0.0
        self._std_return = float(clean.std()) if len(clean) > 1 else 0.0

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self._mean_return)

    def predict_distribution(self, X: pd.DataFrame) -> dict[str, np.ndarray] | None:
        if self._std_return <= 0:
            return None
        from scipy.stats import norm

        quantile_levels = {"p10": 0.10, "p25": 0.25, "p50": 0.50, "p75": 0.75, "p90": 0.90}
        n = len(X)
        return {
            key: np.full(n, self._mean_return + norm.ppf(level) * self._std_return)
            for key, level in quantile_levels.items()
        }

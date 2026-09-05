"""Tree-ensemble models (spec section 16, models 3 & 4).

LightGBM/XGBoost are skipped deliberately (spec: "when dependency
compatibility permits") -- LightGBM needs a system `libomp` install this
environment doesn't have. `HistGradientBoostingRegressor(loss="quantile")`
gives genuine per-quantile model output (fit once per quantile level)
instead of residual-bootstrapped intervals, which is what spec section 18
prefers when available ("Prefer a model capable of producing prediction
intervals or quantile estimates").
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor

from app.forecasting.ml.models.base import ForecastModel

QUANTILE_LEVELS = {"p10": 0.10, "p25": 0.25, "p50": 0.50, "p75": 0.75, "p90": 0.90}


class RandomForestReturnModel(ForecastModel):
    name = "random_forest"

    def __init__(self, n_estimators: int = 200, max_depth: int = 6, random_state: int = 42) -> None:
        self._model = RandomForestRegressor(
            n_estimators=n_estimators, max_depth=max_depth, min_samples_leaf=20,
            random_state=random_state, n_jobs=-1,
        )
        self._fitted = False

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        self._model.fit(X, y)
        self._fitted = True

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self._fitted:
            return np.zeros(len(X))
        return self._model.predict(X)

    def predict_distribution(self, X: pd.DataFrame) -> dict[str, np.ndarray] | None:
        if not self._fitted:
            return None
        # Per-tree predictions approximate the model's own predictive
        # distribution -- a documented, cheap way to get quantiles out of
        # a forest without training a separate quantile-regression forest.
        X_values = X.to_numpy()
        tree_predictions = np.stack([tree.predict(X_values) for tree in self._model.estimators_], axis=0)
        return {
            key: np.percentile(tree_predictions, level * 100, axis=0)
            for key, level in QUANTILE_LEVELS.items()
        }

    def predict_probability_positive(self, X: pd.DataFrame) -> np.ndarray | None:
        if not self._fitted:
            return None
        X_values = X.to_numpy()
        tree_predictions = np.stack([tree.predict(X_values) for tree in self._model.estimators_], axis=0)
        return (tree_predictions > 0).mean(axis=0)


class GradientBoostingQuantileModel(ForecastModel):
    """Fits one `HistGradientBoostingRegressor` per quantile level plus
    one squared-error model for the point estimate -- five to six small
    fits, all fast enough for on-demand/offline training (spec section
    32), never at request time."""

    name = "gradient_boosting_quantile"

    def __init__(self, max_iter: int = 150, max_depth: int = 4, random_state: int = 42) -> None:
        self._params = dict(max_iter=max_iter, max_depth=max_depth, random_state=random_state)
        self._point_model = HistGradientBoostingRegressor(loss="squared_error", **self._params)
        self._quantile_models: dict[str, HistGradientBoostingRegressor] = {}
        self._fitted = False

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        self._point_model.fit(X, y)
        for key, level in QUANTILE_LEVELS.items():
            model = HistGradientBoostingRegressor(loss="quantile", quantile=level, **self._params)
            model.fit(X, y)
            self._quantile_models[key] = model
        self._fitted = True

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self._fitted:
            return np.zeros(len(X))
        return self._point_model.predict(X)

    def predict_distribution(self, X: pd.DataFrame) -> dict[str, np.ndarray] | None:
        if not self._fitted:
            return None
        raw = {key: model.predict(X) for key, model in self._quantile_models.items()}
        # Quantile crossing (p25 predicted above p50, etc.) can happen
        # with independently-fit quantile models -- sort per-row so the
        # reported interval is always monotonic.
        stacked = np.stack([raw[key] for key in QUANTILE_LEVELS], axis=1)
        stacked.sort(axis=1)
        return {key: stacked[:, i] for i, key in enumerate(QUANTILE_LEVELS)}

    def predict_probability_positive(self, X: pd.DataFrame) -> np.ndarray | None:
        distribution = self.predict_distribution(X)
        if distribution is None:
            return None
        return _probability_positive_from_quantiles(distribution)


def _probability_positive_from_quantiles(distribution: dict[str, np.ndarray]) -> np.ndarray:
    """Linear-interpolates the quantile function to estimate P(return >
    0) -- used by any model that only produces quantiles, not a direct
    classifier probability."""
    levels = np.array(list(QUANTILE_LEVELS.values()))
    values = np.stack([distribution[key] for key in QUANTILE_LEVELS], axis=1)
    n = values.shape[0]
    result = np.empty(n)
    for i in range(n):
        row = values[i]
        if row[-1] <= 0:
            result[i] = 0.0
        elif row[0] >= 0:
            result[i] = 1.0
        else:
            prob_below_zero = float(np.interp(0.0, row, levels))
            result[i] = 1.0 - prob_below_zero
    return result

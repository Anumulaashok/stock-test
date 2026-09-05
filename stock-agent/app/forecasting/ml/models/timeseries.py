"""Autoregressive time-series baseline (statsmodels `AutoReg`).

Architectural note this model must be read against: every other model
in this ensemble (`tree_models.py`, `baseline.py`) is cross-sectional --
it maps a feature vector at one (ticker, date) row to a return, and
generalizes across tickers because every feature is already a
ticker-relative ratio (see `training.py`'s pooling rationale). A true
ARIMA/AutoReg model is the opposite: it is fit on ONE continuous,
date-ordered series and forecasts the next step(s) of that same series.

The pooled walk-forward training set here interleaves many tickers'
non-contiguous dates in one fold. There is no well-defined way to roll
an AR model forward per-ticker inside that scheme without either (a)
retraining a separate AR model per ticker per fold (a much larger
architectural change than "add one more model to the registry"), or (b)
pretending the pooled series is one continuous sequence it is not.

This model does neither. It fits `AutoReg` on the fold's return series
in the order given (capturing real serial-correlation structure in
returns -- something `HistoricalMeanModel`'s flat mean cannot), and
uses that fit's one-step-ahead forecast as a single scalar applied to
every row in the test set, exactly the way `HistoricalMeanModel` applies
its scalar mean. It is a legitimate autoregressive baseline, not a
per-ticker forecast -- do not present it as the latter.
"""

import logging

import numpy as np
import pandas as pd

from app.forecasting.ml.models.base import ForecastModel

logger = logging.getLogger(__name__)

MIN_OBSERVATIONS_MULTIPLIER = 3


class AutoRegReturnModel(ForecastModel):
    name = "autoreg_return"

    def __init__(self, lags: int = 5) -> None:
        self._lags = lags
        self._forecast_value: float = 0.0

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        clean = y.dropna()
        if len(clean) < self._lags * MIN_OBSERVATIONS_MULTIPLIER:
            self._forecast_value = float(clean.mean()) if len(clean) else 0.0
            return
        try:
            from statsmodels.tsa.ar_model import AutoReg

            fitted = AutoReg(clean.to_numpy(), lags=self._lags).fit()
            forecast = fitted.predict(start=len(clean), end=len(clean))
            self._forecast_value = float(forecast[0])
        except Exception:
            logger.warning("autoreg_fit_failed rows=%d lags=%d", len(clean), self._lags, exc_info=True)
            self._forecast_value = float(clean.mean())

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self._forecast_value)

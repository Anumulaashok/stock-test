"""Modular forecast-model interface (spec section 16).

Every model predicts *return* (spec section 4), not price -- price is
derived only at presentation time (see `app.forecasting.ml.pipeline`).
Models are not forced into a single output shape: `predict` always
returns a point estimate, but `predict_distribution` may return a wide
or narrow set of quantiles depending on what the underlying model can
actually produce (spec section 16: "Do not force every model to produce
the same type of output") -- a model that cannot support quantiles
returns `None` and the ensemble/quality layer accounts for that rather
than fabricating one.
"""

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class ForecastModel(ABC):
    name: str = "base"

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None: ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Point estimate of return, one per row of `X`."""

    def predict_distribution(self, X: pd.DataFrame) -> dict[str, np.ndarray] | None:
        """Optional: {"p10": array, "p25": array, ..., "p90": array},
        one value per row of `X`. `None` means this model does not
        produce a distribution -- the ensemble falls back to residual-
        based intervals for it (see `app.forecasting.ml.validation`)."""
        return None

    def predict_probability_positive(self, X: pd.DataFrame) -> np.ndarray | None:
        """Optional: P(return > 0) per row. `None` means the ensemble
        derives it from the point estimate + residual distribution
        instead of a direct classifier output."""
        return None

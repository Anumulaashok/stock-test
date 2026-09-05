"""AutoRegReturnModel (app.forecasting.ml.models.timeseries) -- the
statsmodels-backed autoregressive baseline added to MODEL_FACTORIES."""

import numpy as np
import pandas as pd
import pytest

from app.forecasting.ml.models.timeseries import AutoRegReturnModel
from app.forecasting.ml.training import MODEL_FACTORIES


def test_registered_in_model_factories():
    assert "autoreg_return" in MODEL_FACTORIES
    assert MODEL_FACTORIES["autoreg_return"] is AutoRegReturnModel


def test_predict_returns_one_value_per_row():
    rng = np.random.default_rng(42)
    y = pd.Series(rng.normal(0, 0.01, size=200))
    X = pd.DataFrame(index=y.index)

    model = AutoRegReturnModel(lags=5)
    model.fit(X, y)
    predicted = model.predict(X.iloc[:10])

    assert predicted.shape == (10,)
    assert np.all(np.isfinite(predicted))


def test_predict_is_a_constant_across_rows_not_per_row_lookahead():
    # This model does not have a well-defined per-ticker continuous
    # rollout in the pooled walk-forward scheme (see the module
    # docstring) -- it must apply one scalar forecast uniformly, the
    # same way HistoricalMeanModel does, never a distinct value per row.
    rng = np.random.default_rng(7)
    y = pd.Series(rng.normal(0, 0.01, size=100))
    X = pd.DataFrame(index=y.index)

    model = AutoRegReturnModel(lags=5)
    model.fit(X, y)
    predicted = model.predict(X.iloc[:20])

    assert len(set(predicted.tolist())) == 1


def test_falls_back_to_the_mean_with_too_little_data_for_the_lag_order():
    y = pd.Series([0.01, -0.02, 0.03])
    X = pd.DataFrame(index=y.index)

    model = AutoRegReturnModel(lags=5)
    model.fit(X, y)

    assert model.predict(X) == pytest.approx(np.full(3, y.mean()))


def test_empty_training_series_predicts_zero_not_a_crash():
    y = pd.Series([], dtype=float)
    X = pd.DataFrame(index=y.index)

    model = AutoRegReturnModel(lags=5)
    model.fit(X, y)

    assert model.predict(pd.DataFrame(index=[0, 1])) == pytest.approx([0.0, 0.0])


def test_real_autoreg_fit_engages_not_the_exception_fallback(caplog):
    # Regression test: an earlier version passed `old_names=False` to
    # `AutoReg`, a kwarg the installed statsmodels (0.15) doesn't
    # accept -- every fit silently hit the except branch and fell back
    # to the plain mean, identical to HistoricalMeanModel, without any
    # test catching it (the other tests here only check output shape,
    # not which code path produced it). Asserting no warning was logged
    # is what actually distinguishes "real AR fit" from "silent
    # fallback."
    rng = np.random.default_rng(3)
    y = pd.Series(rng.normal(0, 0.01, size=200))
    X = pd.DataFrame(index=y.index)

    with caplog.at_level("WARNING"):
        model = AutoRegReturnModel(lags=5)
        model.fit(X, y)

    assert not any("autoreg_fit_failed" in record.message for record in caplog.records)


def test_has_no_distribution_or_probability_output_ensemble_falls_back():
    # Base ForecastModel defaults -- this model doesn't claim a
    # distribution or a direct P(positive) it can't actually produce.
    y = pd.Series(np.random.default_rng(1).normal(0, 0.01, size=50))
    X = pd.DataFrame(index=y.index)
    model = AutoRegReturnModel()
    model.fit(X, y)

    assert model.predict_distribution(X) is None
    assert model.predict_probability_positive(X) is None

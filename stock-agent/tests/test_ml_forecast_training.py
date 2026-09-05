"""app.forecasting.ml.training -- the offline training/walk-forward
orchestration layer. Neither train_all_horizons() nor run_training()
had any direct test coverage before this file (only exercised
indirectly, and only along degraded/empty paths, via
test_ml_forecast_api.py and test_ml_forecast_cache.py's fake
pipeline) -- this is real end-to-end coverage of "does training
actually train and weight models correctly," per the master brief's
test-requirement list (model training, ensemble calculations, walk-
forward evaluation)."""

import numpy as np
import pandas as pd

from app.forecasting.ml.horizons import MlHorizon
from app.forecasting.ml.targets import target_column
from app.forecasting.ml.training import MIN_ROWS_PER_HORIZON, MODEL_FACTORIES, train_all_horizons


def _synthetic_pooled_dataset(n_rows: int = 400, seed: int = 7) -> pd.DataFrame:
    """One feature (`price_vs_sma50`) is constructed to genuinely
    predict the 14D target return; the rest of MODEL_FACTORIES'
    baselines have nothing to learn from it. A model that actually
    fits the relationship should out-perform naive/historical-mean on
    walk-forward MAE -- if it doesn't, something in the training loop
    is broken, not just "the model wasn't good enough this time."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_rows)
    price_vs_sma50 = rng.normal(0, 0.05, size=n_rows)
    noise = rng.normal(0, 0.01, size=n_rows)
    target_14d = 0.5 * price_vs_sma50 + noise

    return pd.DataFrame(
        {
            "date": dates,
            "ticker": "SYN",
            "price_vs_sma50": price_vs_sma50,
            target_column(MlHorizon.D14): target_14d,
        }
    )


def test_train_all_horizons_returns_a_result_for_a_horizon_with_enough_rows():
    pooled = _synthetic_pooled_dataset()
    results = train_all_horizons(pooled)

    assert MlHorizon.D14 in results
    result = results[MlHorizon.D14]
    assert set(result.weights.keys()) == set(MODEL_FACTORIES.keys())
    assert set(result.performance.keys()) <= set(MODEL_FACTORIES.keys())


def test_skips_a_horizon_with_no_target_column_at_all():
    pooled = _synthetic_pooled_dataset()
    results = train_all_horizons(pooled)
    assert MlHorizon.M1 not in results  # never had a target_return_1M column


def test_skips_a_horizon_below_the_minimum_row_count():
    pooled = _synthetic_pooled_dataset(n_rows=MIN_ROWS_PER_HORIZON - 1)
    results = train_all_horizons(pooled)
    assert MlHorizon.D14 not in results


def test_a_model_that_can_learn_the_real_relationship_beats_the_naive_baseline():
    pooled = _synthetic_pooled_dataset(n_rows=600)
    result = train_all_horizons(pooled)[MlHorizon.D14]

    naive_mae = result.performance["naive_zero_return"]["mean_mae_across_folds"]
    gbm_mae = result.performance["gradient_boosting_quantile"]["mean_mae_across_folds"]
    assert gbm_mae < naive_mae


def test_weight_zero_means_no_valid_walk_forward_result_not_a_penalty_for_being_bad():
    # naive_zero_return has a real (if worse) walk-forward MAE here --
    # it should get a small positive weight, never 0, since 0 is
    # reserved for "no fold produced a usable MAE at all" (ensemble.py).
    pooled = _synthetic_pooled_dataset(n_rows=600)
    result = train_all_horizons(pooled)[MlHorizon.D14]
    assert result.weights["naive_zero_return"] > 0


def test_every_model_in_the_registry_gets_a_weight_even_if_zero():
    pooled = _synthetic_pooled_dataset(n_rows=600)
    result = train_all_horizons(pooled)[MlHorizon.D14]
    assert set(result.weights.keys()) == set(MODEL_FACTORIES.keys())
    assert all(w >= 0 for w in result.weights.values())

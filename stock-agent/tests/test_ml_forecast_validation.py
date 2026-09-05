import numpy as np
import pandas as pd

from app.forecasting.ml.validation import evaluate_predictions, walk_forward_splits


def test_walk_forward_folds_never_test_on_dates_before_train_end():
    dates = pd.Series(pd.bdate_range("2020-01-01", periods=1000))
    folds = walk_forward_splits(dates, n_folds=5)
    assert len(folds) > 0
    for fold in folds:
        train_dates = dates[fold.train_mask]
        test_dates = dates[fold.test_mask]
        assert train_dates.max() <= fold.train_end
        assert test_dates.min() > fold.train_end
        assert test_dates.max() <= fold.test_end


def test_walk_forward_folds_are_expanding_not_random():
    dates = pd.Series(pd.bdate_range("2020-01-01", periods=1000))
    folds = walk_forward_splits(dates, n_folds=5)
    train_sizes = [fold.train_mask.sum() for fold in folds]
    assert train_sizes == sorted(train_sizes)  # strictly non-decreasing training window


def test_too_little_history_returns_no_folds():
    dates = pd.Series(pd.bdate_range("2020-01-01", periods=10))
    assert walk_forward_splits(dates) == []


def test_evaluate_predictions_mae_rmse_directional_accuracy():
    actual = np.array([0.05, -0.03, 0.02, -0.01])
    predicted = np.array([0.04, -0.03, -0.01, -0.02])
    metrics = evaluate_predictions(actual_returns=actual, predicted_returns=predicted)
    assert metrics.sample_size == 4
    assert metrics.mae == pytest_approx(np.mean(np.abs(predicted - actual)))
    # directions: (+,+) match, (-,-) match, (+,-) mismatch, (-,-) match -> 3/4
    assert metrics.directional_accuracy == 0.75


def pytest_approx(value):
    import pytest

    return pytest.approx(value, rel=1e-9)


def test_evaluate_predictions_ignores_nan_pairs():
    actual = np.array([0.05, np.nan, 0.02])
    predicted = np.array([0.04, 0.01, np.nan])
    metrics = evaluate_predictions(actual_returns=actual, predicted_returns=predicted)
    assert metrics.sample_size == 1


def test_brier_score_zero_for_perfect_probability_calibration():
    actual = np.array([0.05, -0.05, 0.05, -0.05])
    predicted = np.array([0.01, -0.01, 0.01, -0.01])
    prob = np.array([1.0, 0.0, 1.0, 0.0])
    metrics = evaluate_predictions(actual_returns=actual, predicted_returns=predicted, probability_positive=prob)
    assert metrics.brier_score == 0.0


def test_interval_coverage_reflects_fraction_within_bounds():
    actual = np.array([0.05, 0.20, -0.30])
    predicted = np.zeros(3)
    p10 = np.array([-0.10, -0.10, -0.10])
    p90 = np.array([0.10, 0.10, 0.10])
    metrics = evaluate_predictions(actual_returns=actual, predicted_returns=predicted, p10=p10, p90=p90)
    assert metrics.interval_coverage_80 == pytest_approx(1 / 3)

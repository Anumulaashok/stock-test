"""Walk-forward validation + evaluation metrics (spec sections 20/22).

No random train/test split anywhere in this module. `walk_forward_splits`
partitions by *date*, expanding-window style (train on everything before
a cutoff, test on the slice right after it) -- each test fold's
predictions are made using a model trained only on strictly earlier data,
which is what makes the resulting metrics honest (spec section 15/20:
"Each historical prediction must be generated without seeing the
future").
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class WalkForwardFold:
    fold_index: int
    train_end: pd.Timestamp
    test_end: pd.Timestamp
    train_mask: pd.Series
    test_mask: pd.Series


def walk_forward_splits(
    dates: pd.Series, *, n_folds: int = 5, min_train_fraction: float = 0.5
) -> list[WalkForwardFold]:
    """`dates` is a Series (any index) of the date associated with each
    row in the dataset being split -- for the pooled cross-ticker
    dataset this is the row's trading date, shared across tickers, so a
    fold's test window is the same calendar slice for every ticker
    (no ticker sees "future" data relative to another via a
    ticker-specific split boundary)."""
    unique_dates = pd.Series(sorted(dates.unique()))
    n = len(unique_dates)
    if n < 20:
        return []

    first_test_idx = max(int(n * min_train_fraction), 1)
    if first_test_idx >= n:
        return []

    boundaries = np.linspace(first_test_idx, n - 1, num=min(n_folds, n - first_test_idx), dtype=int)
    boundaries = sorted(set(boundaries.tolist()))

    folds: list[WalkForwardFold] = []
    prev_boundary = first_test_idx
    for fold_index, boundary in enumerate(boundaries):
        if boundary <= prev_boundary and fold_index > 0:
            continue
        train_end = unique_dates.iloc[prev_boundary - 1] if prev_boundary > 0 else unique_dates.iloc[0]
        test_end = unique_dates.iloc[boundary]
        train_mask = dates <= train_end
        test_mask = (dates > train_end) & (dates <= test_end)
        if train_mask.sum() == 0 or test_mask.sum() == 0:
            prev_boundary = boundary
            continue
        folds.append(
            WalkForwardFold(
                fold_index=fold_index, train_end=train_end, test_end=test_end,
                train_mask=train_mask, test_mask=test_mask,
            )
        )
        prev_boundary = boundary
    return folds


@dataclass(frozen=True)
class EvaluationMetrics:
    sample_size: int
    mae: float | None
    rmse: float | None
    directional_accuracy: float | None
    brier_score: float | None
    interval_coverage_80: float | None  # fraction of actuals within [p10, p90]


def evaluate_predictions(
    *,
    actual_returns: np.ndarray,
    predicted_returns: np.ndarray,
    probability_positive: np.ndarray | None = None,
    p10: np.ndarray | None = None,
    p90: np.ndarray | None = None,
) -> EvaluationMetrics:
    mask = ~np.isnan(actual_returns) & ~np.isnan(predicted_returns)
    n = int(mask.sum())
    if n == 0:
        return EvaluationMetrics(0, None, None, None, None, None)

    actual = actual_returns[mask]
    predicted = predicted_returns[mask]
    errors = predicted - actual
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))
    directional_accuracy = float(np.mean(np.sign(predicted) == np.sign(actual)))

    brier_score = None
    if probability_positive is not None:
        prob_mask = mask & ~np.isnan(probability_positive)
        if prob_mask.sum() > 0:
            outcome_positive = (actual_returns[prob_mask] > 0).astype(float)
            brier_score = float(np.mean((probability_positive[prob_mask] - outcome_positive) ** 2))

    interval_coverage = None
    if p10 is not None and p90 is not None:
        interval_mask = mask & ~np.isnan(p10) & ~np.isnan(p90)
        if interval_mask.sum() > 0:
            within = (actual_returns[interval_mask] >= p10[interval_mask]) & (
                actual_returns[interval_mask] <= p90[interval_mask]
            )
            interval_coverage = float(np.mean(within))

    return EvaluationMetrics(
        sample_size=n, mae=mae, rmse=rmse, directional_accuracy=directional_accuracy,
        brier_score=brier_score, interval_coverage_80=interval_coverage,
    )

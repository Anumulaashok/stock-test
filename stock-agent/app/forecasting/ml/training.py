"""Offline training job (spec sections 20/32/33): builds a pooled,
cross-ticker feature dataset, runs walk-forward validation per model per
horizon, refits each model on the full pooled history for serving, and
persists everything via `app.forecasting.ml.artifacts.ArtifactStore`.

Pooled across tickers deliberately (spec section 35's own DANLAW
validation run has essentially no persisted history -- see the
implementation assessment) -- every feature this pipeline uses is
already a ticker-relative ratio or return, so training on one ticker's
patterns and applying them to another's current state is the intended
generalization, not a shortcut. `daily_price_history` is NOT used here:
it is far shallower than yfinance's own 5-year OHLCV history for the
same tickers (see `app.forecasting.ml.data`).

Never invoked from a request handler (spec section 32) -- run via
`python -m app.forecasting.ml.backtest --train` or a scheduled job.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.forecasting.ml.artifacts import ArtifactStore, new_manifest
from app.forecasting.ml.data import MlPriceHistoryService
from app.forecasting.ml.ensemble import weights_from_mae
from app.forecasting.ml.features import (
    FEATURE_COLUMNS,
    RELATIVE_STRENGTH_COLUMNS,
    build_price_features,
    build_relative_strength_features,
)
from app.forecasting.ml.horizons import ALL_HORIZONS, MlHorizon
from app.forecasting.ml.models.baseline import HistoricalMeanModel, NaiveReturnModel
from app.forecasting.ml.models.timeseries import AutoRegReturnModel
from app.forecasting.ml.models.tree_models import GradientBoostingQuantileModel, RandomForestReturnModel
from app.forecasting.ml.regime import classify_regime_series
from app.forecasting.ml.targets import build_targets, target_column
from app.forecasting.ml.validation import evaluate_predictions, walk_forward_splits

logger = logging.getLogger(__name__)

MODEL_FACTORIES: dict[str, type] = {
    "naive_zero_return": NaiveReturnModel,
    "historical_mean_return": HistoricalMeanModel,
    "random_forest": RandomForestReturnModel,
    "gradient_boosting_quantile": GradientBoostingQuantileModel,
    "autoreg_return": AutoRegReturnModel,
}

ALL_FEATURE_COLUMNS = FEATURE_COLUMNS + RELATIVE_STRENGTH_COLUMNS
MIN_ROWS_PER_HORIZON = 200


@dataclass(frozen=True)
class HorizonTrainingResult:
    horizon: MlHorizon
    weights: dict[str, float]
    performance: dict[str, dict[str, float | int | None]]


@dataclass(frozen=True)
class TrainingResult:
    pooled_dataset: pd.DataFrame
    tickers_used: list[str]
    tickers_skipped: list[str]
    horizon_results: dict[MlHorizon, HorizonTrainingResult]
    training_data_end_date: str


async def build_pooled_dataset(
    tickers: list[str], *, price_service: MlPriceHistoryService, period: str = "5y"
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """One row per (ticker, date) with technical + relative-strength
    features, regime, and per-horizon forward-return targets. Rows with
    any NaN feature (warm-up period, e.g. before 200 trading days of
    history exist) or NaN target for every horizon are dropped."""
    benchmark_result = await price_service.get_benchmark_history(period=period)
    benchmark_close = benchmark_result.frame["close"] if benchmark_result.is_usable else None

    frames: list[pd.DataFrame] = []
    used: list[str] = []
    skipped: list[str] = []

    for ticker in tickers:
        result = await price_service.get_history(ticker, period=period)
        if not result.is_usable or len(result.frame) < MIN_ROWS_PER_HORIZON:
            skipped.append(ticker)
            continue

        price_features = build_price_features(result.frame)
        targets = build_targets(result.frame["close"])
        merged = price_features.join(targets)

        if benchmark_close is not None:
            relative = build_relative_strength_features(result.frame["close"], benchmark_close)
            merged = merged.join(relative)

        merged["regime"] = classify_regime_series(merged)
        merged["ticker"] = ticker
        merged["date"] = merged.index
        frames.append(merged)
        used.append(ticker)

    if not frames:
        return pd.DataFrame(), used, skipped

    pooled = pd.concat(frames, axis=0, ignore_index=True)
    return pooled, used, skipped


def _feature_columns_present(pooled: pd.DataFrame) -> list[str]:
    return [c for c in ALL_FEATURE_COLUMNS if c in pooled.columns]


def train_all_horizons(pooled: pd.DataFrame) -> dict[MlHorizon, HorizonTrainingResult]:
    feature_columns = _feature_columns_present(pooled)
    results: dict[MlHorizon, HorizonTrainingResult] = {}

    for horizon in ALL_HORIZONS:
        target_col = target_column(horizon)
        if target_col not in pooled.columns:
            continue
        usable = pooled.dropna(subset=feature_columns + [target_col])
        if len(usable) < MIN_ROWS_PER_HORIZON:
            logger.info("ml_training_skip_horizon horizon=%s reason=insufficient_rows rows=%d", horizon, len(usable))
            continue

        X_all = usable[feature_columns]
        y_all = usable[target_col]
        dates = usable["date"]

        folds = walk_forward_splits(dates, n_folds=5)
        mae_by_model: dict[str, list[float]] = {name: [] for name in MODEL_FACTORIES}
        performance: dict[str, dict[str, float | int | None]] = {}

        for fold in folds:
            X_train, y_train = X_all[fold.train_mask], y_all[fold.train_mask]
            X_test, y_test = X_all[fold.test_mask], y_all[fold.test_mask]
            if len(X_train) < 50 or len(X_test) == 0:
                continue
            for name, factory in MODEL_FACTORIES.items():
                model = factory()
                model.fit(X_train, y_train)
                predicted = model.predict(X_test)
                metrics = evaluate_predictions(actual_returns=y_test.to_numpy(), predicted_returns=predicted)
                if metrics.mae is not None:
                    mae_by_model[name].append(metrics.mae)

        for name, mae_values in mae_by_model.items():
            if mae_values:
                performance[name] = {
                    "sample_size": len(mae_values),
                    "mean_mae_across_folds": float(np.mean(mae_values)),
                }

        weights = weights_from_mae({name: (np.mean(v) if v else None) for name, v in mae_by_model.items()})
        results[horizon] = HorizonTrainingResult(horizon=horizon, weights=weights, performance=performance)

    return results


async def run_training(
    tickers: list[str], *, artifact_store: ArtifactStore | None = None, period: str = "5y"
) -> TrainingResult:
    store = artifact_store or ArtifactStore()
    price_service = MlPriceHistoryService()

    pooled, used, skipped = await build_pooled_dataset(tickers, price_service=price_service, period=period)
    if pooled.empty:
        raise ValueError("No usable price history for any ticker in the training universe")

    horizon_results = train_all_horizons(pooled)
    feature_columns = _feature_columns_present(pooled)

    weights_payload: dict[str, dict[str, float]] = {}
    for horizon, result in horizon_results.items():
        target_col = target_column(horizon)
        usable = pooled.dropna(subset=feature_columns + [target_col])
        X_all, y_all = usable[feature_columns], usable[target_col]
        for name, factory in MODEL_FACTORIES.items():
            model = factory()
            model.fit(X_all, y_all)
            store.save_model(horizon, name, model)
        weights_payload[horizon.value] = result.weights

    store.save_pooled_dataset(pooled)
    store.save_weights(weights_payload)
    training_end_date = str(pooled["date"].max().date())
    store.save_manifest(new_manifest(tickers=used, row_count=len(pooled), training_data_end_date=training_end_date))

    return TrainingResult(
        pooled_dataset=pooled, tickers_used=used, tickers_skipped=skipped,
        horizon_results=horizon_results, training_data_end_date=training_end_date,
    )

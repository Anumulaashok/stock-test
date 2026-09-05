"""Developer backtesting/training CLI (spec section 33).

    python -m app.forecasting.ml.backtest --train
    python -m app.forecasting.ml.backtest --ticker DANLAW --horizon 14D

`--train` runs the full offline training job (spec section 32) and
writes artifacts to `var/ml_forecast/`. `--ticker/--horizon` runs
walk-forward validation for one ticker's own price history and prints a
comparison table across: the naive baseline, the historical-mean
baseline, this project's *existing* deterministic technical forecast
(spec section 27 -- reusing `fit_linear_trend` from
`app.forecasting.calculations`, the same OLS method
`ForecastingService.forecast_technical` uses, so the comparison is
apples-to-apples), and the new Random Forest / Gradient Boosting models.
"""

import argparse
import asyncio
import logging
from decimal import Decimal

import numpy as np
import pandas as pd

from app.forecasting.calculations import fit_linear_trend
from app.forecasting.ml.data import MlPriceHistoryService
from app.forecasting.ml.features import FEATURE_COLUMNS, RELATIVE_STRENGTH_COLUMNS, build_price_features, build_relative_strength_features
from app.forecasting.ml.horizons import HORIZON_TRADING_DAYS, MlHorizon
from app.forecasting.ml.models.baseline import HistoricalMeanModel, NaiveReturnModel
from app.forecasting.ml.models.tree_models import GradientBoostingQuantileModel, RandomForestReturnModel
from app.forecasting.ml.targets import build_targets, target_column
from app.forecasting.ml.training import run_training
from app.forecasting.ml.validation import evaluate_predictions, walk_forward_splits
from app.sectors.universe import SECTOR_UNIVERSE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ALL_FEATURE_COLUMNS = FEATURE_COLUMNS + RELATIVE_STRENGTH_COLUMNS


def _technical_baseline_predictions(close: pd.Series, horizon_days: int, window: int = 60) -> np.ndarray:
    """Reproduces `ForecastingService.forecast_technical`'s linear-trend
    method at each row: fit OLS on the trailing `window` closes, project
    `horizon_days` forward, express as a return. `NaN` where fewer than
    `window` prior closes exist."""
    predictions = np.full(len(close), np.nan)
    values = close.to_numpy()
    for i in range(window, len(values)):
        trailing = [Decimal(str(v)) for v in values[i - window : i]]
        slope, intercept, _, status, _ = fit_linear_trend(trailing)
        if status.value != "calculated" or slope is None or intercept is None:
            continue
        projected = float(intercept) + float(slope) * (window - 1 + horizon_days)
        current = values[i - 1]
        if current:
            predictions[i] = projected / current - 1
    return predictions


async def _run_ticker_backtest(ticker: str, horizon: MlHorizon) -> None:
    price_service = MlPriceHistoryService()
    price_result = await price_service.get_history(ticker, period="5y")
    if not price_result.is_usable:
        print(f"No usable price history for {ticker}: {price_result.warning}")
        return

    benchmark_result = await price_service.get_benchmark_history(period="5y")
    features = build_price_features(price_result.frame)
    if benchmark_result.is_usable:
        features = features.join(build_relative_strength_features(price_result.frame["close"], benchmark_result.frame["close"]))
    targets = build_targets(price_result.frame["close"])
    merged = features.join(targets)
    merged["date"] = merged.index

    target_col = target_column(horizon)
    feature_columns = [c for c in ALL_FEATURE_COLUMNS if c in merged.columns]
    merged["technical_baseline"] = _technical_baseline_predictions(
        price_result.frame["close"], HORIZON_TRADING_DAYS[horizon]
    )
    usable = merged.dropna(subset=feature_columns + [target_col])

    print(f"\nTicker: {ticker}  Horizon: {horizon.value} ({HORIZON_TRADING_DAYS[horizon]} trading days)")
    print(f"Usable rows after dropping warm-up/undecided targets: {len(usable)}")
    if len(usable) < 100:
        print("Insufficient history for a meaningful per-ticker walk-forward backtest (need >=100 rows).")
        print("This is expected for a thinly-listed/recently-tracked ticker -- see the training universe")
        print("in `python -m app.forecasting.ml.backtest --train` for the cross-ticker pooled model actually served.")
        return

    folds = walk_forward_splits(usable["date"], n_folds=5)
    if not folds:
        print("Not enough date range to build walk-forward folds.")
        return

    model_factories = {
        "naive_zero_return": NaiveReturnModel,
        "historical_mean_return": HistoricalMeanModel,
        "random_forest": RandomForestReturnModel,
        "gradient_boosting_quantile": GradientBoostingQuantileModel,
    }

    rows = []
    for name, factory in model_factories.items():
        maes, rmses, das, briers, coverages = [], [], [], [], []
        for fold in folds:
            X_train, y_train = usable.loc[fold.train_mask, feature_columns], usable.loc[fold.train_mask, target_col]
            X_test, y_test = usable.loc[fold.test_mask, feature_columns], usable.loc[fold.test_mask, target_col]
            if len(X_train) < 50 or len(X_test) == 0:
                continue
            model = factory()
            model.fit(X_train, y_train)
            predicted = model.predict(X_test)
            prob = model.predict_probability_positive(X_test)
            distribution = model.predict_distribution(X_test)
            metrics = evaluate_predictions(
                actual_returns=y_test.to_numpy(), predicted_returns=predicted, probability_positive=prob,
                p10=distribution["p10"] if distribution else None, p90=distribution["p90"] if distribution else None,
            )
            if metrics.mae is not None:
                maes.append(metrics.mae); rmses.append(metrics.rmse); das.append(metrics.directional_accuracy)
            if metrics.brier_score is not None:
                briers.append(metrics.brier_score)
            if metrics.interval_coverage_80 is not None:
                coverages.append(metrics.interval_coverage_80)
        rows.append((name, len(maes), np.mean(maes) if maes else None, np.mean(rmses) if rmses else None,
                     np.mean(das) if das else None, np.mean(briers) if briers else None, np.mean(coverages) if coverages else None))

    technical_actual = usable[target_col].to_numpy()
    technical_pred = usable["technical_baseline"].to_numpy()
    technical_metrics = evaluate_predictions(actual_returns=technical_actual, predicted_returns=technical_pred)
    rows.append(("technical_baseline (existing system)", 1, technical_metrics.mae, technical_metrics.rmse, technical_metrics.directional_accuracy, None, None))

    header = f"{'Model':<38}{'Folds':<7}{'MAE':<10}{'RMSE':<10}{'DirAcc':<9}{'Brier':<9}{'IntCov80':<10}"
    print(header)
    print("-" * len(header))
    for name, n_folds, mae, rmse, da, brier, coverage in rows:
        print(
            f"{name:<38}{n_folds:<7}"
            f"{'' if mae is None else f'{mae:.4f}':<10}"
            f"{'' if rmse is None else f'{rmse:.4f}':<10}"
            f"{'' if da is None else f'{da:.2%}':<9}"
            f"{'' if brier is None else f'{brier:.4f}':<9}"
            f"{'' if coverage is None else f'{coverage:.2%}':<10}"
        )


def _default_training_universe() -> list[str]:
    return sorted({t for tickers in SECTOR_UNIVERSE.values() for t in tickers})


async def _run_evaluation() -> None:
    from app.core.config import get_settings
    from app.db.base import get_session_factory, init_engine
    from app.forecasting.ml.evaluation import evaluate_due_predictions
    from app.forecasting.ml.persistence import MlForecastPersistence

    settings = get_settings()
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    async with session_factory() as db:
        count = await evaluate_due_predictions(MlForecastPersistence(db))
    print(f"Evaluated {count} due prediction(s) and refreshed global model-performance rows.")


async def _run_training(tickers: list[str]) -> None:
    print(f"Training on {len(tickers)} tickers: {', '.join(tickers)}")
    result = await run_training(tickers)
    print(f"\nUsed {len(result.tickers_used)} tickers, skipped {len(result.tickers_skipped)}: {result.tickers_skipped}")
    print(f"Pooled dataset: {len(result.pooled_dataset)} rows, training data through {result.training_data_end_date}")
    for horizon, horizon_result in result.horizon_results.items():
        print(f"\n{horizon.value} model weights (from walk-forward MAE): {horizon_result.weights}")
        print(f"{horizon.value} per-model walk-forward performance: {horizon_result.performance}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-horizon ML forecast training/backtesting")
    parser.add_argument("--train", action="store_true", help="Run the offline training job and write artifacts")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate due predictions against actual outcomes")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated tickers for --train (default: sector universe)")
    parser.add_argument("--ticker", type=str, default=None, help="Single ticker to backtest")
    parser.add_argument("--horizon", type=str, default="14D", choices=[h.value for h in MlHorizon] + ["14d", "1m", "3m", "1y"])
    args = parser.parse_args()

    if args.train:
        tickers = args.tickers.split(",") if args.tickers else _default_training_universe()
        asyncio.run(_run_training(tickers))
        return

    if args.evaluate:
        asyncio.run(_run_evaluation())
        return

    if args.ticker:
        horizon = MlHorizon(args.horizon.upper())
        asyncio.run(_run_ticker_backtest(args.ticker, horizon))
        return

    parser.print_help()


if __name__ == "__main__":
    main()

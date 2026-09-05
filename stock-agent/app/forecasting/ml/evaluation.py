"""Fills in actual outcomes for predictions whose horizon has elapsed
(spec sections 9/21), and rolls the results up into
`ForecastModelPerformanceRow` (spec section 22) -- the "did this
forecast turn out to be right" half of the pipeline, complementing
`app.forecasting.ml.pipeline` (which only ever predicts).

Not wired into `app.scheduler` yet (see the implementation summary's
"known limitations") -- run via
`python -m app.forecasting.ml.backtest --evaluate` for now, the same
way `app.forecasting.accuracy_service.ForecastAccuracyService` (the
existing deterministic-forecast equivalent) is invoked on-demand from
`GET /api/v1/market/{ticker}/forecast-accuracy` rather than a
background job.
"""

import logging
from datetime import date, datetime, timezone

import numpy as np

from app.forecasting.ml.data import MlPriceHistoryService
from app.forecasting.ml.persistence import MlForecastPersistence
from app.forecasting.ml.versions import MODEL_VERSION

logger = logging.getLogger(__name__)


async def evaluate_due_predictions(persistence: MlForecastPersistence, *, as_of: date | None = None) -> int:
    """Returns the number of predictions newly evaluated. Never
    evaluates against a fabricated price -- a target date that isn't
    actually present in the fetched price history (e.g. a market
    holiday, or the ticker delisted) is left unevaluated, not guessed."""
    as_of = as_of or datetime.now(timezone.utc).date()
    due = await persistence.get_due_for_evaluation(as_of=as_of)
    if not due:
        return 0

    price_service = MlPriceHistoryService()
    price_cache: dict[str, object] = {}
    evaluated = 0

    for row in due:
        if row.ticker not in price_cache:
            price_cache[row.ticker] = await price_service.get_history(row.ticker, period="5y")
        price_result = price_cache[row.ticker]
        if not price_result.is_usable:
            continue

        target_ts = row.target_date
        close = price_result.frame["close"]
        available = close.index[close.index.date <= target_ts]
        if len(available) == 0:
            continue
        actual_price = float(close.loc[available.max()])
        actual_return = actual_price / float(row.current_price) - 1

        within_interval = None
        if row.p10 is not None and row.p90 is not None:
            within_interval = float(row.p10) <= actual_return <= float(row.p90)

        await persistence.record_outcome(
            row, actual_price=actual_price, actual_return=actual_return, within_interval=within_interval
        )
        evaluated += 1

    await _recompute_global_performance(persistence, horizons={row.horizon for row in due})
    return evaluated


async def _recompute_global_performance(persistence: MlForecastPersistence, *, horizons: set[str]) -> None:
    from sqlalchemy import select

    from app.db.models import ForecastPredictionRow

    for horizon in horizons:
        stmt = (
            select(ForecastPredictionRow)
            .where(ForecastPredictionRow.horizon == horizon)
            .where(ForecastPredictionRow.evaluated_at.is_not(None))
        )
        result = await persistence._db.execute(stmt)  # noqa: SLF001 - same module family, avoids a redundant public method
        rows = list(result.scalars().all())
        if not rows:
            continue

        actual_returns = np.array([float(r.actual_return) for r in rows])
        predicted_returns = np.array([float(r.predicted_return) for r in rows])
        probability_positive = np.array(
            [float(r.probability_positive) if r.probability_positive is not None else np.nan for r in rows]
        )
        p10 = np.array([float(r.p10) if r.p10 is not None else np.nan for r in rows])
        p90 = np.array([float(r.p90) if r.p90 is not None else np.nan for r in rows])

        from app.forecasting.ml.validation import evaluate_predictions

        metrics = evaluate_predictions(
            actual_returns=actual_returns, predicted_returns=predicted_returns,
            probability_positive=probability_positive, p10=p10, p90=p90,
        )
        await persistence.upsert_model_performance(
            model_name="ensemble", model_version=MODEL_VERSION, horizon=horizon, scope="ALL", scope_value="ALL",
            sample_size=metrics.sample_size, mae=metrics.mae, rmse=metrics.rmse,
            directional_accuracy=metrics.directional_accuracy, brier_score=metrics.brier_score,
            interval_coverage_80=metrics.interval_coverage_80,
        )

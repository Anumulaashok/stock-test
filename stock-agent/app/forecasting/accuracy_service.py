"""Evaluates `ForecastSnapshotRow` predictions against realized prices in
`daily_price_history`, writing `PredictionOutcomeRow` entries -- the
"Phase 11" evaluation pass `PredictionOutcomeRow`'s own docstring
(app.db.models) says isn't built yet. Only evaluates a forecast whose
`target_date` has actually passed and for which `daily_price_history`
now has an actual price, and only once per `forecast_snapshot_id`
(enforced here by skipping anything already in `PredictionOutcomeRow`,
and by that table's own unique constraint as a backstop). Never
recalculates a forecast, never touches valuation/scoring -- purely a
comparison of two already-stored numbers.
"""

import logging
from datetime import date as date_type
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyPriceHistoryRow, ForecastSnapshotRow, PredictionOutcomeRow

logger = logging.getLogger(__name__)


class ForecastAccuracyService:
    async def evaluate_ticker(
        self, db: AsyncSession, ticker: str, as_of: date_type | None = None
    ) -> int:
        """Evaluates every not-yet-evaluated forecast for `ticker` whose
        `target_date` is on or before `as_of` (default: today) and for
        which an actual price now exists in `daily_price_history`.
        Returns the number of new `PredictionOutcomeRow`s written --
        `0` is a normal outcome (nothing newly due), not an error."""
        ticker = ticker.strip().upper()
        as_of = as_of or datetime.now(timezone.utc).date()

        already_evaluated = select(PredictionOutcomeRow.forecast_snapshot_id)
        stmt = select(ForecastSnapshotRow).where(
            ForecastSnapshotRow.ticker == ticker,
            ForecastSnapshotRow.target_date.is_not(None),
            ForecastSnapshotRow.target_date <= as_of,
            ForecastSnapshotRow.predicted_price.is_not(None),
            ForecastSnapshotRow.id.not_in(already_evaluated),
        )
        pending = (await db.execute(stmt)).scalars().all()
        if not pending:
            return 0

        written = 0
        for forecast in pending:
            actual_stmt = select(DailyPriceHistoryRow.price).where(
                DailyPriceHistoryRow.ticker == ticker, DailyPriceHistoryRow.date == forecast.target_date
            )
            actual_price = (await db.execute(actual_stmt)).scalar_one_or_none()
            if actual_price is None:
                continue  # no actual price recorded for that date yet -- evaluate on a later pass

            absolute_error = abs(actual_price - forecast.predicted_price)
            percentage_error = (
                (absolute_error / actual_price * 100) if actual_price != 0 else None
            )

            # Direction accuracy needs a baseline (the price as of the
            # prediction itself) -- only computed when that baseline is
            # actually on record; never guessed.
            direction_correct = None
            baseline_stmt = select(DailyPriceHistoryRow.price).where(
                DailyPriceHistoryRow.ticker == ticker, DailyPriceHistoryRow.date == forecast.prediction_date
            )
            baseline_price = (await db.execute(baseline_stmt)).scalar_one_or_none()
            if baseline_price is not None and baseline_price != actual_price:
                predicted_up = forecast.predicted_price > baseline_price
                actual_up = actual_price > baseline_price
                direction_correct = predicted_up == actual_up

            db.add(
                PredictionOutcomeRow(
                    forecast_snapshot_id=forecast.id,
                    ticker=ticker,
                    target_date=forecast.target_date,
                    predicted_price=forecast.predicted_price,
                    actual_price=actual_price,
                    absolute_error=absolute_error,
                    percentage_error=percentage_error,
                    direction_correct=direction_correct,
                    evaluated_at=datetime.now(timezone.utc),
                )
            )
            written += 1

        await db.commit()
        if written:
            logger.info("forecast_accuracy_evaluated ticker=%s rows_written=%d", ticker, written)
        return written

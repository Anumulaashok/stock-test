"""Persistence for ML forecasts, model performance, and news events
(spec sections 8/21/22) -- thin CRUD over the tables added to
`app.db.models`. Kept separate from `app.forecasting.accuracy_service`
(which evaluates the existing deterministic `ForecastSnapshotRow`s)
since the two systems' tables are intentionally not shared (see the
`ForecastPredictionRow` docstring).
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ForecastModelPerformanceRow, ForecastPredictionRow, NewsEventRow
from app.forecasting.ml.news.models import NewsEvent

logger = logging.getLogger(__name__)


def _dec(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


class MlForecastPersistence:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save_prediction(self, row: ForecastPredictionRow) -> None:
        self._db.add(row)
        await self._db.commit()

    async def get_predictions(self, ticker: str, horizon: str | None = None, limit: int = 50) -> list[ForecastPredictionRow]:
        stmt = select(ForecastPredictionRow).where(ForecastPredictionRow.ticker == ticker.upper())
        if horizon:
            stmt = stmt.where(ForecastPredictionRow.horizon == horizon)
        stmt = stmt.order_by(ForecastPredictionRow.prediction_timestamp.desc()).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_due_for_evaluation(self, *, as_of: date, limit: int = 200) -> list[ForecastPredictionRow]:
        stmt = (
            select(ForecastPredictionRow)
            .where(ForecastPredictionRow.target_date <= as_of)
            .where(ForecastPredictionRow.evaluated_at.is_(None))
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def record_outcome(
        self, row: ForecastPredictionRow, *, actual_price: float, actual_return: float, within_interval: bool | None
    ) -> None:
        row.actual_price = _dec(actual_price)
        row.actual_return = _dec(actual_return)
        row.absolute_error = _dec(abs(actual_return - float(row.predicted_return)))
        row.direction_correct = (actual_return > 0) == (float(row.predicted_return) > 0)
        row.within_prediction_interval = within_interval
        row.evaluated_at = datetime.now(timezone.utc)
        await self._db.commit()

    async def upsert_model_performance(
        self,
        *,
        model_name: str,
        model_version: str,
        horizon: str,
        scope: str,
        scope_value: str,
        sample_size: int,
        mae: float | None,
        rmse: float | None,
        directional_accuracy: float | None,
        brier_score: float | None,
        interval_coverage_80: float | None,
    ) -> None:
        dialect = self._db.bind.dialect.name if self._db.bind is not None else "postgresql"
        insert_fn = sqlite_insert if dialect == "sqlite" else postgresql_insert
        values = dict(
            model_name=model_name, model_version=model_version, horizon=horizon,
            scope=scope, scope_value=scope_value, sample_size=sample_size,
            mae=_dec(mae), rmse=_dec(rmse), directional_accuracy=_dec(directional_accuracy),
            brier_score=_dec(brier_score), interval_coverage_80=_dec(interval_coverage_80),
        )
        stmt = insert_fn(ForecastModelPerformanceRow).values(**values)
        update_cols = {k: v for k, v in values.items() if k not in ("model_name", "model_version", "horizon", "scope", "scope_value")}
        stmt = stmt.on_conflict_do_update(
            index_elements=["model_name", "model_version", "horizon", "scope", "scope_value"],
            set_=update_cols,
        )
        await self._db.execute(stmt)
        await self._db.commit()

    async def get_performance(self, *, horizon: str, scope: str = "ALL", scope_value: str = "ALL") -> ForecastModelPerformanceRow | None:
        stmt = select(ForecastModelPerformanceRow).where(
            ForecastModelPerformanceRow.horizon == horizon,
            ForecastModelPerformanceRow.scope == scope,
            ForecastModelPerformanceRow.scope_value == scope_value,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def save_news_events(self, events: list[NewsEvent]) -> None:
        if not events:
            return
        dialect = self._db.bind.dialect.name if self._db.bind is not None else "postgresql"
        insert_fn = sqlite_insert if dialect == "sqlite" else postgresql_insert
        for event in events:
            values = dict(
                ticker=event.ticker, company=event.company, published_at=event.published_at,
                source=event.source, headline=event.headline, summary=event.summary, url=event.url,
                event_type=event.event_type.value, sentiment=event.sentiment.value,
                sentiment_score=_dec(event.sentiment_score), importance_score=_dec(event.importance_score),
                novelty_score=_dec(event.novelty_score), market_timing=event.market_timing.value,
            )
            stmt = insert_fn(NewsEventRow).values(**values)
            stmt = stmt.on_conflict_do_nothing(index_elements=["ticker", "published_at", "headline"])
            await self._db.execute(stmt)
        await self._db.commit()

    async def get_news_events(self, ticker: str, *, since: datetime | None = None, limit: int = 200) -> list[NewsEventRow]:
        stmt = select(NewsEventRow).where(NewsEventRow.ticker == ticker.upper())
        if since is not None:
            stmt = stmt.where(NewsEventRow.published_at >= since)
        stmt = stmt.order_by(NewsEventRow.published_at.desc()).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_news_events(self, *, before: datetime | None = None, limit: int = 5000) -> list[NewsEventRow]:
        stmt = select(NewsEventRow)
        if before is not None:
            stmt = stmt.where(NewsEventRow.published_at < before)
        stmt = stmt.order_by(NewsEventRow.published_at.desc()).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())


def news_event_row_to_domain(row: NewsEventRow) -> NewsEvent:
    from app.forecasting.ml.news.models import EventType, MarketTiming, Sentiment

    return NewsEvent(
        ticker=row.ticker, company=row.company, published_at=row.published_at, source=row.source,
        headline=row.headline, summary=row.summary, url=row.url,
        event_type=EventType(row.event_type), sentiment=Sentiment(row.sentiment),
        sentiment_score=float(row.sentiment_score), importance_score=float(row.importance_score),
        novelty_score=float(row.novelty_score), market_timing=MarketTiming(row.market_timing),
    )

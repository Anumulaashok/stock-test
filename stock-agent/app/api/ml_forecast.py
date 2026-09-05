"""ML multi-horizon forecast API (spec section 31).

Parallel to, and independent of, the existing `/api/v1/market/{ticker}/forecast-accuracy`
and the `ReportForecastSection` embedded in `/api/v1/analyze/ticker` --
this router serves the new `app.forecasting.ml` subsystem only, so the
existing deterministic forecast keeps working unmodified (spec section
27, "Technical Baseline"). Endpoints:

- `GET /api/v1/ml-forecast/{ticker}` -- full multi-horizon forecast.
- `GET /api/v1/ml-forecast/{ticker}/history` -- persisted past predictions.
- `GET /api/v1/ml-forecast/{ticker}/accuracy` -- walk-forward/outcome-based model performance.
- `GET /api/v1/ml-forecast/{ticker}/news-impact` -- recent events + historical event-type statistics.
- `GET /api/v1/ml-forecast/{ticker}/analogs` -- historical analog statistics per horizon.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.forecasting.ml.artifacts import ArtifactStore
from app.forecasting.ml.cache import CachedMlForecastPipeline
from app.forecasting.ml.horizons import MlHorizon
from app.forecasting.ml.news.ingestion import NewsEventIngestionService
from app.forecasting.ml.persistence import MlForecastPersistence
from app.forecasting.ml.pipeline import MlForecastPipeline
from app.api.dependencies import build_news_client
from app.cache.store import SqlCacheStore
from app.models.ml_forecast import MlForecastResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ml-forecast", tags=["ml-forecast"])


def _build_pipeline(settings: Settings, db: AsyncSession) -> CachedMlForecastPipeline:
    news_client = build_news_client(settings)
    news_ingestion = NewsEventIngestionService(news_client) if news_client is not None else None
    persistence = MlForecastPersistence(db)
    inner = MlForecastPipeline(
        artifact_store=ArtifactStore(), news_ingestion=news_ingestion, persistence=persistence,
    )
    return CachedMlForecastPipeline(inner, SqlCacheStore(db))


@router.get("/{ticker}", response_model=MlForecastResult)
async def get_ml_forecast(
    ticker: str,
    company_name: str | None = Query(default=None),
    force_refresh: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> MlForecastResult:
    pipeline = _build_pipeline(settings, db)
    return await pipeline.predict(ticker, company_name=company_name, force_refresh=force_refresh)


@router.get("/{ticker}/history")
async def get_ml_forecast_history(
    ticker: str,
    horizon: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    persistence = MlForecastPersistence(db)
    rows = await persistence.get_predictions(ticker, horizon=horizon, limit=limit)
    return {
        "ticker": ticker.upper(),
        "predictions": [
            {
                "prediction_timestamp": row.prediction_timestamp.isoformat(),
                "horizon": row.horizon,
                "predicted_return": float(row.predicted_return),
                "predicted_price": float(row.predicted_price),
                "target_date": row.target_date.isoformat(),
                "actual_return": float(row.actual_return) if row.actual_return is not None else None,
                "actual_price": float(row.actual_price) if row.actual_price is not None else None,
                "direction_correct": row.direction_correct,
                "forecast_quality": row.forecast_quality,
                "model_version": row.model_version,
            }
            for row in rows
        ],
    }


@router.get("/{ticker}/accuracy")
async def get_ml_forecast_accuracy(ticker: str, db: AsyncSession = Depends(get_db)) -> dict:
    persistence = MlForecastPersistence(db)
    accuracy: dict[str, dict] = {}
    for horizon in MlHorizon:
        row = await persistence.get_performance(horizon=horizon.value)
        if row is None:
            accuracy[horizon.value] = {"sample_size": 0, "note": "No walk-forward evaluation recorded yet"}
            continue
        accuracy[horizon.value] = {
            "sample_size": row.sample_size,
            "mae": float(row.mae) if row.mae is not None else None,
            "rmse": float(row.rmse) if row.rmse is not None else None,
            "directional_accuracy": float(row.directional_accuracy) if row.directional_accuracy is not None else None,
            "brier_score": float(row.brier_score) if row.brier_score is not None else None,
            "interval_coverage_80": float(row.interval_coverage_80) if row.interval_coverage_80 is not None else None,
        }
    return {"ticker": ticker.upper(), "accuracy_by_horizon": accuracy}


@router.get("/{ticker}/news-impact")
async def get_ml_forecast_news_impact(
    ticker: str, company_name: str | None = Query(default=None),
    settings: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db),
) -> dict:
    pipeline = _build_pipeline(settings, db)
    result = await pipeline.predict(ticker, company_name=company_name)
    return result.news_impact.model_dump()


@router.get("/{ticker}/analogs")
async def get_ml_forecast_analogs(
    ticker: str, company_name: str | None = Query(default=None),
    settings: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db),
) -> dict:
    pipeline = _build_pipeline(settings, db)
    result = await pipeline.predict(ticker, company_name=company_name)
    return {
        "ticker": ticker.upper(),
        "analogs_by_horizon": {horizon: forecast.analog.model_dump() for horizon, forecast in result.horizons.items()},
    }

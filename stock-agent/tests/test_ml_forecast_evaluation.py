from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ForecastPredictionRow
from app.forecasting.ml.data import PriceHistoryResult
from app.forecasting.ml.evaluation import evaluate_due_predictions
from app.forecasting.ml.persistence import MlForecastPersistence


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def _make_row(**overrides) -> ForecastPredictionRow:
    base = dict(
        ticker="TEST", prediction_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        data_timestamp=date(2026, 1, 1), horizon="14D", model_version="v1", feature_version="v1",
        news_feature_version="v1", current_price=Decimal("100"), predicted_return=Decimal("0.05"),
        predicted_price=Decimal("105"), p10=Decimal("-0.05"), p90=Decimal("0.15"),
        probability_positive=Decimal("0.6"), metadata_json="{}", target_date=date(2026, 1, 15),
    )
    base.update(overrides)
    return ForecastPredictionRow(**base)


async def test_evaluate_due_predictions_records_actual_outcome(db_session, monkeypatch):
    persistence = MlForecastPersistence(db_session)
    await persistence.save_prediction(_make_row())

    close = pd.Series([100.0, 108.0], index=pd.DatetimeIndex(["2026-01-01", "2026-01-15"]))
    frame = pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": close})

    async def fake_get_history(self, ticker, period="5y"):
        return PriceHistoryResult(ticker=ticker, yfinance_symbol=ticker, frame=frame)

    from app.forecasting.ml.data import MlPriceHistoryService

    monkeypatch.setattr(MlPriceHistoryService, "get_history", fake_get_history)

    count = await evaluate_due_predictions(persistence, as_of=date(2026, 1, 16))
    assert count == 1

    rows = await persistence.get_predictions("TEST")
    assert rows[0].evaluated_at is not None
    assert rows[0].actual_price == Decimal("108")
    assert rows[0].direction_correct is True  # both predicted (+5%) and actual (+8%) positive
    assert rows[0].within_prediction_interval is True  # 0.08 is within [-0.05, 0.15]

    perf = await persistence.get_performance(horizon="14D")
    assert perf is not None
    assert perf.sample_size == 1


async def test_no_due_predictions_returns_zero(db_session):
    persistence = MlForecastPersistence(db_session)
    await persistence.save_prediction(_make_row(target_date=date(2099, 1, 1)))
    count = await evaluate_due_predictions(persistence, as_of=date(2026, 1, 1))
    assert count == 0

import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.data.daily_price_history_service import upsert_daily_price
from app.db.base import Base
from app.db.models import ForecastSnapshotRow, PredictionOutcomeRow, ResearchRunRow
from app.forecasting.accuracy_service import ForecastAccuracyService


def d(value) -> Decimal:
    return Decimal(str(value))


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


async def _make_run(db, ticker="HUDCO") -> str:
    run = ResearchRunRow(
        ticker=ticker, research_date=date(2026, 9, 1), started_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        status="COMPLETED", run_type="NORMAL", data_version="v1", calculation_version="v1",
        forecast_version="v1", prompt_version="v1", model_version="test",
    )
    db.add(run)
    await db.commit()
    return run.id


async def _make_forecast(
    db, run_id, ticker="HUDCO", *, prediction_date=date(2026, 9, 1), target_date=date(2026, 9, 3),
    predicted_price=d(200), method="linear_regression", horizon="DAILY",
) -> str:
    forecast = ForecastSnapshotRow(
        research_run_id=run_id, ticker=ticker, horizon=horizon, method=method,
        prediction_date=prediction_date, target_date=target_date, period_index=1,
        predicted_price=predicted_price, status="calculated", metadata_json=json.dumps({}),
        forecast_version="v1",
    )
    db.add(forecast)
    await db.commit()
    return forecast.id


@pytest.mark.asyncio
async def test_no_forecasts_due_returns_zero(db_session):
    run_id = await _make_run(db_session)
    await _make_forecast(db_session, run_id, target_date=date(2026, 9, 30))  # far in the future

    written = await ForecastAccuracyService().evaluate_ticker(db_session, "HUDCO", as_of=date(2026, 9, 3))
    assert written == 0


@pytest.mark.asyncio
async def test_forecast_due_but_no_actual_price_yet_is_skipped(db_session):
    run_id = await _make_run(db_session)
    await _make_forecast(db_session, run_id, target_date=date(2026, 9, 3))

    written = await ForecastAccuracyService().evaluate_ticker(db_session, "HUDCO", as_of=date(2026, 9, 3))
    assert written == 0

    outcomes = (await db_session.execute(select(PredictionOutcomeRow))).scalars().all()
    assert outcomes == []


@pytest.mark.asyncio
async def test_evaluates_and_computes_error_once_actual_price_exists(db_session):
    run_id = await _make_run(db_session)
    forecast_id = await _make_forecast(db_session, run_id, predicted_price=d(200), target_date=date(2026, 9, 3))
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="yfinance_daily", price=d(210))
    await db_session.commit()

    written = await ForecastAccuracyService().evaluate_ticker(db_session, "HUDCO", as_of=date(2026, 9, 3))
    assert written == 1

    outcome = (await db_session.execute(select(PredictionOutcomeRow))).scalar_one()
    assert outcome.forecast_snapshot_id == forecast_id
    assert outcome.predicted_price == d(200)
    assert outcome.actual_price == d(210)
    assert outcome.absolute_error == d(10)
    # percentage_error is Numeric(10,4) -- rounds on the DB round-trip
    assert abs(outcome.percentage_error - (d(10) / d(210) * 100)) < d("0.001")


@pytest.mark.asyncio
async def test_direction_correct_when_baseline_price_is_on_record(db_session):
    run_id = await _make_run(db_session)
    await _make_forecast(
        db_session, run_id, predicted_price=d(210), prediction_date=date(2026, 9, 1), target_date=date(2026, 9, 3)
    )
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 1), source="yfinance_daily", price=d(200))  # baseline
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="yfinance_daily", price=d(215))  # actual, also went up
    await db_session.commit()

    await ForecastAccuracyService().evaluate_ticker(db_session, "HUDCO", as_of=date(2026, 9, 3))

    outcome = (await db_session.execute(select(PredictionOutcomeRow))).scalar_one()
    assert outcome.direction_correct is True


@pytest.mark.asyncio
async def test_direction_correct_is_none_without_a_baseline(db_session):
    run_id = await _make_run(db_session)
    await _make_forecast(db_session, run_id, predicted_price=d(210), target_date=date(2026, 9, 3))
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="yfinance_daily", price=d(215))
    await db_session.commit()

    await ForecastAccuracyService().evaluate_ticker(db_session, "HUDCO", as_of=date(2026, 9, 3))

    outcome = (await db_session.execute(select(PredictionOutcomeRow))).scalar_one()
    assert outcome.direction_correct is None


@pytest.mark.asyncio
async def test_same_forecast_is_never_evaluated_twice(db_session):
    run_id = await _make_run(db_session)
    await _make_forecast(db_session, run_id, target_date=date(2026, 9, 3))
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="yfinance_daily", price=d(210))
    await db_session.commit()

    first = await ForecastAccuracyService().evaluate_ticker(db_session, "HUDCO", as_of=date(2026, 9, 3))
    second = await ForecastAccuracyService().evaluate_ticker(db_session, "HUDCO", as_of=date(2026, 9, 3))

    assert first == 1
    assert second == 0
    outcomes = (await db_session.execute(select(PredictionOutcomeRow))).scalars().all()
    assert len(outcomes) == 1


@pytest.mark.asyncio
async def test_unavailable_forecast_with_null_predicted_price_is_never_evaluated(db_session):
    run_id = await _make_run(db_session)
    await _make_forecast(db_session, run_id, predicted_price=None, target_date=date(2026, 9, 3))
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="yfinance_daily", price=d(210))
    await db_session.commit()

    written = await ForecastAccuracyService().evaluate_ticker(db_session, "HUDCO", as_of=date(2026, 9, 3))
    assert written == 0

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ForecastPredictionRow
from app.forecasting.ml.news.models import EventType, MarketTiming, NewsEvent, Sentiment
from app.forecasting.ml.persistence import MlForecastPersistence, news_event_row_to_domain


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


def _prediction_row(**overrides) -> ForecastPredictionRow:
    base = dict(
        ticker="RELIANCE", prediction_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        data_timestamp=date(2026, 1, 1), horizon="14D", model_version="v1", feature_version="v1",
        news_feature_version="v1", current_price=Decimal("1000"), predicted_return=Decimal("0.05"),
        predicted_price=Decimal("1050"), metadata_json="{}", target_date=date(2026, 1, 15),
    )
    base.update(overrides)
    return ForecastPredictionRow(**base)


async def test_save_and_get_predictions_round_trips(db_session):
    persistence = MlForecastPersistence(db_session)
    await persistence.save_prediction(_prediction_row())
    rows = await persistence.get_predictions("RELIANCE")
    assert len(rows) == 1
    assert rows[0].predicted_return == Decimal("0.05")


async def test_get_predictions_filters_by_horizon(db_session):
    persistence = MlForecastPersistence(db_session)
    await persistence.save_prediction(_prediction_row(horizon="14D"))
    await persistence.save_prediction(_prediction_row(horizon="1Y"))
    rows = await persistence.get_predictions("RELIANCE", horizon="1Y")
    assert len(rows) == 1 and rows[0].horizon == "1Y"


async def test_get_due_for_evaluation_only_returns_unevaluated_past_target_dates(db_session):
    persistence = MlForecastPersistence(db_session)
    await persistence.save_prediction(_prediction_row(target_date=date(2020, 1, 1)))  # due
    await persistence.save_prediction(_prediction_row(target_date=date(2099, 1, 1)))  # not due yet
    due = await persistence.get_due_for_evaluation(as_of=date(2026, 1, 1))
    assert len(due) == 1
    assert due[0].target_date == date(2020, 1, 1)


async def test_record_outcome_computes_direction_and_error(db_session):
    persistence = MlForecastPersistence(db_session)
    row = _prediction_row(predicted_return=Decimal("0.05"))
    await persistence.save_prediction(row)
    await persistence.record_outcome(row, actual_price=1030, actual_return=0.03, within_interval=True)
    assert row.direction_correct is True  # both predicted and actual positive
    assert row.absolute_error == pytest.approx(Decimal("0.02"), abs=Decimal("0.0001"))
    assert row.evaluated_at is not None


async def test_upsert_model_performance_is_idempotent_on_conflict(db_session):
    persistence = MlForecastPersistence(db_session)
    await persistence.upsert_model_performance(
        model_name="random_forest", model_version="v1", horizon="14D", scope="ALL", scope_value="ALL",
        sample_size=10, mae=0.05, rmse=0.07, directional_accuracy=0.6, brier_score=0.2, interval_coverage_80=0.8,
    )
    await persistence.upsert_model_performance(
        model_name="random_forest", model_version="v1", horizon="14D", scope="ALL", scope_value="ALL",
        sample_size=20, mae=0.04, rmse=0.06, directional_accuracy=0.65, brier_score=0.18, interval_coverage_80=0.82,
    )
    row = await persistence.get_performance(horizon="14D")
    assert row is not None
    assert row.sample_size == 20
    assert row.mae == Decimal("0.04")


def _news_event(headline="Wins order") -> NewsEvent:
    return NewsEvent(
        ticker="RELIANCE", published_at=datetime(2026, 1, 1, tzinfo=timezone.utc), headline=headline,
        event_type=EventType.ORDER_WIN, sentiment=Sentiment.POSITIVE, market_timing=MarketTiming.MARKET_HOURS,
    )


async def test_save_news_events_dedupes_identical_rows(db_session):
    persistence = MlForecastPersistence(db_session)
    await persistence.save_news_events([_news_event(), _news_event()])
    rows = await persistence.get_news_events("RELIANCE")
    assert len(rows) == 1


async def test_news_event_row_round_trips_to_domain(db_session):
    persistence = MlForecastPersistence(db_session)
    await persistence.save_news_events([_news_event("Wins big contract")])
    rows = await persistence.get_news_events("RELIANCE")
    domain_event = news_event_row_to_domain(rows[0])
    assert domain_event.event_type == EventType.ORDER_WIN
    assert domain_event.headline == "Wins big contract"

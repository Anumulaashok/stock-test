from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.alerts.service import AlertError, AlertService
from app.db.base import Base
from app.db.models import AlertRow, AlertTriggerRow, DailyPriceHistoryRow, ForecastPredictionRow, ResearchAnalysisSnapshotRow, ResearchRunRow
from app.models.alerts import AlertConditionType, AlertCreateRequest

USER = "user-1"
OTHER_USER = "user-2"


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


def service() -> AlertService:
    return AlertService(market_data_service=None)


# --- CRUD + ownership ------------------------------------------------------------


async def test_create_and_list_alert(db_session):
    svc = service()
    created = await svc.create_alert(
        db_session, USER, AlertCreateRequest(ticker="acme", condition_type=AlertConditionType.PRICE_ABOVE, threshold_value=Decimal("100"))
    )
    assert created.ticker == "ACME"
    listed = await svc.list_alerts(db_session, USER)
    assert [a.id for a in listed] == [created.id]


async def test_threshold_condition_requires_a_threshold_value():
    svc = service()
    with pytest.raises(AlertError) as exc_info:
        await svc.create_alert(None, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.PRICE_ABOVE, threshold_value=None))
    assert exc_info.value.code == "threshold_required"


async def test_duplicate_alert_is_rejected(db_session):
    svc = service()
    request = AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.PRICE_ABOVE, threshold_value=Decimal("100"))
    await svc.create_alert(db_session, USER, request)
    with pytest.raises(AlertError) as exc_info:
        await svc.create_alert(db_session, USER, request)
    assert exc_info.value.code == "duplicate_alert"


async def test_a_user_cannot_see_or_delete_another_users_alert(db_session):
    svc = service()
    alert = await svc.create_alert(
        db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.PRICE_ABOVE, threshold_value=Decimal("100"))
    )
    assert await svc.list_alerts(db_session, OTHER_USER) == []
    with pytest.raises(AlertError) as exc_info:
        await svc.delete_alert(db_session, OTHER_USER, alert.id)
    assert exc_info.value.code == "alert_not_found"


async def test_deleting_an_alert_cascades_its_triggers(db_session):
    svc = service()
    alert = await svc.create_alert(
        db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.PRICE_ABOVE, threshold_value=Decimal("50"))
    )
    db_session.add(AlertTriggerRow(alert_id=alert.id, observed_value="100"))
    await db_session.commit()

    await svc.delete_alert(db_session, USER, alert.id)

    remaining = await svc.list_triggers(db_session, USER)
    assert remaining == []


# --- Evaluation: price ------------------------------------------------------------


class _StubQuoteService:
    def __init__(self, price: Decimal | None) -> None:
        self._price = price

    async def get_quote(self, ticker: str):
        from app.models.market import MarketDataError, MarketDataErrorCode, MarketQuote, MarketSnapshot, MarketSnapshotResult, MarketStatus, PriceFreshness

        if self._price is None:
            return MarketSnapshotResult(status="error", error=MarketDataError(code=MarketDataErrorCode.TICKER_NOT_FOUND, message="n/a"))
        quote = MarketQuote(
            ticker=ticker, current_price=self._price, previous_close=self._price, change=Decimal(0), change_percent=Decimal(0),
            currency="INR", market_status=MarketStatus.OPEN, market_timestamp=None,
            data_timestamp="2026-08-21T00:00:00+00:00", freshness=PriceFreshness.LIVE, source="stub",
        )
        snapshot = MarketSnapshot(ticker=ticker, quote=quote, recent_prices=[], fetched_at="2026-08-21T00:00:00+00:00")
        return MarketSnapshotResult(status="success", snapshot=snapshot)


async def test_price_above_alert_fires_when_the_quote_exceeds_the_threshold(db_session):
    svc = AlertService(market_data_service=_StubQuoteService(Decimal("150")))
    await svc.create_alert(db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.PRICE_ABOVE, threshold_value=Decimal("100")))

    evaluations = await svc.evaluate_alerts(db_session, USER)

    assert evaluations[0].status == "met"
    assert evaluations[0].newly_triggered is True


async def test_price_alert_reports_unavailable_not_not_met_when_no_quote_exists(db_session):
    svc = AlertService(market_data_service=_StubQuoteService(None))
    await svc.create_alert(db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.PRICE_ABOVE, threshold_value=Decimal("100")))

    evaluations = await svc.evaluate_alerts(db_session, USER)

    assert evaluations[0].status == "unavailable"


async def test_repeated_evaluation_at_the_same_price_does_not_re_trigger(db_session):
    svc = AlertService(market_data_service=_StubQuoteService(Decimal("150")))
    await svc.create_alert(db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.PRICE_ABOVE, threshold_value=Decimal("100")))

    first = await svc.evaluate_alerts(db_session, USER)
    second = await svc.evaluate_alerts(db_session, USER)

    assert first[0].newly_triggered is True
    assert second[0].newly_triggered is False
    triggers = await svc.list_triggers(db_session, USER)
    assert len(triggers) == 1


# --- Evaluation: score -------------------------------------------------------------


async def _insert_completed_run_with_score(db_session, ticker: str, overall_score: str):
    run = ResearchRunRow(
        ticker=ticker, research_date=date(2026, 8, 20), started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc), status="COMPLETED", run_type="NORMAL",
        data_version="v1", calculation_version="v1", forecast_version="v1", prompt_version="v1", model_version="v1",
    )
    db_session.add(run)
    await db_session.flush()
    db_session.add(ResearchAnalysisSnapshotRow(
        research_run_id=run.id, ticker=ticker, financial_analysis_json="{}", valuation_json="{}",
        scoring_json=f'{{"overall_score": {overall_score}, "band": "good"}}', analysis_version="v1",
    ))
    await db_session.commit()


async def test_score_above_alert_fires_from_the_latest_persisted_score(db_session):
    await _insert_completed_run_with_score(db_session, "ACME", "82")
    svc = service()
    await svc.create_alert(db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.SCORE_ABOVE, threshold_value=Decimal("80")))

    evaluations = await svc.evaluate_alerts(db_session, USER)

    assert evaluations[0].status == "met"
    assert evaluations[0].observed_value == "82"


async def test_score_alert_is_unavailable_when_the_ticker_was_never_researched(db_session):
    svc = service()
    await svc.create_alert(db_session, USER, AlertCreateRequest(ticker="NEVERRESEARCHED", condition_type=AlertConditionType.SCORE_ABOVE, threshold_value=Decimal("80")))

    evaluations = await svc.evaluate_alerts(db_session, USER)

    assert evaluations[0].status == "unavailable"


# --- Evaluation: DMA crossover ------------------------------------------------------


async def _insert_dma(db_session, ticker: str, day: date, dma50: str, dma200: str):
    db_session.add(DailyPriceHistoryRow(ticker=ticker, date=day, price=Decimal("100"), dma50=Decimal(dma50), dma200=Decimal(dma200), source="test"))
    await db_session.commit()


async def test_golden_cross_alert_fires_when_dma50_is_above_dma200(db_session):
    await _insert_dma(db_session, "ACME", date(2026, 8, 20), "105", "100")
    svc = service()
    await svc.create_alert(db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.DMA_CROSSOVER_GOLDEN))

    evaluations = await svc.evaluate_alerts(db_session, USER)
    assert evaluations[0].status == "met"


async def test_death_cross_alert_does_not_fire_on_a_golden_cross_reading(db_session):
    await _insert_dma(db_session, "ACME", date(2026, 8, 20), "105", "100")
    svc = service()
    await svc.create_alert(db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.DMA_CROSSOVER_DEATH))

    evaluations = await svc.evaluate_alerts(db_session, USER)
    assert evaluations[0].status == "not_met"


# --- Evaluation: regime change -------------------------------------------------------


async def _insert_prediction_with_regime(db_session, ticker: str, regime: str, ts: datetime):
    db_session.add(ForecastPredictionRow(
        ticker=ticker, prediction_timestamp=ts, data_timestamp=date(2026, 8, 20), horizon="14D",
        model_version="v1", feature_version="v1", news_feature_version="v1",
        current_price=Decimal("100"), predicted_return=Decimal("0.01"), predicted_price=Decimal("101"),
        regime=regime, target_date=date(2026, 9, 3), metadata_json="{}",
    ))
    await db_session.commit()


async def test_regime_change_alert_does_not_fire_on_the_first_evaluation(db_session):
    # First read only "primes" what regime was last seen -- it never
    # fires just because a regime exists (see AlertService._evaluate_one).
    await _insert_prediction_with_regime(db_session, "ACME", "TRENDING_UP", datetime(2026, 8, 20, tzinfo=timezone.utc))
    svc = service()
    await svc.create_alert(db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.REGIME_CHANGE))

    evaluations = await svc.evaluate_alerts(db_session, USER)
    assert evaluations[0].status == "not_met"


async def test_regime_change_alert_fires_once_the_regime_actually_changes(db_session):
    await _insert_prediction_with_regime(db_session, "ACME", "TRENDING_UP", datetime(2026, 8, 20, tzinfo=timezone.utc))
    svc = service()
    await svc.create_alert(db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.REGIME_CHANGE))
    await svc.evaluate_alerts(db_session, USER)  # primes last_seen_regime

    await _insert_prediction_with_regime(db_session, "ACME", "HIGH_VOLATILITY", datetime(2026, 8, 21, tzinfo=timezone.utc))
    evaluations = await svc.evaluate_alerts(db_session, USER)

    assert evaluations[0].status == "met"
    assert evaluations[0].observed_value == "HIGH_VOLATILITY"


# --- Triggers ------------------------------------------------------------------------


async def test_acknowledge_trigger_is_owner_scoped(db_session):
    svc = service()
    alert = await svc.create_alert(db_session, USER, AlertCreateRequest(ticker="ACME", condition_type=AlertConditionType.PRICE_ABOVE, threshold_value=Decimal("50")))
    trigger_row = AlertTriggerRow(alert_id=alert.id, observed_value="100")
    db_session.add(trigger_row)
    await db_session.commit()
    await db_session.refresh(trigger_row)

    with pytest.raises(AlertError):
        await svc.acknowledge_trigger(db_session, OTHER_USER, trigger_row.id)

    await svc.acknowledge_trigger(db_session, USER, trigger_row.id)
    unacknowledged = await svc.list_triggers(db_session, USER, unacknowledged_only=True)
    assert unacknowledged == []

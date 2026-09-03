from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.data.daily_price_history_service import upsert_daily_price
from app.db.base import Base
from app.db.models import DailyPriceHistoryRow


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


async def _get_row(db, ticker, day) -> DailyPriceHistoryRow | None:
    stmt = select(DailyPriceHistoryRow).where(DailyPriceHistoryRow.ticker == ticker, DailyPriceHistoryRow.date == day)
    return (await db.execute(stmt)).scalar_one_or_none()


@pytest.mark.asyncio
async def test_inserts_a_new_row(db_session):
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="screener_import", price=d("181.07"))
    await db_session.commit()

    row = await _get_row(db_session, "HUDCO", date(2026, 9, 3))
    assert row is not None
    assert row.price == d("181.07")
    assert row.source == "screener_import"


@pytest.mark.asyncio
async def test_ticker_is_normalized_to_uppercase(db_session):
    await upsert_daily_price(db_session, "hudco", date(2026, 9, 3), source="screener_import", price=d("181.07"))
    await db_session.commit()
    assert await _get_row(db_session, "HUDCO", date(2026, 9, 3)) is not None


@pytest.mark.asyncio
async def test_screener_import_overwrites_a_prior_screener_import(db_session):
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="screener_import", price=d("181.07"))
    await db_session.commit()
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="screener_import", price=d("182.00"))
    await db_session.commit()

    row = await _get_row(db_session, "HUDCO", date(2026, 9, 3))
    assert row.price == d("182.00")


@pytest.mark.asyncio
async def test_yfinance_daily_overwrites_a_prior_screener_import(db_session):
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="screener_import", price=d("181.07"))
    await db_session.commit()
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="yfinance_daily", price=d("183.00"))
    await db_session.commit()

    row = await _get_row(db_session, "HUDCO", date(2026, 9, 3))
    assert row.price == d("183.00")
    assert row.source == "yfinance_daily"


@pytest.mark.asyncio
async def test_screener_backfill_never_clobbers_a_live_yfinance_row(db_session):
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="yfinance_daily", price=d("183.00"))
    await db_session.commit()
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="screener_import", price=d("999.00"))
    await db_session.commit()

    row = await _get_row(db_session, "HUDCO", date(2026, 9, 3))
    assert row.price == d("183.00")
    assert row.source == "yfinance_daily"


@pytest.mark.asyncio
async def test_a_partial_update_does_not_blank_fields_it_did_not_report(db_session):
    """A field the new write left unset (None) must not overwrite a value
    a previous write already recorded -- an update that only has a price
    (e.g. a quote) must not erase an existing delivery percentage."""
    await upsert_daily_price(
        db_session, "HUDCO", date(2026, 9, 3),
        source="screener_import", price=d("181.07"), volume=d(1000), delivery_percentage=d("42.5"),
    )
    await db_session.commit()

    await upsert_daily_price(
        db_session, "HUDCO", date(2026, 9, 3), source="screener_import", price=d("182.00")
    )
    await db_session.commit()

    row = await _get_row(db_session, "HUDCO", date(2026, 9, 3))
    assert row.price == d("182.00")
    assert row.volume == d(1000)
    assert row.delivery_percentage == d("42.5")


async def test_two_live_sources_on_the_same_date_still_overwrite(db_session):
    """Backfill-over-live is blocked; live-over-live still applies."""
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="yfinance_daily", price=d("183.00"))
    await db_session.commit()
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="fmp_daily", price=d("183.50"))
    await db_session.commit()

    row = await _get_row(db_session, "HUDCO", date(2026, 9, 3))
    assert row.price == d("183.50")
    assert row.source == "fmp_daily"


async def test_different_dates_do_not_collide(db_session):
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 2), source="screener_import", price=d(1))
    await upsert_daily_price(db_session, "HUDCO", date(2026, 9, 3), source="screener_import", price=d(2))
    await db_session.commit()

    assert (await _get_row(db_session, "HUDCO", date(2026, 9, 2))).price == d(1)
    assert (await _get_row(db_session, "HUDCO", date(2026, 9, 3))).price == d(2)

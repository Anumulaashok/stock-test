"""Shared upsert logic for `daily_price_history` — used by both the
one-time Screener bulk import (`app.data.screener_import_service`) and
the ongoing daily accumulation from live market-data fetches
(`app.snapshot.service`). One place owns the "which source wins on a
same-day conflict" rule so it can't drift between the two callers.
"""

import logging
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyPriceHistoryRow

logger = logging.getLogger(__name__)


async def upsert_daily_price(
    db: AsyncSession,
    ticker: str,
    day: date_type,
    *,
    source: str,
    price: Decimal | None = None,
    dma50: Decimal | None = None,
    dma200: Decimal | None = None,
    volume: Decimal | None = None,
    delivery_percentage: Decimal | None = None,
) -> None:
    """Does not commit — callers batch this with whatever else they're
    already committing in the same unit of work."""
    ticker = ticker.strip().upper()
    stmt = select(DailyPriceHistoryRow).where(
        DailyPriceHistoryRow.ticker == ticker, DailyPriceHistoryRow.date == day
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is None:
        db.add(
            DailyPriceHistoryRow(
                ticker=ticker, date=day, price=price, dma50=dma50, dma200=dma200,
                volume=volume, delivery_percentage=delivery_percentage, source=source,
            )
        )
        logger.info("daily_price_history_inserted ticker=%s date=%s source=%s", ticker, day, source)
        return

    # A one-time historical backfill (screener_import) must never
    # overwrite a figure the ongoing daily accumulation (yfinance_daily)
    # already recorded for that date -- the live source is authoritative
    # for the day it actually observed.
    if existing.source == "yfinance_daily" and source == "screener_import":
        logger.info(
            "daily_price_history_skip_backfill_over_live ticker=%s date=%s", ticker, day
        )
        return

    existing.price = price
    existing.dma50 = dma50
    existing.dma200 = dma200
    existing.volume = volume
    existing.delivery_percentage = delivery_percentage
    existing.source = source
    existing.imported_at = datetime.now(timezone.utc)
    logger.info("daily_price_history_updated ticker=%s date=%s source=%s", ticker, day, source)

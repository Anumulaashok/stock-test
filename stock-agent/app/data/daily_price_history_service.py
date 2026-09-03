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

# Ownership rule (documented, fixed): a one-time historical backfill
# (any "*_import" source, e.g. "screener_import") must never overwrite a
# row an ongoing live accumulation (any "*_daily" source, e.g.
# "yfinance_daily", "fmp_daily") already wrote for that date -- the
# provider that actually observed the day live is authoritative for it,
# regardless of which provider is configured as the historical primary.
# Two "*_daily" sources (or two "*_import" sources) for the same date
# simply overwrite in write order; that case doesn't currently arise
# since only one live accumulator runs per research request.
def _is_backfill(source: str) -> bool:
    return source.endswith("_import")


def _is_live(source: str) -> bool:
    return source.endswith("_daily")


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

    if _is_live(existing.source) and _is_backfill(source):
        logger.info(
            "daily_price_history_skip_backfill_over_live ticker=%s date=%s existing_source=%s new_source=%s",
            ticker, day, existing.source, source,
        )
        return

    # Only overwrite a field when the new source actually reported a
    # value -- a partial update (e.g. a quote with price but no delivery
    # percentage) must not blank a field a previous write filled in.
    if price is not None:
        existing.price = price
    if dma50 is not None:
        existing.dma50 = dma50
    if dma200 is not None:
        existing.dma200 = dma200
    if volume is not None:
        existing.volume = volume
    if delivery_percentage is not None:
        existing.delivery_percentage = delivery_percentage
    existing.source = source
    existing.imported_at = datetime.now(timezone.utc)
    logger.info("daily_price_history_updated ticker=%s date=%s source=%s", ticker, day, source)

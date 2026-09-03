"""Orchestrates a one-time historical bulk import from Screener.in into
`daily_price_history` -- the seed data `app.forecasting.accuracy_service`
and the ongoing daily yfinance accumulation (`app.snapshot.service`)
both build on. Never called automatically; only triggered by
`POST /api/v1/market/{ticker}/historical/import`, since Screener's
numeric company id must be supplied manually (see
`app.data.providers.screener_client`).
"""

import logging
from datetime import date as date_type

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.daily_price_history_service import upsert_daily_price
from app.data.mappers.screener import map_screener_chart, map_screener_company_list
from app.data.providers.screener_client import ScreenerClient, ScreenerImportError, ScreenerMappingNotFoundError
from app.db.models import ScreenerCompanyMappingRow

logger = logging.getLogger(__name__)


class ScreenerImportService:
    def __init__(self, client: ScreenerClient) -> None:
        self._client = client

    async def import_historical_prices(
        self,
        db: AsyncSession,
        ticker: str,
        screener_company_id: int | None = None,
        days: int = 365,
        consolidated: bool = True,
    ) -> tuple[int, str | None, str | None]:
        """Returns `(rows_imported, earliest_date, latest_date)` (dates
        as ISO strings, `None` if nothing was imported). When
        `screener_company_id` is omitted, the ticker's stored mapping
        (from a prior single import or a bulk company-list import) is
        used instead -- this is what makes a mapping "reused always"
        once it's been registered once."""
        ticker = ticker.strip().upper()

        if screener_company_id is None:
            existing = await db.get(ScreenerCompanyMappingRow, ticker)
            if existing is None:
                raise ScreenerMappingNotFoundError(
                    f"No Screener company id is known for '{ticker}' yet -- supply screener_company_id "
                    "once, or bulk-import a Screener company-search list first."
                )
            screener_company_id = existing.screener_company_id
            consolidated = existing.consolidated

        raw = await self._client.get_chart(screener_company_id, days=days, consolidated=consolidated)
        rows = map_screener_chart(raw)

        await self._upsert_mapping(db, ticker, screener_company_id, consolidated)

        imported = 0
        min_date: date_type | None = None
        max_date: date_type | None = None
        for row in rows:
            try:
                parsed_date = date_type.fromisoformat(row["date"])
            except (KeyError, ValueError):
                continue
            await upsert_daily_price(
                db, ticker, parsed_date, source="screener_import",
                price=row.get("price"), dma50=row.get("dma50"), dma200=row.get("dma200"),
                volume=row.get("volume"), delivery_percentage=row.get("delivery_percentage"),
            )
            imported += 1
            min_date = parsed_date if min_date is None else min(min_date, parsed_date)
            max_date = parsed_date if max_date is None else max(max_date, parsed_date)

        await db.commit()
        logger.info(
            "screener_historical_import_completed ticker=%s screener_company_id=%s rows_imported=%d",
            ticker, screener_company_id, imported,
        )
        return imported, min_date.isoformat() if min_date else None, max_date.isoformat() if max_date else None

    async def register_company_mappings(self, db: AsyncSession, entries: list[dict]) -> int:
        """Bulk-upserts `[{ticker, company_name, screener_company_id, consolidated}, ...]`
        (see `app.data.mappers.screener.map_screener_company_list`) --
        the reusable store behind the ticker-input autocomplete and
        behind `import_historical_prices`'s auto-lookup. Returns the
        number of tickers registered/updated."""
        count = 0
        for entry in entries:
            await self._upsert_mapping(
                db, entry["ticker"], entry["screener_company_id"], entry.get("consolidated", True),
                company_name=entry.get("company_name"),
            )
            count += 1
        await db.commit()
        logger.info("screener_company_mappings_registered count=%d", count)
        return count

    async def search_live_and_register(self, db: AsyncSession, query: str) -> list[dict]:
        """Searches Screener.in itself (`ScreenerClient.search_companies`,
        needs `SCREENER_SESSION_COOKIE`) and registers every matched
        company as a mapping in the same call -- so a live search result
        is immediately reusable by `search_mappings`/`import_historical_prices`
        without a separate bulk-paste step. Raises `ScreenerImportError`
        on any fetch failure; callers decide whether/how to fall back."""
        raw = await self._client.search_companies(query)
        entries = map_screener_company_list(raw)
        if entries:
            await self.register_company_mappings(db, entries)
        return entries

    async def search_mappings(self, db: AsyncSession, query: str, limit: int = 10) -> list[ScreenerCompanyMappingRow]:
        """Ticker-input autocomplete -- matches on either the ticker or
        the stored company name, case-insensitive prefix/substring."""
        query = query.strip()
        if not query:
            return []
        pattern = f"%{query}%"
        stmt = (
            select(ScreenerCompanyMappingRow)
            .where(
                or_(
                    func.upper(ScreenerCompanyMappingRow.ticker).like(pattern.upper()),
                    func.upper(ScreenerCompanyMappingRow.company_name).like(pattern.upper()),
                )
            )
            .order_by(ScreenerCompanyMappingRow.ticker)
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def _upsert_mapping(
        self,
        db: AsyncSession,
        ticker: str,
        screener_company_id: int,
        consolidated: bool,
        company_name: str | None = None,
    ) -> None:
        ticker = ticker.strip().upper()
        existing = await db.get(ScreenerCompanyMappingRow, ticker)
        if existing is None:
            db.add(
                ScreenerCompanyMappingRow(
                    ticker=ticker, company_name=company_name,
                    screener_company_id=screener_company_id, consolidated=consolidated,
                )
            )
        else:
            existing.screener_company_id = screener_company_id
            existing.consolidated = consolidated
            if company_name is not None:
                existing.company_name = company_name

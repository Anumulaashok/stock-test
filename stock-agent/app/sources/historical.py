"""Historical daily prices, resolved across the configured chain.

Ownership rule, chosen and fixed: PRIMARY SOURCE WINS. For a given
(ticker, date) the higher-priority provider in the historical chain owns
the bar. A lower-priority provider only fills dates the primary does not
cover, and is replaced if the primary later supplies that date.

Screener supplies a close-only series (close, DMA50/200, volume) — the
open/high/low fields are left None rather than being back-filled with
the close, so nothing downstream mistakes a synthesized value for a real
one.
"""

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.data.mappers.screener import map_screener_chart, map_screener_company_list
from app.data.providers.screener_client import ScreenerClient, ScreenerImportError
from app.db.models import ScreenerCompanyMappingRow
from app.models.market import HistoricalPricePoint
from app.sources.identity import CompanyIdentity
from app.sources.provenance import SourceAttempt, SourceStatus
from app.sources.registry import SCREENER

logger = logging.getLogger(__name__)

# Screener's chart endpoint takes a day window rather than a bar count.
_DAYS_PER_TRADING_DAY = 1.5


class ScreenerHistoricalProvider:
    """Adapts Screener's chart endpoint to the market layer's price
    points. Returns a status rather than raising, so the manager can
    decide to fall back."""

    name = SCREENER

    def __init__(self, client: ScreenerClient) -> None:
        self._client = client

    async def get_recent_prices(
        self, db: AsyncSession, identity: CompanyIdentity, limit: int
    ) -> tuple[list[HistoricalPricePoint], SourceAttempt]:
        if not self._client.has_cookie:
            return [], SourceAttempt(
                provider=self.name,
                status=SourceStatus.NOT_CONFIGURED,
                detail="No Screener session cookie is configured.",
            )
        screener_company_id = identity.screener_company_id
        if screener_company_id is None:
            # No mapping exists yet -- a ticker found via the fast local
            # search list (the common case) never goes through
            # `/company-search`'s auto-register path, so it would
            # otherwise stay permanently unmapped and this "primary"
            # historical source would silently never activate for it.
            # One-time lazy resolution: search Screener directly for
            # this exact ticker and register the mapping on first use.
            screener_company_id = await self._resolve_and_register_mapping(db, identity.canonical_ticker)
        if screener_company_id is None:
            return [], SourceAttempt(
                provider=self.name,
                status=SourceStatus.UNAVAILABLE,
                detail=f"No Screener company mapping is stored for {identity.canonical_ticker}.",
            )

        days = int(limit * _DAYS_PER_TRADING_DAY) + 1
        try:
            raw = await self._client.get_chart(screener_company_id, days=days)
        except ScreenerImportError as exc:
            return [], SourceAttempt(provider=self.name, status=exc.status, detail=str(exc))

        rows = map_screener_chart(raw)
        if not rows:
            return [], SourceAttempt(
                provider=self.name,
                status=SourceStatus.UNAVAILABLE,
                detail="Screener returned no chart data.",
            )

        points = [
            HistoricalPricePoint(
                timestamp=row["date"],
                open=None,
                high=None,
                low=None,
                close=_as_decimal(row.get("price")),
                volume=_as_decimal(row.get("volume")),
            )
            for row in rows
            if row.get("date")
        ]
        # The mapper returns rows in dict order; sort before taking the
        # most recent `limit` bars.
        points = sorted(
            (p for p in points if p.close is not None), key=lambda p: p.timestamp
        )[-limit:]
        if not points:
            return [], SourceAttempt(
                provider=self.name,
                status=SourceStatus.UNAVAILABLE,
                detail="Screener chart data contained no usable closing prices.",
            )
        return points, SourceAttempt(provider=self.name, status=SourceStatus.SUCCESS)

    async def _resolve_and_register_mapping(self, db: AsyncSession, ticker: str) -> int | None:
        """Searches Screener.in directly for `ticker` and, on a
        confident match, registers the mapping so future calls (this
        run's other stages, and every later research run) find it via
        `CompanyIdentityResolver.resolve()`'s plain DB lookup without
        repeating this search.

        "Confident" is either an exact ticker match, or a BSE-only
        listing (no NSE listing at all, so no NSE symbol for Screener
        to return): its `url`-derived "ticker" is BSE's own numeric
        code instead (e.g. "532329" for a company this app tracks as
        e.g. "DANLAW"), which never equals this app's ticker no matter
        how correct the match is. That narrow case -- Screener's
        result is purely numeric, and it's the only result for a query
        that was this app's own ticker -- is accepted; anything else
        with no exact match (including a single non-numeric,
        presumably unrelated, result) is treated as genuinely
        ambiguous and skipped, never guessed. The mapping is always
        registered under *this app's* ticker (never Screener's own
        numeric/BSE one), since that's the key
        `CompanyIdentityResolver.resolve()` looks up by -- only
        `screener_company_id` needs to be Screener's.

        Writes on a short-lived session of its own (mirrors
        `SqlCacheStore`'s established pattern) so a failed/slow mapping
        write can never poison the caller's own research transaction --
        any failure here just means the id isn't persisted for next
        time; it still returns the id so THIS call's chart fetch can
        use it.
        """
        try:
            raw = await self._client.search_companies(ticker)
        except ScreenerImportError as exc:
            logger.info("screener_lazy_mapping_lookup_failed ticker=%s error=%s", ticker, exc)
            return None

        entries = map_screener_company_list(raw)
        match = next((e for e in entries if e["ticker"].upper() == ticker.upper()), None)
        if match is None and len(entries) == 1 and entries[0]["ticker"].isdigit():
            match = entries[0]
        if match is None:
            return None

        try:
            write_session_factory = async_sessionmaker(bind=db.bind, expire_on_commit=False)
            async with write_session_factory() as write_session:
                existing = await write_session.get(ScreenerCompanyMappingRow, ticker)
                if existing is None:
                    write_session.add(
                        ScreenerCompanyMappingRow(
                            ticker=ticker,
                            company_name=match.get("company_name"),
                            screener_company_id=match["screener_company_id"],
                            consolidated=match.get("consolidated", True),
                        )
                    )
                else:
                    existing.screener_company_id = match["screener_company_id"]
                    existing.consolidated = match.get("consolidated", True)
                    if match.get("company_name") is not None:
                        existing.company_name = match["company_name"]
                await write_session.commit()
        except Exception:
            logger.warning("screener_lazy_mapping_write_failed ticker=%s", ticker, exc_info=True)

        return match["screener_company_id"]


def _as_decimal(value) -> Decimal | None:
    if value is None or isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return None


def merge_by_primary(
    series: list[tuple[str, list[HistoricalPricePoint]]],
) -> list[HistoricalPricePoint]:
    """Combine per-source series under the primary-source-wins rule.

    `series` is ordered by provider priority. A later (lower-priority)
    source contributes only the dates no earlier source covered.
    """
    merged: dict[str, HistoricalPricePoint] = {}
    for _source, points in series:
        for point in points:
            merged.setdefault(point.timestamp, point)
    return [merged[key] for key in sorted(merged)]

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

from sqlalchemy.ext.asyncio import AsyncSession

from app.data.mappers.screener import map_screener_chart
from app.data.providers.screener_client import ScreenerClient, ScreenerImportError
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
        if identity.screener_company_id is None:
            return [], SourceAttempt(
                provider=self.name,
                status=SourceStatus.UNAVAILABLE,
                detail=f"No Screener company mapping is stored for {identity.canonical_ticker}.",
            )

        days = int(limit * _DAYS_PER_TRADING_DAY) + 1
        try:
            raw = await self._client.get_chart(identity.screener_company_id, days=days)
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

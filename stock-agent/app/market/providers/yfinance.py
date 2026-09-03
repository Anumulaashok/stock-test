"""YFinanceMarketProvider: implements `MarketDataProvider` via the
`yfinance` library (unofficial Yahoo Finance API -- no key required).
Supplies `market_cap`/`year_high`/`year_low` and real per-day OHLCV that
neither IndianAPI nor FMP provide on this project's plans -- see
`app.market.mappers.yfinance` for field provenance.
"""

from app.market.base import MarketDataProvider
from app.market.mappers.yfinance import map_historical_prices, map_quote
from app.market.providers.yfinance_client import YFinanceClient
from app.models.market import HistoricalPricePoint, MarketQuote


class YFinanceMarketProvider(MarketDataProvider):
    def __init__(self, client: YFinanceClient) -> None:
        self._client = client

    async def get_quote(self, ticker: str) -> MarketQuote:
        raw = await self._client.get_fast_info(ticker)
        return map_quote(raw, ticker)

    async def get_recent_prices(self, ticker: str, limit: int) -> list[HistoricalPricePoint]:
        # `limit` is a day-count budget, not an API page size -- fetch a
        # broad period and trim, mirroring FMPMarketProvider/IndianAPIMarketProvider.
        period = "5y" if limit > 365 else "1y"
        raw_records = await self._client.get_history(ticker, period=period)
        points = map_historical_prices(raw_records)
        return points[-limit:] if limit else points

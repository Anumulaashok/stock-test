"""FMPMarketProvider: implements `MarketDataProvider` for FMP's quote
endpoints. Combines `FMPMarketClient` (HTTP) and `app.market.mappers.fmp`
(schema mapping) so FMP's field names never leak past this module.
"""

from app.market.base import MarketDataProvider
from app.market.mappers.fmp import map_historical_prices, map_quote
from app.market.providers.fmp_client import FMPMarketClient
from app.models.market import HistoricalPricePoint, MarketQuote


class FMPMarketProvider(MarketDataProvider):
    def __init__(self, client: FMPMarketClient) -> None:
        self._client = client

    async def get_quote(self, ticker: str) -> MarketQuote:
        raw = await self._client.get_quote(ticker)
        return map_quote(raw, ticker)

    async def get_recent_prices(self, ticker: str, limit: int) -> list[HistoricalPricePoint]:
        raw_records = await self._client.get_historical_prices(ticker, limit)
        return map_historical_prices(raw_records)

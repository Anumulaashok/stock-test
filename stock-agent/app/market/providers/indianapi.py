"""IndianAPIMarketProvider: implements `MarketDataProvider` for
stock.indianapi.in. Reuses the same `IndianAPIClient` (and account/auth)
`app.data.providers.indianapi.IndianAPIProvider` already uses for
financial statements -- this is the SAME India-only vendor, just a
different endpoint (`/stock`'s `currentPrice`/`stockTechnicalData` and
`/historical_data`) -- no new API key is required.
"""

from app.data.exceptions import ProviderError
from app.data.providers.indianapi_client import IndianAPIClient
from app.market.base import MarketDataProvider
from app.market.exceptions import MarketProviderError
from app.market.mappers.indianapi import map_historical_prices, map_quote
from app.models.market import HistoricalPricePoint, MarketDataErrorCode, MarketQuote

_ERROR_CODE_BY_PROVIDER_CODE = {
    "provider_unavailable": MarketDataErrorCode.PROVIDER_UNAVAILABLE,
    "authentication_failed": MarketDataErrorCode.AUTHENTICATION_FAILED,
    "rate_limited": MarketDataErrorCode.RATE_LIMITED,
    "company_not_found": MarketDataErrorCode.TICKER_NOT_FOUND,
    "invalid_response": MarketDataErrorCode.INVALID_RESPONSE,
    "schema_mismatch": MarketDataErrorCode.SCHEMA_MISMATCH,
}


class IndianAPIMarketProvider(MarketDataProvider):
    def __init__(self, client: IndianAPIClient) -> None:
        self._client = client

    async def get_quote(self, ticker: str) -> MarketQuote:
        try:
            raw = await self._client.get_stock(ticker)
        except ProviderError as exc:
            raise self._translate(exc) from exc
        return map_quote(raw, ticker)

    async def get_recent_prices(self, ticker: str, limit: int) -> list[HistoricalPricePoint]:
        # `limit` is a day-count budget, not an API page size -- fetch a
        # full year and trim, mirroring FMPMarketProvider's contract.
        period = "3yr" if limit > 365 else "1yr"
        try:
            raw = await self._client.get_historical_prices(ticker, period=period)
        except ProviderError as exc:
            raise self._translate(exc) from exc
        points = map_historical_prices(raw)
        return points[-limit:] if limit else points

    @staticmethod
    def _translate(exc: ProviderError) -> MarketProviderError:
        code = _ERROR_CODE_BY_PROVIDER_CODE.get(exc.code.value, MarketDataErrorCode.PROVIDER_UNAVAILABLE)
        return MarketProviderError(code, exc.message, retry_after=getattr(exc, "retry_after", None))

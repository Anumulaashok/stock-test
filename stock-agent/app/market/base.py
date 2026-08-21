"""Provider-agnostic market-data interface — a separate abstraction from
`app.data.base.FinancialDataProvider`. A `MarketDataProvider` supplies
*prices* (current quote, recent OHLCV); it must never be asked for
financial statements, and `FinancialDataProvider` must never be asked
for a price.
"""

from abc import ABC, abstractmethod

from app.models.market import HistoricalPricePoint, MarketQuote


class MarketDataProvider(ABC):
    @abstractmethod
    async def get_quote(self, ticker: str) -> MarketQuote:
        """Raises `app.market.exceptions.MarketProviderError` on failure.
        Never fabricates a price, change, or timestamp the provider
        didn't actually report."""
        raise NotImplementedError

    @abstractmethod
    async def get_recent_prices(self, ticker: str, limit: int) -> list[HistoricalPricePoint]:
        """Most-recent-first is not guaranteed; ordering is whatever the
        provider returns. Raises `MarketProviderError` on failure."""
        raise NotImplementedError

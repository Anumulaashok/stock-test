"""Market-data orchestration.

`MarketDataService` fetches a quote (and optionally recent prices) and
converts any `MarketProviderError` into a structured `MarketSnapshotResult`
— callers never need exception handling for an expected failure
(provider down, ticker not found, rate limited, ...). Never calculates a
financial metric, never touches valuation/scoring, never calls the LLM.
"""

import logging
from datetime import datetime, timezone

from app.market.base import MarketDataProvider
from app.market.exceptions import MarketProviderError
from app.models.market import MarketDataError, MarketSnapshot, MarketSnapshotResult

logger = logging.getLogger(__name__)

DEFAULT_RECENT_PRICES_LIMIT = 30


class MarketDataService:
    def __init__(self, provider: MarketDataProvider, default_recent_prices_limit: int = DEFAULT_RECENT_PRICES_LIMIT) -> None:
        self._provider = provider
        self._default_recent_prices_limit = default_recent_prices_limit

    async def get_snapshot(self, ticker: str, include_recent_prices: bool = True) -> MarketSnapshotResult:
        fetched_at = datetime.now(timezone.utc).isoformat()
        warnings: list[str] = []

        try:
            quote = await self._provider.get_quote(ticker)
        except MarketProviderError as exc:
            logger.warning("Market data provider error for %s: %s [%s]", ticker, exc.message, exc.code)
            return MarketSnapshotResult(
                status="error", error=MarketDataError(code=exc.code, message=exc.message)
            )

        recent_prices = []
        if include_recent_prices:
            try:
                recent_prices = await self._provider.get_recent_prices(
                    ticker, self._default_recent_prices_limit
                )
            except MarketProviderError as exc:
                # Recent prices are supplementary -- a quote without
                # history is still a usable snapshot.
                logger.warning(
                    "Market data provider error fetching recent prices for %s: %s", ticker, exc.message
                )
                warnings.append(f"recent price history unavailable: {exc.message}")

        snapshot = MarketSnapshot(
            ticker=ticker, quote=quote, recent_prices=recent_prices, fetched_at=fetched_at, warnings=warnings
        )
        return MarketSnapshotResult(status="success", snapshot=snapshot)

    async def get_quote(self, ticker: str) -> MarketSnapshotResult:
        return await self.get_snapshot(ticker, include_recent_prices=False)

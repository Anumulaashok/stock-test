"""Caches `MarketDataService.get_snapshot` results.

Market quotes are live data, so this uses a much shorter TTL than
`CachedFinancialDataService` (see `Settings.market_data_cache_ttl_seconds`)
-- just enough to collapse bursts of requests for the same ticker
(e.g. a watchlist dashboard rendering several rows) without serving a
meaningfully stale price.
"""

import logging

from app.cache.store import CacheStore
from app.cache.versioning import CACHE_SCHEMA_VERSION
from app.market.service import MarketDataService
from app.models.market import MarketSnapshotResult

logger = logging.getLogger(__name__)


class CachedMarketDataService:
    def __init__(
        self,
        inner: MarketDataService,
        cache: CacheStore,
        provider_name: str,
        ttl_seconds: int,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._provider_name = provider_name
        self._ttl_seconds = ttl_seconds

    def _key(self, ticker: str, include_recent_prices: bool) -> str:
        return (
            f"market_snapshot:{CACHE_SCHEMA_VERSION}:{self._provider_name}:"
            f"{ticker.strip().upper()}:{include_recent_prices}"
        )

    async def get_snapshot(self, ticker: str, include_recent_prices: bool = True) -> MarketSnapshotResult:
        key = self._key(ticker, include_recent_prices)
        hit = await self._cache.get(key)
        if hit is not None and not hit.is_expired:
            logger.info("provider_cache_hit provider=%s ticker=%s data_type=market_snapshot", self._provider_name, ticker)
            return MarketSnapshotResult.model_validate_json(hit.value)

        logger.info("provider_fetch provider=%s ticker=%s data_type=market_snapshot", self._provider_name, ticker)
        result = await self._inner.get_snapshot(ticker, include_recent_prices=include_recent_prices)

        if result.status == "success":
            await self._cache.set(key, result.model_dump_json(), self._ttl_seconds)
            return result

        if hit is not None:
            logger.info("Market data provider failed for %s; serving cached snapshot instead", ticker)
            return MarketSnapshotResult.model_validate_json(hit.value)
        return result

    async def get_quote(self, ticker: str) -> MarketSnapshotResult:
        return await self.get_snapshot(ticker, include_recent_prices=False)

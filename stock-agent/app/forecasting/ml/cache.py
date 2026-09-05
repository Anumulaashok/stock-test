"""Caches `MlForecastPipeline.predict` results (spec section 29), mirroring
`app.cache.market_data.CachedMarketDataService`. A forecast is much more
expensive to compute than a market quote (a 5-year price fetch plus
several model evaluations per horizon) but doesn't need to be as fresh --
new price data only lands once a day, so a longer TTL than the market
quote cache is appropriate.
"""

import logging

from pydantic import ValidationError

from app.cache.store import CacheStore
from app.cache.versioning import CACHE_SCHEMA_VERSION
from app.forecasting.ml.pipeline import MlForecastPipeline
from app.forecasting.ml.versions import FEATURE_VERSION, MODEL_VERSION
from app.models.ml_forecast import MlForecastResult

logger = logging.getLogger(__name__)


class CachedMlForecastPipeline:
    def __init__(self, inner: MlForecastPipeline, cache: CacheStore, ttl_seconds: int = 1800) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    def _key(self, ticker: str) -> str:
        return f"ml_forecast:{CACHE_SCHEMA_VERSION}:{MODEL_VERSION}:{FEATURE_VERSION}:{ticker.strip().upper()}"

    async def predict(self, ticker: str, *, company_name: str | None = None, force_refresh: bool = False) -> MlForecastResult:
        key = self._key(ticker)
        if not force_refresh:
            hit = await self._cache.get(key)
            if hit is not None and not hit.is_expired:
                try:
                    return MlForecastResult.model_validate_json(hit.value)
                except ValidationError:
                    # A cached payload from a since-changed response
                    # schema (a field added/removed) -- treat exactly
                    # like a cache miss rather than 500ing; the fresh
                    # write below overwrites the stale entry.
                    logger.info("ml_forecast_cache_schema_mismatch ticker=%s", ticker)

        result = await self._inner.predict(ticker, company_name=company_name)
        await self._cache.set(key, result.model_dump_json(), self._ttl_seconds)
        return result

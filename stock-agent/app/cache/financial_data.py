"""Caches `FinancialDataService.get_company_financials` results.

`/api/v1/analyze/ticker` and `/api/v1/qa/ticker` each independently
fetch the same provider financials for a ticker (see
`app/application/service.py`). Financial statements don't change
intra-day, so this de-duplicates that cost within the configured TTL
instead of hitting the external provider twice per user session.

Wraps `FinancialDataService` rather than modifying it, so the plain
`POST /api/v1/analyze` request path (which never fetches from a
provider) and every existing test of `FinancialDataService` itself are
unaffected.

A failed fetch (`status="error"`) is cached too, under a much shorter
TTL (`negative_ttl_seconds`) than a success. Without this, a
consistently-failing ticker (e.g. HUDCO before the `/historical_stats`
fallback existed) never gets cached at all, so every repeated request
within the same short window re-hits the live provider — this bounds
that to one live call per `negative_ttl_seconds` window instead.
"""

import logging

from app.cache.store import CacheStore
from app.cache.versioning import CACHE_SCHEMA_VERSION
from app.data.models import CompanyIdentifier, FinancialDataFetchResult
from app.data.service import FinancialDataService

logger = logging.getLogger(__name__)

# 1-5 minutes, per this project's own guidance on negative caching --
# short enough that a genuinely-fixed provider issue (or the
# /historical_stats fallback recovering data) is reflected quickly,
# long enough to collapse a burst of repeated requests for a known-bad
# ticker into one live call.
DEFAULT_NEGATIVE_TTL_SECONDS = 120


class CachedFinancialDataService:
    def __init__(
        self,
        inner: FinancialDataService,
        cache: CacheStore,
        provider_name: str,
        ttl_seconds: int,
        negative_ttl_seconds: int = DEFAULT_NEGATIVE_TTL_SECONDS,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._provider_name = provider_name
        self._ttl_seconds = ttl_seconds
        self._negative_ttl_seconds = negative_ttl_seconds

    def _key(self, ticker: str) -> str:
        return f"financials:{CACHE_SCHEMA_VERSION}:{self._provider_name}:{ticker.strip().upper()}"

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataFetchResult:
        key = self._key(identifier.ticker)
        hit = await self._cache.get(key)
        if hit is not None and not hit.is_expired:
            logger.info("provider_cache_hit provider=%s ticker=%s data_type=financial_statements", self._provider_name, identifier.ticker)
            return FinancialDataFetchResult.model_validate_json(hit.value)

        logger.info("provider_fetch provider=%s ticker=%s data_type=financial_statements", self._provider_name, identifier.ticker)
        result = await self._inner.get_company_financials(identifier)

        if result.status == "success":
            await self._cache.set(key, result.model_dump_json(), self._ttl_seconds)
            return result

        if hit is not None:
            cached_result = FinancialDataFetchResult.model_validate_json(hit.value)
            if cached_result.status == "success":
                # Provider failed but a (possibly expired) SUCCESSFUL
                # cached value exists -- serving it beats surfacing an
                # outage the cache could have masked. A cached hit that
                # was itself a negative-cache entry doesn't get this
                # treatment -- it falls through to refresh the negative
                # cache below instead of perpetually re-serving an old
                # failure.
                logger.info(
                    "Financial data provider failed for %s; serving cached data instead", identifier.ticker
                )
                return cached_result

        logger.info(
            "provider_fetch_failed_negative_cache provider=%s ticker=%s ttl_seconds=%d",
            self._provider_name, identifier.ticker, self._negative_ttl_seconds,
        )
        await self._cache.set(key, result.model_dump_json(), self._negative_ttl_seconds)
        return result

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
"""

import logging

from app.cache.store import CacheStore
from app.cache.versioning import CACHE_SCHEMA_VERSION
from app.data.models import CompanyIdentifier, FinancialDataFetchResult
from app.data.service import FinancialDataService

logger = logging.getLogger(__name__)


class CachedFinancialDataService:
    def __init__(
        self,
        inner: FinancialDataService,
        cache: CacheStore,
        provider_name: str,
        ttl_seconds: int,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._provider_name = provider_name
        self._ttl_seconds = ttl_seconds

    def _key(self, ticker: str) -> str:
        return f"financials:{CACHE_SCHEMA_VERSION}:{self._provider_name}:{ticker.strip().upper()}"

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataFetchResult:
        key = self._key(identifier.ticker)
        hit = await self._cache.get(key)
        if hit is not None and not hit.is_expired:
            return FinancialDataFetchResult.model_validate_json(hit.value)

        result = await self._inner.get_company_financials(identifier)

        if result.status == "success":
            await self._cache.set(key, result.model_dump_json(), self._ttl_seconds)
            return result

        if hit is not None:
            # Provider failed but a (possibly expired) cached value
            # exists -- serving it beats surfacing an outage the cache
            # could have masked.
            logger.info(
                "Financial data provider failed for %s; serving cached data instead", identifier.ticker
            )
            return FinancialDataFetchResult.model_validate_json(hit.value)
        return result

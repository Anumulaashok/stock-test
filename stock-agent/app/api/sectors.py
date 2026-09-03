"""Market Opportunity API — sector ranking built from the app's own
deterministic per-ticker scoring (see `app/sectors/service.py`).

Cached whole-response (not per-ticker) because computing it evaluates
every constituent across every sector in one call; a TTL keeps repeat
dashboard loads cheap without a second, ticker-level cache layer.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import build_sector_ranking_service
from app.cache.store import SqlCacheStore
from app.cache.versioning import CACHE_SCHEMA_VERSION
from app.core.config import Settings, get_settings
from app.data.factory import get_financial_data_provider
from app.db.base import get_db
from app.models.sectors import MarketOpportunityResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sectors"])

_CACHE_KEY = f"market_opportunity:{CACHE_SCHEMA_VERSION}"


@router.get("/sectors")
async def get_market_opportunity(
    force_refresh: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> MarketOpportunityResult:
    try:
        get_financial_data_provider(settings)
    except ValueError as exc:
        logger.warning("Sector ranking: financial data provider misconfigured: %s", exc)
        return MarketOpportunityResult(
            status="unavailable",
            generated_at="",
            warnings=[f"Financial data provider is not configured: {exc}"],
        )

    cache = SqlCacheStore(db)
    if not force_refresh:
        hit = await cache.get(_CACHE_KEY)
        if hit is not None and not hit.is_expired:
            return MarketOpportunityResult.model_validate_json(hit.value)

    service = build_sector_ranking_service(settings, db)
    result = await service.rank_sectors()

    if result.status != "unavailable":
        await cache.set(_CACHE_KEY, result.model_dump_json(), settings.sector_overview_cache_ttl_seconds)

    return result

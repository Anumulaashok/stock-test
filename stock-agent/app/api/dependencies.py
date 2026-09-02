"""Shared FastAPI dependency builders for API routers.

Extracted from `app/api/analyze.py` so `app/api/qa.py` (and any future
router that needs the same pipeline) builds services the same way
instead of duplicating provider-wiring/error-handling logic.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.service import AnalystService
from app.cache.financial_data import CachedFinancialDataService
from app.cache.market_data import CachedMarketDataService
from app.cache.store import SqlCacheStore
from app.core.config import Settings
from app.data.base import FinancialDataProvider
from app.data.service import FinancialDataService
from app.forecasting.service import ForecastingService
from app.llm.factory import get_llm_provider
from app.market.service import MarketDataService
from app.market.factory import get_market_data_provider
from app.models.analyst import AnalystError, AnalystErrorCode, AnalystResult
from app.pipeline.service import AnalysisPipelineService
from app.research.factory import get_research_provider
from app.research.service import ResearchService
from app.financial.service import FinancialAnalysisService
from app.scoring.service import ScoringService
from app.valuation.service import ValuationService

logger = logging.getLogger(__name__)


class MisconfiguredAnalystService:
    """Stand-in for `AnalystService` when no LLM provider can be built.

    Lets the deterministic stages complete normally (`status="partial"`)
    instead of failing the whole request over an LLM configuration issue.
    """

    def __init__(self, message: str) -> None:
        self._message = message

    async def analyze(self, *_args, **_kwargs) -> AnalystResult:
        return AnalystResult(
            status="error",
            error=AnalystError(code=AnalystErrorCode.LLM_UNAVAILABLE, message=self._message),
        )


def build_research_service(settings: Settings) -> ResearchService | None:
    """Returns `None` (not an error) when unconfigured — research is
    always optional; a caller who didn't opt in never even calls this."""
    try:
        provider = get_research_provider(settings)
    except ValueError as exc:
        logger.info("Research provider not configured: %s", exc)
        return None
    return ResearchService(
        provider,
        default_date_range_days=settings.research_default_days,
        default_max_results=settings.research_default_max_results,
        stale_after_days=settings.research_stale_after_days,
    )


def build_market_data_service(settings: Settings) -> MarketDataService | None:
    """Returns `None` (not an error) when unconfigured -- a live price is
    a nice-to-have for ticker analysis, not a requirement."""
    try:
        provider = get_market_data_provider(settings)
    except ValueError as exc:
        logger.info("Market data provider not configured: %s", exc)
        return None
    return MarketDataService(
        provider, default_recent_prices_limit=settings.market_data_recent_prices_limit
    )


def build_cached_financial_data_service(
    settings: Settings, provider: FinancialDataProvider, db: AsyncSession
) -> CachedFinancialDataService:
    """Wraps `FinancialDataService` with a TTL cache keyed on
    ticker+provider (see `app/cache/financial_data.py`) so repeated
    requests for the same ticker within the TTL -- notably
    `/analyze/ticker` and `/qa/ticker` fetching the same data
    independently -- don't hit the external provider twice."""
    return CachedFinancialDataService(
        FinancialDataService(provider),
        SqlCacheStore(db),
        provider_name=settings.financial_data_provider,
        ttl_seconds=settings.financial_data_cache_ttl_seconds,
    )


def build_cached_market_data_service(
    settings: Settings, db: AsyncSession
) -> CachedMarketDataService | None:
    """Returns `None` when unconfigured, mirroring
    `build_market_data_service`. Uses a much shorter TTL than the
    financial-data cache since a quote is live data."""
    inner = build_market_data_service(settings)
    if inner is None:
        return None
    return CachedMarketDataService(
        inner,
        SqlCacheStore(db),
        provider_name=settings.market_data_provider,
        ttl_seconds=settings.market_data_cache_ttl_seconds,
    )


def build_pipeline(settings: Settings) -> AnalysisPipelineService:
    try:
        provider = get_llm_provider(settings)
        analyst_service = AnalystService(
            provider, max_response_tokens=settings.analyst_max_response_tokens
        )
    except ValueError as exc:
        logger.warning("Analyst LLM provider misconfigured: %s", exc)
        analyst_service = MisconfiguredAnalystService(str(exc))

    return AnalysisPipelineService(
        financial_service=FinancialAnalysisService(),
        valuation_service=ValuationService(),
        scoring_service=ScoringService(),
        analyst_service=analyst_service,
        research_service=build_research_service(settings),
        forecasting_service=ForecastingService(),
    )

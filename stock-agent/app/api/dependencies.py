"""Shared FastAPI dependency builders for API routers.

Extracted from `app/api/analyze.py` so `app/api/qa.py` (and any future
router that needs the same pipeline) builds services the same way
instead of duplicating provider-wiring/error-handling logic.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.service import AnalystService
from app.application.service import AnalysisApplicationService
from app.cache.financial_data import CachedFinancialDataService
from app.cache.market_data import CachedMarketDataService
from app.cache.store import SqlCacheStore
from app.core.config import Settings
from app.data.base import FinancialDataProvider
from app.data.factory import get_financial_data_provider
from app.data.providers.screener_client import ScreenerClient
from app.data.service import FinancialDataService
from app.sources.capabilities import Category
from app.sources.historical import ScreenerHistoricalProvider
from app.sources.manager import DataSourceManager
from app.sources.registry import (
    FMP,
    INDIANAPI,
    LOCAL,
    SCREENER,
    YFINANCE,
    SourceRegistry,
)
from app.forecasting.service import ForecastingService
from app.llm.factory import get_llm_provider
from app.market.service import MarketDataService
from app.market.factory import get_market_data_provider
from app.models.analyst import AnalystError, AnalystErrorCode, AnalystResult
from app.news.client import NewsClient
from app.pipeline.service import AnalysisPipelineService
from app.research.factory import get_research_provider
from app.research.service import ResearchService
from app.financial.service import FinancialAnalysisService
from app.scoring.service import ScoringService
from app.sectors.service import SectorRankingService
from app.snapshot.service import ResearchSnapshotService
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
        negative_ttl_seconds=settings.financial_data_negative_cache_ttl_seconds,
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


def _configured_sources(settings: Settings, *, screener_cookie: str | None) -> dict[str, bool]:
    """A provider is "configured" only if the credentials it actually
    needs are present. yfinance needs none; Screener needs a cookie only
    for search, but a cookie is what makes it usable in practice."""
    return {
        SCREENER: bool(screener_cookie or settings.screener_session_cookie),
        INDIANAPI: bool(settings.indian_api_key),
        FMP: bool(settings.fmp_api_key),
        YFINANCE: True,
        LOCAL: True,
    }


def build_source_registry(settings: Settings, *, screener_cookie: str | None = None) -> SourceRegistry:
    return SourceRegistry(
        chains={
            Category.FINANCIALS: settings.financial_provider_chain(),
            Category.MARKET_QUOTE: settings.market_provider_chain(),
            Category.HISTORICAL_PRICE: settings.historical_price_chain(),
            Category.COMPANY_SEARCH: settings.company_search_chain(),
        },
        configured=_configured_sources(settings, screener_cookie=screener_cookie),
    )


def _build_financial_fetchers(
    settings: Settings, registry: SourceRegistry, db: AsyncSession
) -> dict[str, object]:
    """One cached fetcher per provider in the chain. The cache key already
    includes the provider name, so each source caches independently and a
    fallback never serves the primary's cached payload."""
    fetchers: dict[str, object] = {}
    for name in registry.chain_for(Category.FINANCIALS):
        try:
            provider = get_financial_data_provider(settings, provider_name=name)
        except ValueError as exc:
            logger.info("Financial provider %s not configured: %s", name, exc)
            continue
        fetchers[name] = CachedFinancialDataService(
            FinancialDataService(provider),
            SqlCacheStore(db),
            provider_name=name,
            ttl_seconds=settings.financial_data_cache_ttl_seconds,
            negative_ttl_seconds=settings.financial_data_negative_cache_ttl_seconds,
        )
    return fetchers


def _build_market_fetchers(
    settings: Settings, registry: SourceRegistry, db: AsyncSession
) -> dict[str, object]:
    fetchers: dict[str, object] = {}
    for name in registry.chain_for(Category.MARKET_QUOTE):
        try:
            provider = get_market_data_provider(settings, provider_name=name)
        except ValueError as exc:
            logger.info("Market provider %s not configured: %s", name, exc)
            continue
        fetchers[name] = CachedMarketDataService(
            MarketDataService(
                provider, default_recent_prices_limit=settings.market_data_recent_prices_limit
            ),
            SqlCacheStore(db),
            provider_name=name,
            ttl_seconds=settings.market_data_cache_ttl_seconds,
        )
    return fetchers


def build_data_source_manager(
    settings: Settings, db: AsyncSession, *, screener_cookie: str | None = None
) -> DataSourceManager:
    """The single provider-selection path. Built per request, so its
    per-call provenance bookkeeping is never shared across requests."""
    registry = build_source_registry(settings, screener_cookie=screener_cookie)
    cookie = screener_cookie or settings.screener_session_cookie
    historical = None
    if cookie and SCREENER in registry.chain_for(Category.HISTORICAL_PRICE):
        historical = ScreenerHistoricalProvider(
            ScreenerClient(
                base_url=settings.screener_base_url,
                session_cookie=cookie,
                timeout_seconds=settings.screener_timeout_seconds,
            )
        )
    return DataSourceManager(
        registry=registry,
        financial_providers=_build_financial_fetchers(settings, registry, db),
        market_providers=_build_market_fetchers(settings, registry, db),
        historical_provider=historical,
        db=db,
        recent_prices_limit=settings.market_data_recent_prices_limit,
    )


def build_analyst_service(settings: Settings):
    """Shared by `build_pipeline` and `build_research_snapshot_service` so
    both build the analyst LLM provider the same way instead of
    duplicating the misconfiguration fallback."""
    try:
        provider = get_llm_provider(settings)
        return AnalystService(provider, max_response_tokens=settings.analyst_max_response_tokens)
    except ValueError as exc:
        logger.warning("Analyst LLM provider misconfigured: %s", exc)
        return MisconfiguredAnalystService(str(exc))


def build_pipeline(settings: Settings) -> AnalysisPipelineService:
    return AnalysisPipelineService(
        financial_service=FinancialAnalysisService(),
        valuation_service=ValuationService(),
        scoring_service=ScoringService(),
        analyst_service=build_analyst_service(settings),
        research_service=build_research_service(settings),
        forecasting_service=ForecastingService(),
    )


def build_news_client(settings: Settings) -> NewsClient | None:
    """Returns `None` (not an error) when neither provider is configured
    -- news is always an optional modifier, never a requirement."""
    if not settings.newsdata_api_key and not settings.newsapi_api_key:
        return None
    return NewsClient(
        newsdata_api_key=settings.newsdata_api_key,
        newsdata_base_url=settings.newsdata_base_url,
        newsapi_api_key=settings.newsapi_api_key,
        newsapi_base_url=settings.newsapi_base_url,
        connect_timeout_seconds=settings.news_connect_timeout_seconds,
        timeout_seconds=settings.news_timeout_seconds,
    )


def build_sector_ranking_service(settings: Settings, db: AsyncSession) -> SectorRankingService:
    """Reuses the exact same `AnalysisApplicationService` construction
    `/analyze/ticker` and `/qa/ticker` use, so a sector's constituent
    scores are computed identically (same cache, same provider) to a
    direct single-ticker lookup -- never a second, divergent scoring path."""
    manager = build_data_source_manager(settings, db)
    application_service = AnalysisApplicationService(manager, build_pipeline(settings), manager)
    return SectorRankingService(application_service, news_client=build_news_client(settings))


def build_research_snapshot_service(settings: Settings, db: AsyncSession) -> ResearchSnapshotService:
    """The persistent-snapshot orchestrator behind `POST
    /api/v1/research/ticker` -- wraps the same `AnalysisPipelineService`
    and `AnalystService` construction `build_pipeline` uses, so the
    deterministic/LLM behavior is identical whether a request goes
    through the plain (never-persisted) `/analyze/ticker` or the
    persisted `/research/ticker` endpoint.

    Raises `ValueError` (uncaught) when the financial data provider is
    misconfigured -- callers must check `get_financial_data_provider`
    themselves first, exactly as `app/api/analyze.py`'s
    `analyze_ticker` route already does, so a missing API key produces
    the same clear `CombinedAnalysisResult(status="failed", ...)`
    response either endpoint would give."""
    # Still raises ValueError when nothing can serve financials, matching
    # the previous contract callers pre-check against.
    get_financial_data_provider(settings)
    manager = build_data_source_manager(settings, db)
    application_service = AnalysisApplicationService(manager, build_pipeline(settings), manager)

    return ResearchSnapshotService(
        application_service=application_service,
        financial_data_service=manager,
        market_data_service=manager,
        analyst_service=build_analyst_service(settings),
        financial_data_provider_name=settings.financial_data_provider,
        market_data_provider_name=settings.market_data_provider,
        llm_provider_name=settings.llm_provider,
        model_version=settings.local_llm_model or "unknown",
    )

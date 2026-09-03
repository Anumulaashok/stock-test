"""Historical price store API.

Endpoints here, in the order a user actually walks through them:
- `POST /screener-mappings/import` -- paste one of Screener's own
  company-search JSON results (a list of `{id, name, url}` objects) to
  bulk-register ticker -> Screener-company-id mappings, reusable from
  then on. Never fetches anything from Screener itself -- pure local
  bookkeeping over data the caller already has.
- `GET /screener-mappings?q=...` -- autocompletes a ticker input against
  those stored mappings.
- `POST /{ticker}/historical/import` -- a one-time, manually-triggered
  bulk backfill of `daily_price_history` from Screener.in (see
  `app.data.screener_import_service`). `screener_company_id` may be
  omitted once a mapping is already registered for the ticker. Never
  called automatically.
- `GET /{ticker}/forecast-accuracy` -- evaluates any newly-due forecasts
  (see `app.forecasting.accuracy_service`) then returns the full
  predicted-vs-actual history for the ticker.

All of this is separate from `app/market/` (the live `MarketDataProvider`
abstraction, e.g. yfinance) -- this router only ever reads/writes the
app's own persisted `daily_price_history`/`screener_company_mappings`/
`prediction_outcomes` tables.
"""

import asyncio
import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import build_market_data_service, build_source_registry
from app.core.config import Settings, get_settings
from app.core.runtime_settings import (
    SCREENER_SESSION_COOKIE_KEY,
    clear_runtime_setting,
    get_runtime_setting,
    resolve_screener_session_cookie,
    set_runtime_setting,
)
from app.data.mappers.screener import map_screener_company_list
from app.data.providers.screener_client import ScreenerClient, ScreenerImportError, ScreenerMappingNotFoundError
from app.data.daily_price_history_service import upsert_daily_price
from app.data.screener_import_service import ScreenerImportService
from app.db.base import get_db
from app.db.models import ForecastSnapshotRow, PredictionOutcomeRow
from app.forecasting.accuracy_service import ForecastAccuracyService
from app.market.factory import get_market_data_provider
from app.sources.capabilities import Category
from app.sources.identity import CompanyIdentityResolver
from app.sources.provenance import SourceStatus
from app.sources.registry import SCREENER, SOURCE_DEFINITIONS
from app.sources.screener_health import validate_cookie
from app.models.market_history import (
    CompanySearchResponse,
    CompanySearchResult,
    DataSourceStatus,
    DataSourceStatusResponse,
    ForecastAccuracyEntry,
    ForecastAccuracySummary,
    IndexQuote,
    IndexQuotesResponse,
    ScreenerCompanyListImportRequest,
    ScreenerCompanyListImportResult,
    ScreenerCookieRequest,
    ScreenerCookieStatus,
    ScreenerImportRequest,
    ScreenerImportResult,
    ScreenerMappingSummary,
)
from app.search.service import StockSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market", tags=["market-history"])


def _normalize(ticker: str) -> str:
    return ticker.strip().upper()


async def _build_service(settings: Settings, db: AsyncSession) -> ScreenerImportService:
    cookie = await resolve_screener_session_cookie(db, settings.screener_session_cookie)
    client = ScreenerClient(
        base_url=settings.screener_base_url,
        session_cookie=cookie,
        timeout_seconds=settings.screener_timeout_seconds,
    )
    return ScreenerImportService(client)


def _cookie_status(health, source: str | None) -> ScreenerCookieStatus:
    return ScreenerCookieStatus(
        configured=health.configured,
        source=source,
        status=health.status.value,
        last_validated_at=health.last_validated_at,
        last_success_at=health.last_success_at,
        last_error_at=health.last_error_at,
        detail=health.detail,
    )


async def _validate_cookie(settings: Settings, cookie: str, source: str) -> ScreenerCookieStatus:
    client = ScreenerClient(
        base_url=settings.screener_base_url,
        session_cookie=cookie,
        timeout_seconds=settings.screener_timeout_seconds,
    )
    return _cookie_status(await validate_cookie(client, source=source), source)


@router.get("/settings/screener-cookie")
async def get_screener_cookie_status(
    validate: bool = Query(
        default=False,
        description="Check the stored cookie against Screener. Off by default so page loads stay cheap.",
    ),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> ScreenerCookieStatus:
    """Never returns the cookie value itself -- only whether one is
    configured, which layer supplied it, and its last known health."""
    runtime_value = await get_runtime_setting(db, SCREENER_SESSION_COOKIE_KEY)
    cookie = runtime_value or settings.screener_session_cookie
    source = "runtime" if runtime_value else ("env" if settings.screener_session_cookie else None)

    if not cookie:
        return ScreenerCookieStatus(
            configured=False, source=None, status=SourceStatus.NOT_CONFIGURED.value
        )
    if validate:
        return await _validate_cookie(settings, cookie, source)
    return ScreenerCookieStatus(configured=True, source=source, status="UNKNOWN")


@router.put("/settings/screener-cookie")
async def set_screener_cookie(
    request: ScreenerCookieRequest,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> ScreenerCookieStatus:
    """Stores the cookie in the DB (`AppSettingRow`), effective
    immediately for every subsequent request -- no server restart,
    unlike the `SCREENER_SESSION_COOKIE` env var. The value itself is
    never echoed back or logged.

    The cookie is stored first and validated second, so a Screener outage
    never prevents saving a cookie that may well be valid."""
    cookie = request.session_cookie.strip()
    await set_runtime_setting(db, SCREENER_SESSION_COOKIE_KEY, cookie)
    return await _validate_cookie(settings, cookie, "runtime")


@router.get("/data-sources/status")
async def get_data_source_status(
    validate_screener: bool = Query(
        default=False,
        description="Also check the Screener cookie live. Off by default: this endpoint is "
        "on the Intelligence page's hot path, and validation is a real network call.",
    ),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> DataSourceStatusResponse:
    """Which sources are configured, what each is actually capable of,
    which categories each owns, and how each is currently behaving.

    Screener's health reflects its last known state (from the cookie
    endpoint or a previous `validate_screener=true` call here) unless
    the caller opts into a live check -- probing Screener on every page
    load would make an ordinarily cheap status check as expensive as the
    thing it is checking. No secrets are returned.
    """
    runtime_value = await get_runtime_setting(db, SCREENER_SESSION_COOKIE_KEY)
    cookie = runtime_value or settings.screener_session_cookie
    registry = build_source_registry(settings, screener_cookie=cookie)

    screener_status: str | None = None
    if cookie and validate_screener:
        client = ScreenerClient(
            base_url=settings.screener_base_url,
            session_cookie=cookie,
            timeout_seconds=settings.screener_timeout_seconds,
        )
        screener_status = (await validate_cookie(client, source=None)).status.value
    elif cookie:
        screener_status = SourceStatus.UNKNOWN.value

    sources: list[DataSourceStatus] = []
    for name, definition in SOURCE_DEFINITIONS.items():
        health = registry.health(name)
        primary_for = [c.value for c in Category if registry.role_of(name, c) == "primary"]
        fallback_for = [c.value for c in Category if registry.role_of(name, c) == "fallback"]
        if not health.configured and not primary_for and not fallback_for:
            continue
        status_value = (
            screener_status
            if name == SCREENER and screener_status is not None
            else health.status.value
        )
        sources.append(
            DataSourceStatus(
                name=definition.name,
                label=definition.label,
                type=definition.kind,
                configured=health.configured,
                status=status_value,
                capabilities=sorted(c.value for c in definition.capabilities),
                primary_for=primary_for,
                fallback_for=fallback_for,
                last_success_at=health.last_success_at.isoformat() if health.last_success_at else None,
                last_error_at=health.last_error_at.isoformat() if health.last_error_at else None,
                limitation=definition.limitation,
            )
        )
    return DataSourceStatusResponse(sources=sources)


@router.delete("/settings/screener-cookie")
async def clear_screener_cookie(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> ScreenerCookieStatus:
    """Clears only the runtime override -- if `SCREENER_SESSION_COOKIE`
    is also set as an env var, that one still applies afterward."""
    await clear_runtime_setting(db, SCREENER_SESSION_COOKIE_KEY)
    if settings.screener_session_cookie:
        return ScreenerCookieStatus(configured=True, source="env")
    return ScreenerCookieStatus(configured=False, source=None)


# --- Nifty 50 / Sensex --------------------------------------------------------------
# Real index levels via the same configured MarketDataProvider (yfinance)
# every ticker quote already goes through -- yfinance's `^NSEI`/`^BSESN`
# symbols were live-verified to return real data (2026-09-03). No new
# provider, no fabricated fallback: a quote that fails is reported
# status="unavailable", same as any other missing market-data field.

_INDICES = [("Nifty 50", "^NSEI"), ("Sensex", "^BSESN")]


@router.get("/indices")
async def get_index_quotes(settings: Settings = Depends(get_settings)) -> IndexQuotesResponse:
    service = build_market_data_service(settings)
    if service is None:
        return IndexQuotesResponse(
            indices=[
                IndexQuote(name=name, symbol=symbol, status="unavailable", source="none", warning="No market data provider configured.")
                for name, symbol in _INDICES
            ]
        )

    results = await asyncio.gather(*(service.get_quote(symbol) for _, symbol in _INDICES))

    quotes: list[IndexQuote] = []
    for (name, symbol), result in zip(_INDICES, results):
        if result.status != "success" or result.snapshot is None or result.snapshot.quote is None:
            detail = result.error.message if result.error else "no snapshot was returned"
            quotes.append(
                IndexQuote(name=name, symbol=symbol, status="unavailable", source=settings.market_data_provider, warning=detail)
            )
            continue
        quote = result.snapshot.quote
        quotes.append(
            IndexQuote(
                name=name, symbol=symbol,
                status="available" if quote.current_price is not None else "unavailable",
                current_price=quote.current_price, previous_close=quote.previous_close,
                change=quote.change, change_percent=quote.change_percent,
                source=quote.source, freshness=quote.freshness.value,
            )
        )
    return IndexQuotesResponse(indices=quotes)


@router.post("/screener-mappings/import")
async def import_screener_company_mappings(
    request: ScreenerCompanyListImportRequest,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> ScreenerCompanyListImportResult:
    entries = map_screener_company_list(request.companies)
    registered = await (await _build_service(settings, db)).register_company_mappings(db, entries)
    return ScreenerCompanyListImportResult(registered=registered, skipped=len(request.companies) - registered)


@router.get("/screener-mappings")
async def search_screener_company_mappings(
    q: str = Query(min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> list[ScreenerMappingSummary]:
    rows = await (await _build_service(settings, db)).search_mappings(db, q, limit=limit)
    return [
        ScreenerMappingSummary(
            ticker=row.ticker, company_name=row.company_name,
            screener_company_id=row.screener_company_id, consolidated=row.consolidated,
        )
        for row in rows
    ]


_local_search_service = StockSearchService()


@router.get("/company-search")
async def search_companies(
    q: str = Query(min_length=1),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> CompanySearchResponse:
    """Company-name search used to resolve a Screener id for a ticker.
    Tries Screener.in's own live search first when a session cookie is
    configured (runtime setting or `SCREENER_SESSION_COOKIE` env var) --
    results are auto-registered as mappings, source="screener". Falls
    back to this app's local static NSE directory (the same dataset
    `GET /api/v1/search` uses, source="local_directory") when no cookie
    is set or the live search fails -- always with an honest `source`,
    never blended."""
    cookie = await resolve_screener_session_cookie(db, settings.screener_session_cookie)
    if cookie:
        try:
            entries = await (await _build_service(settings, db)).search_live_and_register(db, q)
        except ScreenerImportError as exc:
            logger.warning("screener_live_search_failed q=%s error=%s -- falling back to local directory", q, exc)
        else:
            return CompanySearchResponse(
                query=q, source="screener", source_detail="Live Screener.in search (session cookie configured).",
                results=[
                    CompanySearchResult(
                        ticker=entry["ticker"], company_name=entry.get("company_name"),
                        screener_company_id=entry["screener_company_id"], source="screener",
                    )
                    for entry in entries
                ],
            )

    local_results = _local_search_service.search(q, limit=10)
    return CompanySearchResponse(
        query=q, source="local_directory",
        source_detail=(
            "No Screener session cookie configured -- local static NSE directory used instead."
            if not cookie
            else "Screener.in live search failed -- fell back to the local static NSE directory."
        ),
        results=[
            CompanySearchResult(
                ticker=r.symbol, company_name=r.name, screener_company_id=None, source="local_directory"
            )
            for r in local_results
        ],
    )


@router.post("/{ticker}/historical/import")
async def import_historical_prices(
    ticker: str,
    request: ScreenerImportRequest,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> ScreenerImportResult:
    """A Screener failure is classified and falls back to the configured
    historical chain rather than aborting with a 502. A missing mapping is
    still a 400 -- that is a client-input problem the caller must fix, and
    no fallback can substitute for it."""
    ticker = _normalize(ticker)
    service = await _build_service(settings, db)
    try:
        rows_imported, earliest_date, latest_date = await service.import_historical_prices(
            db, ticker, request.screener_company_id, days=request.days, consolidated=request.consolidated
        )
    except ScreenerMappingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ScreenerImportError as exc:
        logger.warning(
            "screener_import_failed ticker=%s status=%s", ticker, exc.status.value
        )
        return await _import_from_fallback(settings, db, ticker, exc)

    return ScreenerImportResult(
        ticker=ticker,
        rows_imported=rows_imported,
        earliest_date=earliest_date,
        latest_date=latest_date,
        source=SCREENER,
        status=SourceStatus.SUCCESS.value,
    )


async def _import_from_fallback(
    settings: Settings, db: AsyncSession, ticker: str, cause: ScreenerImportError
) -> ScreenerImportResult:
    """Try each non-Screener provider in the historical chain. Returns a
    structured unavailable result when they all fail -- never a 502, so a
    failed import degrades rather than breaking the caller."""
    registry = build_source_registry(settings, screener_cookie=None)
    chain = [n for n in registry.declared_chain_for(Category.HISTORICAL_PRICE) if n != SCREENER]
    identity = CompanyIdentityResolver().resolve_offline(ticker)
    limit = settings.market_data_recent_prices_limit

    for name in chain:
        try:
            provider = get_market_data_provider(settings, provider_name=name)
            symbol = identity.yfinance_symbol if name != SCREENER else ticker
            points = await provider.get_recent_prices(symbol or ticker, limit)
        except Exception as exc:  # noqa: BLE001 - try the next provider in the chain
            logger.warning(
                "historical_import_fallback_failed ticker=%s provider=%s error=%s", ticker, name, exc
            )
            continue
        if not points:
            continue

        imported = 0
        for point in points:
            day = _parse_day(point.timestamp)
            if day is None or point.close is None:
                continue
            await upsert_daily_price(
                db, ticker, day, source=f"{name}_daily", price=point.close, volume=point.volume
            )
            imported += 1
        await db.commit()

        days = sorted(d for d in (_parse_day(p.timestamp) for p in points) if d is not None)
        logger.info(
            "historical_import_fallback ticker=%s provider=%s rows=%d fallback=true",
            ticker, name, imported,
        )
        return ScreenerImportResult(
            ticker=ticker,
            rows_imported=imported,
            earliest_date=days[0].isoformat() if days else None,
            latest_date=days[-1].isoformat() if days else None,
            source=name,
            status=SourceStatus.FALLBACK.value,
            fallback_used=True,
            detail=f"Screener unavailable ({cause.status.value}); imported from {name} instead.",
        )

    return ScreenerImportResult(
        ticker=ticker,
        rows_imported=0,
        source=SCREENER,
        status=SourceStatus.UNAVAILABLE.value,
        fallback_used=bool(chain),
        detail=(
            f"Screener unavailable ({cause.status.value}) and no configured fallback "
            "could supply historical prices."
        ),
    )


def _parse_day(timestamp: str) -> date | None:
    try:
        return date.fromisoformat(timestamp[:10])
    except (TypeError, ValueError):
        return None


@router.get("/{ticker}/forecast-accuracy")
async def get_forecast_accuracy(
    ticker: str,
    db: AsyncSession = Depends(get_db),
) -> ForecastAccuracySummary:
    ticker = _normalize(ticker)
    newly_evaluated = await ForecastAccuracyService().evaluate_ticker(db, ticker)

    stmt = (
        select(PredictionOutcomeRow, ForecastSnapshotRow)
        .join(ForecastSnapshotRow, PredictionOutcomeRow.forecast_snapshot_id == ForecastSnapshotRow.id)
        .where(PredictionOutcomeRow.ticker == ticker)
        .order_by(PredictionOutcomeRow.target_date.desc())
    )
    rows = (await db.execute(stmt)).all()

    entries = [
        ForecastAccuracyEntry(
            horizon=forecast.horizon,
            method=forecast.method,
            prediction_date=forecast.prediction_date.isoformat(),
            target_date=outcome.target_date.isoformat(),
            predicted_price=outcome.predicted_price,
            actual_price=outcome.actual_price,
            absolute_error=outcome.absolute_error,
            percentage_error=outcome.percentage_error,
            direction_correct=outcome.direction_correct,
        )
        for outcome, forecast in rows
    ]

    percentage_errors = [e.percentage_error for e in entries if e.percentage_error is not None]
    absolute_errors = [e.absolute_error for e in entries if e.absolute_error is not None]
    directions = [e.direction_correct for e in entries if e.direction_correct is not None]

    return ForecastAccuracySummary(
        ticker=ticker,
        evaluated_count=len(entries),
        newly_evaluated=newly_evaluated,
        mean_absolute_error=(sum(absolute_errors) / len(absolute_errors)) if absolute_errors else None,
        mean_percentage_error=(sum(percentage_errors) / len(percentage_errors)) if percentage_errors else None,
        direction_accuracy=(
            Decimal(sum(1 for d in directions if d)) / Decimal(len(directions)) if directions else None
        ),
        entries=entries,
    )

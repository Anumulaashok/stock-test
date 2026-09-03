"""The one place that decides which source answers a request.

`DataSourceManager` satisfies both `app.data.service.FinancialDataFetcher`
and `app.market.service.MarketDataFetcher`, so it drops into the existing
injection points without any caller changing: research, sectors, and
portfolio keep calling the same two methods they always have.

Fallback is per-category, not per-metric. A provider is attempted for a
category only if it declares a capability that category accepts, so
Screener is never asked for a financial statement it cannot produce.
"""

import logging
import time
from dataclasses import dataclass

from app.data.models import (
    CompanyIdentifier,
    FinancialDataError,
    FinancialDataErrorCode,
    FinancialDataFetchResult,
)
from app.models.market import MarketDataError, MarketDataErrorCode, MarketSnapshotResult
from app.sources.capabilities import Category
from app.sources.identity import CompanyIdentity, CompanyIdentityResolver
from app.sources.provenance import (
    FALLBACK_TRIGGERING,
    SourceAttempt,
    SourceStatus,
)
from app.sources.registry import SourceRegistry

logger = logging.getLogger(__name__)


@dataclass
class ProviderBinding:
    """One provider's concrete fetcher for one category."""

    name: str
    fetcher: object


def _financial_status(result: FinancialDataFetchResult) -> SourceStatus:
    """Map a provider's own error code onto a source status. The
    distinction that matters: a company that genuinely doesn't exist is
    not a provider failure, so it must not trigger a pointless fallback
    to a provider that will also not find it."""
    if result.status == "success" and result.data is not None:
        return SourceStatus.SUCCESS
    code = result.error.code if result.error else None
    if code == FinancialDataErrorCode.AUTHENTICATION_FAILED:
        return SourceStatus.AUTH_EXPIRED
    if code == FinancialDataErrorCode.RATE_LIMITED:
        return SourceStatus.RATE_LIMITED
    if code == FinancialDataErrorCode.PROVIDER_UNAVAILABLE:
        return SourceStatus.UNREACHABLE
    if code == FinancialDataErrorCode.COMPANY_NOT_FOUND:
        return SourceStatus.UNAVAILABLE
    return SourceStatus.INVALID


def _market_status(result: MarketSnapshotResult) -> SourceStatus:
    if result.status == "success" and result.snapshot is not None:
        return SourceStatus.SUCCESS
    code = result.error.code if result.error else None
    if code == MarketDataErrorCode.AUTHENTICATION_FAILED:
        return SourceStatus.AUTH_EXPIRED
    if code == MarketDataErrorCode.RATE_LIMITED:
        return SourceStatus.RATE_LIMITED
    if code == MarketDataErrorCode.PROVIDER_UNAVAILABLE:
        return SourceStatus.UNREACHABLE
    if code == MarketDataErrorCode.TICKER_NOT_FOUND:
        return SourceStatus.UNAVAILABLE
    return SourceStatus.INVALID


class DataSourceManager:
    def __init__(
        self,
        *,
        registry: SourceRegistry,
        financial_providers: dict[str, object],
        market_providers: dict[str, object],
        identity_resolver: CompanyIdentityResolver | None = None,
        historical_provider: object | None = None,
        db: object | None = None,
        recent_prices_limit: int = 210,
    ) -> None:
        self._registry = registry
        self._financial_providers = financial_providers
        self._market_providers = market_providers
        self._identity = identity_resolver or CompanyIdentityResolver()
        # Optional: when Screener is the historical primary and can serve
        # this ticker, its series replaces the market provider's.
        self._historical_provider = historical_provider
        self._db = db
        self._recent_prices_limit = recent_prices_limit
        # Per-request record of which source served which category, read
        # back by the snapshot layer so provenance reaches the API.
        self.last_attempts: dict[str, list[SourceAttempt]] = {}

    # --- provenance bookkeeping --------------------------------------------

    def _record(self, category: Category, attempts: list[SourceAttempt]) -> None:
        self.last_attempts[category.value] = attempts

    def resolved_source(self, category: Category) -> str | None:
        """Which provider actually served the category on the last call."""
        for attempt in self.last_attempts.get(category.value, []):
            if attempt.status == SourceStatus.SUCCESS:
                return attempt.provider
        return None

    def used_fallback(self, category: Category) -> bool:
        attempts = self.last_attempts.get(category.value, [])
        for index, attempt in enumerate(attempts):
            if attempt.status == SourceStatus.SUCCESS:
                return index > 0
        return False

    def provenance_snapshot(self) -> dict[str, dict]:
        """Capture which source served each category right now.

        `last_attempts` is overwritten by each call, and one research run
        fetches the market snapshot twice (raw capture, then again inside
        `analyze_by_ticker`). Callers that need provenance must snapshot
        it immediately after their own call rather than reading it back
        later, or they record the wrong call's attempts."""
        return {
            category: {
                "source": next(
                    (a.provider for a in attempts if a.status == SourceStatus.SUCCESS), None
                ),
                "fallback_used": next(
                    (i > 0 for i, a in enumerate(attempts) if a.status == SourceStatus.SUCCESS),
                    False,
                ),
                "attempts": [a.describe() for a in attempts],
            }
            for category, attempts in self.last_attempts.items()
        }

    def _log(self, category: Category, ticker: str, attempt: SourceAttempt, fallback: bool) -> None:
        logger.info(
            "source_call ticker=%s category=%s provider=%s status=%s duration_ms=%s fallback=%s",
            ticker,
            category.value,
            attempt.provider,
            attempt.status.value,
            attempt.duration_ms,
            str(fallback).lower(),
        )

    # --- financial data (FinancialDataFetcher) ------------------------------

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataFetchResult:
        identity = self._identity.resolve_offline(identifier.ticker)
        chain = self._registry.chain_for(Category.FINANCIALS)
        attempts: list[SourceAttempt] = []
        # The primary's verdict is the informative one to report when the
        # whole chain fails -- "company not found" from the authoritative
        # source beats "rate limited" from the last fallback tried.
        primary_result: FinancialDataFetchResult | None = None

        for name in chain:
            fetcher = self._financial_providers.get(name)
            if fetcher is None:
                continue
            started = time.monotonic()
            try:
                result = await fetcher.get_company_financials(
                    CompanyIdentifier(ticker=identity.canonical_ticker)
                )
                status = _financial_status(result)
            except Exception as exc:  # noqa: BLE001 - a provider crash must not end the chain
                status = SourceStatus.ERROR
                result = FinancialDataFetchResult(
                    status="error",
                    error=FinancialDataError(
                        code=FinancialDataErrorCode.PROVIDER_UNAVAILABLE, message=str(exc)
                    ),
                )

            attempt = SourceAttempt(
                provider=name,
                status=status,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            attempts.append(attempt)
            self._log(Category.FINANCIALS, identity.canonical_ticker, attempt, len(attempts) > 1)

            if status == SourceStatus.SUCCESS:
                self._registry.health(name).record_success()
                self._record(Category.FINANCIALS, attempts)
                return result

            self._registry.health(name).record_failure(status, attempt.detail)
            if primary_result is None:
                primary_result = result
            if status not in FALLBACK_TRIGGERING:
                break

        self._record(Category.FINANCIALS, attempts)
        if primary_result is not None:
            return primary_result
        return FinancialDataFetchResult(
            status="error",
            error=FinancialDataError(
                code=FinancialDataErrorCode.PROVIDER_UNAVAILABLE,
                message=(
                    "No financial data provider is configured and capable of supplying "
                    "financial statements."
                ),
            ),
        )

    # --- market data (MarketDataFetcher) ------------------------------------

    async def get_snapshot(
        self, ticker: str, include_recent_prices: bool = True
    ) -> MarketSnapshotResult:
        identity = self._identity.resolve_offline(ticker)
        chain = self._registry.chain_for(Category.MARKET_QUOTE)
        attempts: list[SourceAttempt] = []
        primary_result: MarketSnapshotResult | None = None

        for name in chain:
            fetcher = self._market_providers.get(name)
            if fetcher is None:
                continue
            symbol = self._provider_symbol(name, identity)
            started = time.monotonic()
            try:
                result = await fetcher.get_snapshot(
                    symbol, include_recent_prices=include_recent_prices
                )
                status = _market_status(result)
            except Exception as exc:  # noqa: BLE001 - a provider crash must not end the chain
                status = SourceStatus.ERROR
                result = MarketSnapshotResult(
                    status="error",
                    error=MarketDataError(
                        code=MarketDataErrorCode.PROVIDER_UNAVAILABLE, message=str(exc)
                    ),
                )

            attempt = SourceAttempt(
                provider=name,
                status=status,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            attempts.append(attempt)
            self._log(Category.MARKET_QUOTE, identity.canonical_ticker, attempt, len(attempts) > 1)

            if status == SourceStatus.SUCCESS:
                self._registry.health(name).record_success()
                self._record(Category.MARKET_QUOTE, attempts)
                if include_recent_prices:
                    await self._apply_historical_primary(identity, result, market_source=name)
                return result

            self._registry.health(name).record_failure(status, attempt.detail)
            if primary_result is None:
                primary_result = result

        self._record(Category.MARKET_QUOTE, attempts)
        if primary_result is not None:
            return primary_result
        return MarketSnapshotResult(
            status="error",
            error=MarketDataError(
                code=MarketDataErrorCode.PROVIDER_UNAVAILABLE,
                message="No market data provider is configured and capable of supplying a quote.",
            ),
        )

    async def get_quote(self, ticker: str) -> MarketSnapshotResult:
        """Same shape as `MarketDataService.get_quote`, so callers that
        only need a live price (portfolio/watchlist) swap in directly
        without pulling a full price history."""
        return await self.get_snapshot(ticker, include_recent_prices=False)

    async def _apply_historical_primary(
        self, identity: CompanyIdentity, result: MarketSnapshotResult, *, market_source: str
    ) -> None:
        """Let the historical chain's primary own the price series.

        The market provider's own series is already in `result` and acts
        as the fallback, so a Screener failure here costs nothing — the
        quote and the run both continue.
        """
        chain = self._registry.chain_for(Category.HISTORICAL_PRICE)
        provider = self._historical_provider
        if provider is None or self._db is None or not chain or chain[0] != provider.name:
            # No dedicated historical primary is available, so the series
            # came from whichever market provider served the quote. Report
            # that provider by name rather than the configured chain head,
            # which may be a different provider entirely.
            self._record(
                Category.HISTORICAL_PRICE,
                [
                    SourceAttempt(
                        provider=market_source,
                        status=SourceStatus.SUCCESS
                        if result.snapshot.recent_prices
                        else SourceStatus.UNAVAILABLE,
                    )
                ],
            )
            return

        started = time.monotonic()
        try:
            points, attempt = await provider.get_recent_prices(
                self._db, identity, self._recent_prices_limit
            )
        except Exception as exc:  # noqa: BLE001 - historical is supplementary, never fatal
            points, attempt = [], SourceAttempt(
                provider=provider.name, status=SourceStatus.ERROR, detail=str(exc)
            )
        attempt.duration_ms = int((time.monotonic() - started) * 1000)

        attempts = [attempt]
        self._log(Category.HISTORICAL_PRICE, identity.canonical_ticker, attempt, False)

        if attempt.status == SourceStatus.SUCCESS and points:
            self._registry.health(provider.name).record_success()
            result.snapshot.recent_prices = points
        else:
            self._registry.health(provider.name).record_failure(attempt.status, attempt.detail)
            fallback = SourceAttempt(
                provider=market_source,
                status=SourceStatus.SUCCESS
                if result.snapshot.recent_prices
                else SourceStatus.UNAVAILABLE,
            )
            attempts.append(fallback)
            self._log(Category.HISTORICAL_PRICE, identity.canonical_ticker, fallback, True)
            result.snapshot.warnings.append(
                f"historical prices from {provider.name} unavailable "
                f"({attempt.status.value}); used {market_source}"
            )

        self._record(Category.HISTORICAL_PRICE, attempts)

    def _provider_symbol(self, provider: str, identity: CompanyIdentity) -> str:
        """The provider-specific symbol is applied here, at the boundary —
        the canonical bare ticker is what every caller passes in."""
        if provider == "yfinance":
            return identity.yfinance_symbol or identity.canonical_ticker
        if provider == "fmp":
            return identity.fmp_symbol or identity.canonical_ticker
        return identity.canonical_ticker

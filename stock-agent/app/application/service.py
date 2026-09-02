"""Composes data acquisition and analysis for ticker-based requests.

`AnalysisApplicationService.analyze_by_ticker` fetches `CompanyFinancials`
via `FinancialDataService`, then hands them to the existing, unmodified
`AnalysisPipelineService` — exactly the same pipeline `POST /api/v1/analyze`
already uses. If data acquisition fails, the pipeline is never invoked;
the result is a `CombinedAnalysisResult` with `status="failed"` and a
sanitized warning (never a raw provider payload or credential).

Step 4: also resolves `current_share_price` from `MarketDataService`
(the existing, separate market-data abstraction — see `app/market/`)
when the caller didn't supply one explicitly. This is input wiring
only: the resolved price is placed on the same `current_share_price`
field `ValuationService`/`build_valuation_input` already consume, and
every downstream valuation/scoring behavior for a missing price is
exactly what already existed before this change — no new "unavailable"
handling was added, because none was needed.

Also resolves `recent_prices` the same way (explicit request value
always wins, otherwise fetched from `MarketDataService`) so the
forecasting stage's price-trend extrapolation has historical prices to
work with without every caller needing to supply them.
"""

import logging
from decimal import Decimal

from app.data.models import CompanyIdentifier
from app.data.service import FinancialDataFetcher
from app.market.service import MarketDataFetcher
from app.models.market import HistoricalPricePoint, MarketSnapshot, PriceFreshness
from app.pipeline.models import (
    AnalysisRequest,
    CombinedAnalysisResult,
    PipelineCompanyInfo,
    PipelineStatus,
    TickerAnalysisRequest,
)
from app.pipeline.service import AnalysisPipelineService

logger = logging.getLogger(__name__)

# A quote is only usable for valuation if it's LIVE or DELAYED. STALE is
# deliberately excluded: valuation answers "is this attractive at the
# CURRENT price", and a stale-tagged price is, by this application's own
# freshness model, not trustworthy enough to represent "current". This
# mirrors the existing "never fabricate/never use what the provider
# itself flagged as unreliable" policy already applied throughout
# app/market/ and app/data/.
_USABLE_FRESHNESS = {PriceFreshness.LIVE, PriceFreshness.DELAYED}


class AnalysisApplicationService:
    def __init__(
        self,
        financial_data_service: FinancialDataFetcher,
        analysis_pipeline_service: AnalysisPipelineService,
        market_data_service: MarketDataFetcher | None = None,
    ) -> None:
        self._financial_data_service = financial_data_service
        self._pipeline = analysis_pipeline_service
        self._market_data_service = market_data_service

    async def analyze_by_ticker(
        self, request: TickerAnalysisRequest, run_analyst: bool = True
    ) -> CombinedAnalysisResult:
        company = PipelineCompanyInfo(name=request.ticker, ticker=request.ticker)

        fetch_result = await self._financial_data_service.get_company_financials(
            CompanyIdentifier(ticker=request.ticker)
        )

        if fetch_result.status != "success":
            logger.warning(
                "Financial data fetch failed for %s: %s", request.ticker, fetch_result.error
            )
            return CombinedAnalysisResult(
                company=company,
                status=PipelineStatus.FAILED,
                warnings=[f"Failed to retrieve financial data: {fetch_result.error.message}"],
            )

        data = fetch_result.data
        current_share_price, recent_prices, market_warning = await self._resolve_market_data(request)

        analysis_request = AnalysisRequest(
            company_name=data.company_financials.company_name,
            ticker=request.ticker,
            company_financials=data.company_financials,
            **{
                **request.model_dump(exclude={"ticker", "current_share_price", "recent_prices"}),
                "current_share_price": current_share_price,
                "recent_prices": recent_prices,
            },
        )

        result = await self._pipeline.analyze(analysis_request, run_analyst=run_analyst)
        warnings = data.warnings + result.warnings
        if market_warning:
            warnings = warnings + [market_warning]
        return result.model_copy(update={"warnings": warnings})

    async def _resolve_market_data(
        self, request: TickerAnalysisRequest
    ) -> tuple[Decimal | None, list[HistoricalPricePoint], str | None]:
        """An explicit `current_share_price` / `recent_prices` on the
        request always wins — this preserves the existing override
        behavior callers already rely on. Otherwise, if a
        `MarketDataService` is configured, fetch one snapshot (quote +
        recent prices) through it (never a direct HTTP call, never a
        second FMP client). The quote's price is used only when the
        quote is LIVE or DELAYED; recent prices are supplementary and
        used regardless of quote freshness — the forecasting stage's
        trend fit treats a short/empty history as unavailable itself.

        Never raises: a market-data failure (provider down, rate limited,
        auth failure, or anything unexpected including a network-layer
        exception the provider client didn't already convert) must not
        take down ticker analysis — financial analysis, valuation, and
        scoring must remain available with the price simply left unset,
        exactly like any other missing valuation input.
        """
        want_price = request.current_share_price is None
        want_recent_prices = not request.recent_prices and request.include_price_trend_forecast

        if not want_price and not want_recent_prices:
            return request.current_share_price, request.recent_prices, None
        if self._market_data_service is None:
            return request.current_share_price, request.recent_prices, None

        unavailable_message = (
            "Current market price is unavailable for {ticker}{detail}"
            if want_price
            else "Price history is unavailable for {ticker}{detail}"
        )

        try:
            result = await self._market_data_service.get_snapshot(
                request.ticker, include_recent_prices=want_recent_prices
            )
        except Exception as exc:  # noqa: BLE001 - market data is optional; never fail ticker analysis for it
            logger.warning("Market data service raised unexpectedly for %s: %s", request.ticker, exc)
            return (
                request.current_share_price,
                request.recent_prices,
                unavailable_message.format(ticker=request.ticker, detail="."),
            )

        if result.status != "success" or result.snapshot is None:
            detail = result.error.message if result.error else "no snapshot was returned"
            logger.info("Market snapshot unavailable for %s: %s", request.ticker, detail)
            return (
                request.current_share_price,
                request.recent_prices,
                unavailable_message.format(ticker=request.ticker, detail=f": {detail}"),
            )

        snapshot: MarketSnapshot = result.snapshot
        recent_prices = (
            snapshot.recent_prices if want_recent_prices else request.recent_prices
        )

        if not want_price:
            return request.current_share_price, recent_prices, None
        if snapshot.quote is None or snapshot.quote.current_price is None:
            return None, recent_prices, f"Current market price is unavailable for {request.ticker}."
        if snapshot.quote.freshness not in _USABLE_FRESHNESS:
            return None, recent_prices, (
                f"Current market price for {request.ticker} is {snapshot.quote.freshness.value} "
                "and was not used for valuation."
            )
        return snapshot.quote.current_price, recent_prices, None

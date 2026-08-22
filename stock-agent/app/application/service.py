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
"""

import logging
from decimal import Decimal

from app.data.models import CompanyIdentifier
from app.data.service import FinancialDataService
from app.market.service import MarketDataService
from app.models.market import PriceFreshness
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
        financial_data_service: FinancialDataService,
        analysis_pipeline_service: AnalysisPipelineService,
        market_data_service: MarketDataService | None = None,
    ) -> None:
        self._financial_data_service = financial_data_service
        self._pipeline = analysis_pipeline_service
        self._market_data_service = market_data_service

    async def analyze_by_ticker(self, request: TickerAnalysisRequest) -> CombinedAnalysisResult:
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
        current_share_price, market_warning = await self._resolve_current_share_price(request)

        analysis_request = AnalysisRequest(
            company_name=data.company_financials.company_name,
            ticker=request.ticker,
            company_financials=data.company_financials,
            **{
                **request.model_dump(exclude={"ticker", "current_share_price"}),
                "current_share_price": current_share_price,
            },
        )

        result = await self._pipeline.analyze(analysis_request)
        warnings = data.warnings + result.warnings
        if market_warning:
            warnings = warnings + [market_warning]
        return result.model_copy(update={"warnings": warnings})

    async def _resolve_current_share_price(
        self, request: TickerAnalysisRequest
    ) -> tuple[Decimal | None, str | None]:
        """An explicit `current_share_price` on the request always wins —
        this preserves the existing override behavior callers already
        rely on. Otherwise, if a `MarketDataService` is configured, fetch
        a live quote through it (never a direct HTTP call, never a second
        FMP client) and use its price only when the quote is LIVE or
        DELAYED.

        Never raises: a market-data failure (provider down, rate limited,
        auth failure, or anything unexpected including a network-layer
        exception the provider client didn't already convert) must not
        take down ticker analysis — financial analysis, valuation, and
        scoring must remain available with the price simply left unset,
        exactly like any other missing valuation input.
        """
        if request.current_share_price is not None:
            return request.current_share_price, None
        if self._market_data_service is None:
            return None, None

        try:
            result = await self._market_data_service.get_quote(request.ticker)
        except Exception as exc:  # noqa: BLE001 - market price is optional; never fail ticker analysis for it
            logger.warning("Market data service raised unexpectedly for %s: %s", request.ticker, exc)
            return None, f"Current market price is unavailable for {request.ticker}."

        if result.status != "success" or result.snapshot is None or result.snapshot.quote is None:
            detail = result.error.message if result.error else "no quote was returned"
            logger.info("Market quote unavailable for %s: %s", request.ticker, detail)
            return None, f"Current market price is unavailable for {request.ticker}: {detail}"

        quote = result.snapshot.quote
        if quote.current_price is None:
            return None, f"Current market price is unavailable for {request.ticker}."
        if quote.freshness not in _USABLE_FRESHNESS:
            return None, (
                f"Current market price for {request.ticker} is {quote.freshness.value} and "
                "was not used for valuation."
            )
        return quote.current_price, None

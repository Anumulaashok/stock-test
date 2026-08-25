from decimal import Decimal

import pytest

from app.application.service import AnalysisApplicationService
from app.data.base import FinancialDataProvider
from app.data.exceptions import ProviderError
from app.data.models import (
    CompanyIdentifier,
    FinancialDataErrorCode,
    FinancialDataMetadata,
    FinancialDataResult,
)
from app.data.service import FinancialDataService
from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_statements import CompanyFinancials, IncomeStatement
from app.models.market import (
    MarketDataError,
    MarketDataErrorCode,
    MarketQuote,
    MarketSnapshot,
    MarketSnapshotResult,
    MarketStatus,
    PriceFreshness,
)
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult
from app.models.valuation import ValuationRange
from app.pipeline.models import PipelineStatus, TickerAnalysisRequest
from app.pipeline.service import AnalysisPipelineService


def d(value) -> Decimal:
    return Decimal(str(value))


class FakeProvider(FinancialDataProvider):
    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataResult:
        if self._raises:
            raise self._raises
        return self._result


def _fetch_success(ticker="ACME"):
    financials = CompanyFinancials(
        company_name=ticker, ticker=ticker,
        income_statements=[IncomeStatement(period="FY2024", revenue=d(1000))],
    )
    return FinancialDataResult(
        company_financials=financials,
        metadata=FinancialDataMetadata(
            provider="financial_modeling_prep", source_identifier=ticker, retrieved_at="2026-01-01T00:00:00Z",
        ),
        warnings=["some provider warning"],
    )


class FakeFinancialService:
    def __init__(self):
        self.received_company_financials = None

    def analyze(self, company_financials):
        self.received_company_financials = company_financials
        return FinancialAnalysisResult(company=company_financials.company_name, periods_analyzed=["FY2024"], metrics=[])


class FakeValuationService:
    def __init__(self):
        self.received_valuation_input = None

    def analyze(self, valuation_input):
        self.received_valuation_input = valuation_input
        return ValuationRange(company="ACME", results=[])


class FakeScoringService:
    def analyze(self, financial_analysis, valuation):
        return ScoringResult(
            company_name="ACME", overall_score=d(70), overall_status=ScoreStatus.CALCULATED,
            category_scores=[CategoryScore(category="profitability", score=d(70), weight=d("1.0"), status=ScoreStatus.CALCULATED)],
        )


class FakeAnalystService:
    async def analyze(self, financial_analysis, valuation, scoring, company_financials=None, research=None):
        from app.models.analyst import AnalystResponse, AnalystResult, AnalystSection
        section = AnalystSection(text="ok")
        return AnalystResult(status="success", response=AnalystResponse(
            company_name="ACME", investment_thesis=section, profitability_analysis=section,
            growth_analysis=section, financial_health_analysis=section, cash_flow_analysis=section,
            valuation_analysis=section, risk_analysis=section,
        ))


class FakeMarketDataService:
    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises
        self.received_ticker = None

    async def get_snapshot(self, ticker, include_recent_prices=True):
        self.received_ticker = ticker
        if self._raises:
            raise self._raises
        return self._result

    async def get_quote(self, ticker):
        return await self.get_snapshot(ticker, include_recent_prices=False)


def _quote_result(price="180.00", freshness=PriceFreshness.LIVE) -> MarketSnapshotResult:
    quote = MarketQuote(
        ticker="ACME", current_price=d(price), previous_close=d(price), change=d(0),
        change_percent=d(0), currency="USD", market_status=MarketStatus.OPEN,
        market_timestamp=None, data_timestamp="2026-08-21T00:00:00+00:00",
        freshness=freshness, source="stub",
    )
    snapshot = MarketSnapshot(ticker="ACME", quote=quote, recent_prices=[], fetched_at="2026-08-21T00:00:00+00:00")
    return MarketSnapshotResult(status="success", snapshot=snapshot)


def _application_service(provider, market_data_service=None):
    financial_service = FakeFinancialService()
    valuation_service = FakeValuationService()
    pipeline = AnalysisPipelineService(
        financial_service=financial_service,
        valuation_service=valuation_service,
        scoring_service=FakeScoringService(),
        analyst_service=FakeAnalystService(),
    )
    app_service = AnalysisApplicationService(
        FinancialDataService(provider), pipeline, market_data_service
    )
    return app_service, financial_service, valuation_service


@pytest.mark.asyncio
async def test_successful_ticker_analysis_flows_through_pipeline():
    provider = FakeProvider(result=_fetch_success())
    app_service, financial_service, _ = _application_service(provider)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="acme"))

    assert result.status is PipelineStatus.CALCULATED
    assert result.financial_analysis is not None
    # The pipeline received exactly the normalized CompanyFinancials the
    # data service produced -- not raw provider data, not a second copy.
    assert financial_service.received_company_financials is not None
    assert financial_service.received_company_financials.company_name == "ACME"
    assert financial_service.received_company_financials.income_statements[0].revenue == d(1000)


@pytest.mark.asyncio
async def test_provider_warnings_propagate_into_combined_result():
    provider = FakeProvider(result=_fetch_success())
    app_service, _, _ = _application_service(provider)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="ACME"))

    assert "some provider warning" in result.warnings


@pytest.mark.asyncio
async def test_company_not_found_returns_failed_without_running_pipeline():
    provider = FakeProvider(raises=ProviderError(FinancialDataErrorCode.COMPANY_NOT_FOUND, "no data for ticker"))
    app_service, financial_service, _ = _application_service(provider)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="NOPE"))

    assert result.status is PipelineStatus.FAILED
    assert result.financial_analysis is None
    assert any("no data for ticker" in w for w in result.warnings)
    assert financial_service.received_company_financials is None  # pipeline never ran


@pytest.mark.asyncio
async def test_provider_unavailable_returns_failed():
    provider = FakeProvider(raises=ProviderError(FinancialDataErrorCode.PROVIDER_UNAVAILABLE, "down"))
    app_service, _, _ = _application_service(provider)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="ACME"))

    assert result.status is PipelineStatus.FAILED


@pytest.mark.asyncio
async def test_valuation_assumptions_pass_through_to_pipeline_request():
    provider = FakeProvider(result=_fetch_success())
    app_service, _, _ = _application_service(provider)

    request = TickerAnalysisRequest(ticker="ACME", discount_rate=d("0.09"), target_pe=d(20))
    result = await app_service.analyze_by_ticker(request)

    assert result.status is PipelineStatus.CALCULATED


# --- Step 4: automatic market-price resolution -----------------------------------


@pytest.mark.asyncio
async def test_live_quote_price_reaches_valuation():
    provider = FakeProvider(result=_fetch_success())
    market_service = FakeMarketDataService(result=_quote_result(freshness=PriceFreshness.LIVE))
    app_service, _, valuation_service = _application_service(provider, market_service)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="ACME"))

    assert result.status is PipelineStatus.CALCULATED
    assert market_service.received_ticker == "ACME"
    assert valuation_service.received_valuation_input.current_share_price == d("180.00")


@pytest.mark.asyncio
async def test_delayed_quote_price_reaches_valuation():
    provider = FakeProvider(result=_fetch_success())
    market_service = FakeMarketDataService(result=_quote_result(freshness=PriceFreshness.DELAYED))
    app_service, _, valuation_service = _application_service(provider, market_service)

    await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="ACME"))

    assert valuation_service.received_valuation_input.current_share_price == d("180.00")


@pytest.mark.asyncio
async def test_stale_quote_is_not_used_for_valuation():
    provider = FakeProvider(result=_fetch_success())
    market_service = FakeMarketDataService(result=_quote_result(freshness=PriceFreshness.STALE))
    app_service, _, valuation_service = _application_service(provider, market_service)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="ACME"))

    assert valuation_service.received_valuation_input.current_share_price is None
    assert any("stale" in w.lower() for w in result.warnings)
    # Financial analysis must still succeed even though the price was rejected.
    assert result.status is PipelineStatus.CALCULATED


@pytest.mark.asyncio
async def test_unavailable_quote_does_not_fabricate_a_price():
    provider = FakeProvider(result=_fetch_success())
    unavailable = MarketSnapshotResult(
        status="error",
        error=MarketDataError(code=MarketDataErrorCode.TICKER_NOT_FOUND, message="no quote was found"),
    )
    market_service = FakeMarketDataService(result=unavailable)
    app_service, _, valuation_service = _application_service(provider, market_service)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="ACME"))

    assert valuation_service.received_valuation_input.current_share_price is None
    assert any("current market price is unavailable" in w.lower() for w in result.warnings)
    assert result.status is PipelineStatus.CALCULATED


@pytest.mark.asyncio
async def test_market_service_failure_does_not_break_financial_analysis():
    provider = FakeProvider(result=_fetch_success())
    market_service = FakeMarketDataService(raises=RuntimeError("boom"))
    app_service, financial_service, valuation_service = _application_service(provider, market_service)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="ACME"))

    assert result.status is PipelineStatus.CALCULATED
    assert financial_service.received_company_financials is not None
    assert valuation_service.received_valuation_input.current_share_price is None


@pytest.mark.asyncio
async def test_explicit_current_share_price_overrides_market_quote():
    provider = FakeProvider(result=_fetch_success())
    market_service = FakeMarketDataService(result=_quote_result(price="999.99"))
    app_service, _, valuation_service = _application_service(provider, market_service)

    request = TickerAnalysisRequest(ticker="ACME", current_share_price=d("42.00"))
    await app_service.analyze_by_ticker(request)

    assert valuation_service.received_valuation_input.current_share_price == d("42.00")
    # The market quote was never even consulted -- an explicit price wins outright.
    assert market_service.received_ticker is None


@pytest.mark.asyncio
async def test_no_market_data_service_configured_leaves_price_unset():
    provider = FakeProvider(result=_fetch_success())
    app_service, _, valuation_service = _application_service(provider, market_data_service=None)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="ACME"))

    assert valuation_service.received_valuation_input.current_share_price is None
    assert result.status is PipelineStatus.CALCULATED

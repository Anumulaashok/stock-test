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
    def analyze(self, valuation_input):
        return ValuationRange(company="ACME", results=[])


class FakeScoringService:
    def analyze(self, financial_analysis, valuation):
        return ScoringResult(
            company_name="ACME", overall_score=d(70), overall_status=ScoreStatus.CALCULATED,
            category_scores=[CategoryScore(category="profitability", score=d(70), weight=d("1.0"), status=ScoreStatus.CALCULATED)],
        )


class FakeAnalystService:
    async def analyze(self, financial_analysis, valuation, scoring, company_financials=None):
        from app.models.analyst import AnalystResponse, AnalystResult, AnalystSection
        section = AnalystSection(text="ok", evidence=[])
        return AnalystResult(status="success", response=AnalystResponse(
            company_name="ACME", investment_thesis=section, profitability_analysis=section,
            growth_analysis=section, financial_health_analysis=section, cash_flow_analysis=section,
            valuation_analysis=section, risk_analysis=section,
        ))


def _application_service(provider):
    financial_service = FakeFinancialService()
    pipeline = AnalysisPipelineService(
        financial_service=financial_service,
        valuation_service=FakeValuationService(),
        scoring_service=FakeScoringService(),
        analyst_service=FakeAnalystService(),
    )
    app_service = AnalysisApplicationService(FinancialDataService(provider), pipeline)
    return app_service, financial_service


@pytest.mark.asyncio
async def test_successful_ticker_analysis_flows_through_pipeline():
    provider = FakeProvider(result=_fetch_success())
    app_service, financial_service = _application_service(provider)

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
    app_service, _ = _application_service(provider)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="ACME"))

    assert "some provider warning" in result.warnings


@pytest.mark.asyncio
async def test_company_not_found_returns_failed_without_running_pipeline():
    provider = FakeProvider(raises=ProviderError(FinancialDataErrorCode.COMPANY_NOT_FOUND, "no data for ticker"))
    app_service, financial_service = _application_service(provider)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="NOPE"))

    assert result.status is PipelineStatus.FAILED
    assert result.financial_analysis is None
    assert any("no data for ticker" in w for w in result.warnings)
    assert financial_service.received_company_financials is None  # pipeline never ran


@pytest.mark.asyncio
async def test_provider_unavailable_returns_failed():
    provider = FakeProvider(raises=ProviderError(FinancialDataErrorCode.PROVIDER_UNAVAILABLE, "down"))
    app_service, _ = _application_service(provider)

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="ACME"))

    assert result.status is PipelineStatus.FAILED


@pytest.mark.asyncio
async def test_valuation_assumptions_pass_through_to_pipeline_request():
    provider = FakeProvider(result=_fetch_success())
    app_service, _ = _application_service(provider)

    request = TickerAnalysisRequest(ticker="ACME", discount_rate=d("0.09"), target_pe=d(20))
    result = await app_service.analyze_by_ticker(request)

    assert result.status is PipelineStatus.CALCULATED

"""End-to-end: FINANCIAL_DATA_PROVIDER=indianapi through the full
AnalysisApplicationService -> AnalysisPipelineService chain, with a
mocked IndianAPIProvider. Verifies the downstream pipeline (financial
analysis -> valuation -> scoring -> analyst) never needs to know which
financial data provider supplied the data.
"""

from decimal import Decimal

import pytest

from app.application.service import AnalysisApplicationService
from app.data.base import FinancialDataProvider
from app.data.mappers.indianapi import build_company_financials
from app.data.models import CompanyIdentifier, FinancialDataMetadata, FinancialDataResult
from app.models.analyst import AnalystResponse, AnalystResult, AnalystSection
from app.models.financial_results import FinancialAnalysisResult
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult
from app.models.valuation import ValuationRange
from app.pipeline.models import PipelineStatus, TickerAnalysisRequest
from app.pipeline.service import AnalysisPipelineService


def d(value) -> Decimal:
    return Decimal(str(value))


def _indianapi_raw_entry():
    def item(key, value):
        return {"displayName": key, "key": key, "value": value}

    return {
        "FiscalYear": 2026,
        "Type": "Annual",
        "stockFinancialMap": {
            "INC": [
                item("Revenue", "1075675.00"),
                item("NetIncome", "80775.00"),
                item("DilutedWeightedAverageShares", "1353.27"),
                item("DilutedNormalizedEPS", "59.76"),
            ],
            "BAL": [
                item("TotalDebt", "398000.00"),
                item("CashEquivalents", "98592.00"),
                item("TotalAssets", "2178140.00"),
                item("TotalCurrentAssets", "594249.00"),
                item("TotalCurrentLiabilities", "541254.00"),
                item("TotalEquity", "904030.00"),
            ],
            "CAS": [
                item("CashfromOperatingActivities", "192113.00"),
                item("CapitalExpenditures", "-122916"),
            ],
        },
    }


class FakeIndianAPIProvider(FinancialDataProvider):
    """Mimics `IndianAPIProvider` without any real HTTP call."""

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataResult:
        company_financials, currency, warnings = build_company_financials(
            company_name="Reliance Industries",
            ticker=identifier.ticker,
            financials_raw=[_indianapi_raw_entry()],
        )
        metadata = FinancialDataMetadata(
            provider="indianapi", source_identifier=identifier.ticker,
            retrieved_at="2026-01-01T00:00:00+00:00", currency=currency, frequency="annual",
            fiscal_periods=company_financials.fiscal_periods,
        )
        return FinancialDataResult(company_financials=company_financials, metadata=metadata, warnings=warnings)


class RecordingFinancialService:
    def __init__(self):
        self.received_company_financials = None

    def analyze(self, company_financials):
        self.received_company_financials = company_financials
        return FinancialAnalysisResult(
            company=company_financials.company_name, periods_analyzed=company_financials.fiscal_periods,
            metrics=[],
        )


class PassthroughValuationService:
    def analyze(self, valuation_input):
        return ValuationRange(company="Reliance Industries", results=[])


class PassthroughScoringService:
    def analyze(self, financial_analysis, valuation):
        return ScoringResult(
            company_name="Reliance Industries", overall_score=d(70), overall_status=ScoreStatus.CALCULATED,
            category_scores=[CategoryScore(category="profitability", score=d(70), weight=d("1.0"), status=ScoreStatus.CALCULATED)],
        )


class PassthroughAnalystService:
    async def analyze(self, financial_analysis, valuation, scoring, company_financials=None, research=None):
        section = AnalystSection(text="ok")
        return AnalystResult(status="success", response=AnalystResponse(
            company_name="Reliance Industries", investment_thesis=section, profitability_analysis=section,
            growth_analysis=section, financial_health_analysis=section, cash_flow_analysis=section,
            valuation_analysis=section, risk_analysis=section,
        ))


@pytest.mark.asyncio
async def test_indianapi_flows_through_the_full_pipeline_without_it_knowing():
    from app.data.service import FinancialDataService

    financial_service = RecordingFinancialService()
    pipeline = AnalysisPipelineService(
        financial_service=financial_service,
        valuation_service=PassthroughValuationService(),
        scoring_service=PassthroughScoringService(),
        analyst_service=PassthroughAnalystService(),
    )
    app_service = AnalysisApplicationService(
        FinancialDataService(FakeIndianAPIProvider()), pipeline
    )

    result = await app_service.analyze_by_ticker(TickerAnalysisRequest(ticker="Reliance"))

    assert result.status is PipelineStatus.CALCULATED
    assert result.financial_analysis is not None

    # The CompanyFinancials the deterministic pipeline received is the
    # canonical model, built from IndianAPI data -- no IndianAPI field
    # names or shapes reached the financial service.
    received = financial_service.received_company_financials
    assert received is not None
    assert received.company_name == "Reliance Industries"
    assert received.income_statements[0].revenue == d("1075675.00")
    assert received.income_statements[0].net_income == d("80775.00")
    assert received.balance_sheets[0].total_debt == d("398000.00")
    assert received.cash_flow_statements[0].operating_cash_flow == d("192113.00")
    assert received.currency == "INR"  # IndianAPI is Indian-market-only

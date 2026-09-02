from decimal import Decimal

import pytest

from app.models.analyst import AnalystResponse, AnalystResult, AnalystSection
from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_statements import CompanyFinancials
from app.models.forecasting import ForecastResult
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult
from app.models.valuation import ValuationRange
from app.pipeline.models import AnalysisRequest, PipelineStatus
from app.pipeline.service import AnalysisPipelineService


def d(value) -> Decimal:
    return Decimal(str(value))


def _request(**overrides):
    defaults = dict(
        company_name="Acme Corp", ticker="ACME",
        company_financials=CompanyFinancials(company_name="Acme Corp"),
    )
    defaults.update(overrides)
    return AnalysisRequest(**defaults)


class FakeFinancialService:
    def analyze(self, company_financials):
        return FinancialAnalysisResult(company="Acme Corp", periods_analyzed=["FY2024"], metrics=[])


class FakeValuationService:
    def analyze(self, valuation_input):
        return ValuationRange(company="Acme Corp", current_share_price=d(50), results=[])


class FakeScoringService:
    def analyze(self, financial_analysis, valuation):
        return ScoringResult(
            company_name="Acme Corp", overall_score=d(70), overall_status=ScoreStatus.CALCULATED,
            category_scores=[CategoryScore(category="profitability", score=d(70), weight=d("1.0"), status=ScoreStatus.CALCULATED)],
        )


class FakeAnalystService:
    def __init__(self):
        self.calls = []

    async def analyze(self, financial_analysis, valuation, scoring, company_financials=None, research=None):
        self.calls.append((financial_analysis, valuation, scoring))
        section = AnalystSection(text="ok")
        return AnalystResult(status="success", response=AnalystResponse(
            company_name="Acme Corp", investment_thesis=section, profitability_analysis=section,
            growth_analysis=section, financial_health_analysis=section, cash_flow_analysis=section,
            valuation_analysis=section, risk_analysis=section,
        ))


class FakeForecastingService:
    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises
        self.calls = []

    def forecast(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise self._raises
        return self._result


def _empty_forecast_result():
    return ForecastResult(company="Acme Corp", warnings=["a forecast warning"])


def _pipeline(forecasting_service=None):
    return AnalysisPipelineService(
        financial_service=FakeFinancialService(),
        valuation_service=FakeValuationService(),
        scoring_service=FakeScoringService(),
        analyst_service=FakeAnalystService(),
        forecasting_service=forecasting_service,
    )


@pytest.mark.asyncio
async def test_no_forecasting_service_configured_leaves_forecast_none():
    pipeline = _pipeline(forecasting_service=None)

    result = await pipeline.analyze(_request())

    assert result.forecast is None
    assert result.status is PipelineStatus.CALCULATED


@pytest.mark.asyncio
async def test_projection_years_from_request_reaches_forecasting_service():
    forecasting_service = FakeForecastingService(result=_empty_forecast_result())
    pipeline = _pipeline(forecasting_service=forecasting_service)

    await pipeline.analyze(_request(projection_years=3))

    assert forecasting_service.calls[0]["projection_years"] == 3


@pytest.mark.asyncio
async def test_no_projection_years_leaves_forecasting_service_default():
    forecasting_service = FakeForecastingService(result=_empty_forecast_result())
    pipeline = _pipeline(forecasting_service=forecasting_service)

    await pipeline.analyze(_request())

    assert "projection_years" not in forecasting_service.calls[0]


@pytest.mark.asyncio
async def test_forecasting_service_result_flows_into_combined_result():
    forecasting_service = FakeForecastingService(result=_empty_forecast_result())
    pipeline = _pipeline(forecasting_service=forecasting_service)

    result = await pipeline.analyze(_request())

    assert len(forecasting_service.calls) == 1
    assert result.forecast is not None
    assert result.forecast.company == "Acme Corp"
    assert "a forecast warning" in result.warnings
    assert result.status is PipelineStatus.CALCULATED


@pytest.mark.asyncio
async def test_forecasting_service_raising_does_not_fail_pipeline():
    forecasting_service = FakeForecastingService(raises=RuntimeError("boom"))
    pipeline = _pipeline(forecasting_service=forecasting_service)

    result = await pipeline.analyze(_request())

    assert result.status is PipelineStatus.CALCULATED
    assert result.forecast is None
    assert any("Forecasting" in w for w in result.warnings)
    assert result.financial_analysis is not None
    assert result.valuation is not None
    assert result.scoring is not None


@pytest.mark.asyncio
async def test_forecasting_does_not_feed_the_analyst():
    forecasting_service = FakeForecastingService(result=_empty_forecast_result())
    pipeline = _pipeline(forecasting_service=forecasting_service)
    analyst_service = pipeline._analyst_service

    await pipeline.analyze(_request())

    financial_analysis, valuation, scoring = analyst_service.calls[0]
    assert financial_analysis is not None and valuation is not None and scoring is not None
    # forecast is not among the analyst's positional args at all
    assert len(analyst_service.calls[0]) == 3

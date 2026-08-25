from datetime import datetime, timezone
from decimal import Decimal

from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_results import MetricStatus as FMS
from app.models.forecasting import (
    FinancialForecast,
    ForecastMetric,
    ForecastResult,
    ForecastYear,
    PriceTrendForecast,
    PriceTrendPoint,
    ValuationForecastRange,
    ValuationScenario,
)
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult
from app.models.valuation import ValuationRange, ValuationResult
from app.pipeline.models import CombinedAnalysisResult, ExecutionMetadata, PipelineCompanyInfo, PipelineStatus
from app.reporting.service import ReportService


def d(value) -> Decimal:
    return Decimal(str(value))


def _clock():
    return datetime(2026, 3, 1, tzinfo=timezone.utc)


def _base_combined(forecast) -> CombinedAnalysisResult:
    return CombinedAnalysisResult(
        company=PipelineCompanyInfo(name="Acme Corp", ticker="ACME"),
        status=PipelineStatus.CALCULATED,
        financial_analysis=FinancialAnalysisResult(company="Acme Corp", periods_analyzed=["FY2024"], metrics=[]),
        valuation=ValuationRange(company="Acme Corp", current_share_price=d(100), results=[]),
        scoring=ScoringResult(
            company_name="Acme Corp", overall_score=d(70), overall_status=ScoreStatus.CALCULATED,
            category_scores=[CategoryScore(category="profitability", score=d(70), weight=d("1.0"), status=ScoreStatus.CALCULATED)],
        ),
        forecast=forecast,
        metadata=ExecutionMetadata(
            started_at="2026-03-01T00:00:00+00:00", completed_at="2026-03-01T00:00:01+00:00", duration_ms=1000,
        ),
    )


def test_no_forecast_yields_unavailable_forecast_section():
    combined = _base_combined(forecast=None)

    report = ReportService(clock=_clock).generate(combined)

    assert report.forecast is not None
    assert report.forecast.available is False


def test_forecast_section_carries_financial_metric_projections_and_formatting():
    forecast = ForecastResult(
        company="Acme Corp",
        financial_forecast=FinancialForecast(
            company="Acme Corp",
            projection_years=2,
            metrics=[
                ForecastMetric(
                    name="revenue", unit="USD", base_period="FY2025", base_value=d(121),
                    historical_cagr_percent=d(10), periods_used=["FY2024", "FY2025"],
                    status=FMS.CALCULATED,
                    projections=[
                        ForecastYear(year_offset=1, value=d("133.1"), status=FMS.CALCULATED),
                        ForecastYear(year_offset=2, value=d("146.41"), status=FMS.CALCULATED),
                    ],
                )
            ],
        ),
    )
    combined = _base_combined(forecast)

    report = ReportService(clock=_clock).generate(combined)

    assert report.forecast.available is True
    assert report.forecast.projection_years == 2
    revenue = report.forecast.financial_metrics[0]
    assert revenue.status == "calculated"
    assert revenue.formatted_historical_cagr == "10.00%"
    assert revenue.projections[0].formatted_value == "$133.10"


def test_forecast_section_carries_valuation_scenarios():
    forecast = ForecastResult(
        company="Acme Corp",
        valuation_forecast=ValuationForecastRange(
            company="Acme Corp", current_share_price=d(100),
            scenarios=[
                ValuationScenario(
                    scenario="bear", fcf_growth_rate=d("0.05"),
                    result=ValuationResult(method="dcf", value_per_share=d(90), status=FMS.CALCULATED),
                ),
                ValuationScenario(
                    scenario="base", fcf_growth_rate=d("0.07"),
                    result=ValuationResult(method="dcf", value_per_share=d(110), status=FMS.CALCULATED),
                ),
            ],
        ),
    )
    combined = _base_combined(forecast)

    report = ReportService(clock=_clock).generate(combined)

    scenarios = {s.scenario: s for s in report.forecast.valuation_scenarios}
    assert scenarios["bear"].formatted_value_per_share == "$90.00"
    assert scenarios["base"].value_per_share == d(110)


def test_forecast_section_carries_price_trend_and_disclaimer():
    forecast = ForecastResult(
        company="Acme Corp",
        price_trend_forecast=PriceTrendForecast(
            ticker="ACME", based_on_points=10, status=FMS.CALCULATED,
            points=[PriceTrendPoint(day_offset=1, projected_price=d(101))],
        ),
    )
    combined = _base_combined(forecast)

    report = ReportService(clock=_clock).generate(combined)

    assert report.forecast.price_trend_status == "calculated"
    assert report.forecast.price_trend[0].formatted_projected_price == "$101.00"
    assert "not a prediction" in report.forecast.price_trend_disclaimer

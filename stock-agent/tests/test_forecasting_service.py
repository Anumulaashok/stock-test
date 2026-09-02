from decimal import Decimal

from app.financial.service import FinancialAnalysisService
from app.forecasting.service import ForecastingService
from app.models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFinancials,
    IncomeStatement,
)
from app.models.financial_results import MetricStatus
from app.models.market import HistoricalPricePoint
from app.models.valuation import ValuationInput


def d(value) -> Decimal:
    return Decimal(str(value))


def price_point(timestamp: str, close: Decimal | None) -> HistoricalPricePoint:
    return HistoricalPricePoint(timestamp=timestamp, open=close, high=close, low=close, close=close)


def _company_financials() -> CompanyFinancials:
    return CompanyFinancials(
        company_name="Acme Corp",
        ticker="ACME",
        income_statements=[
            IncomeStatement(period="FY2023", revenue=d(100), net_income=d(10), eps=d(1)),
            IncomeStatement(period="FY2024", revenue=d(110), net_income=d(11), eps=d("1.1")),
            IncomeStatement(period="FY2025", revenue=d(121), net_income=d("12.1"), eps=d("1.21")),
        ],
        balance_sheets=[
            BalanceSheet(period="FY2025", total_debt=d(50), cash_and_equivalents=d(20), shareholders_equity=d(200)),
        ],
        cash_flow_statements=[
            CashFlowStatement(period="FY2023", free_cash_flow=d(40)),
            CashFlowStatement(period="FY2024", free_cash_flow=d(44)),
            CashFlowStatement(period="FY2025", free_cash_flow=d("48.4")),
        ],
    )


def _financial_analysis(company_financials: CompanyFinancials):
    return FinancialAnalysisService().analyze(company_financials)


# --- forecast_financials -----------------------------------------------------------------


def test_forecast_financials_projects_revenue_from_two_period_cagr():
    company_financials = _company_financials()
    financial_analysis = _financial_analysis(company_financials)

    forecast = ForecastingService().forecast_financials(company_financials, financial_analysis, projection_years=2)

    revenue = next(m for m in forecast.metrics if m.name == "revenue")
    assert revenue.status is MetricStatus.CALCULATED
    assert revenue.base_value == d(121)
    # (121/100)^(1/2) - 1 = 10% CAGR
    assert revenue.historical_cagr_percent.quantize(d("0.01")) == d("10.00")
    assert [p.status for p in revenue.projections] == [MetricStatus.CALCULATED, MetricStatus.CALCULATED]


def test_forecast_financials_free_cash_flow_uses_single_period_yoy_growth():
    company_financials = _company_financials()
    financial_analysis = _financial_analysis(company_financials)

    forecast = ForecastingService().forecast_financials(company_financials, financial_analysis, projection_years=1)

    fcf = next(m for m in forecast.metrics if m.name == "free_cash_flow")
    assert fcf.status is MetricStatus.CALCULATED
    assert fcf.base_value == d("48.4")


def test_forecast_financials_fcf_sign_flip_is_invalid_not_insufficient_history():
    # Previous-period FCF negative, latest positive: Step 2's fcf_growth is
    # INVALID ("... is negative; growth percentage is not meaningful"), not
    # UNAVAILABLE -- the forecast must report that real reason verbatim
    # rather than a misleading generic "insufficient historical periods".
    company_financials = CompanyFinancials(
        company_name="Acme Corp",
        income_statements=[
            IncomeStatement(period="FY2025", revenue=d(100)),
            IncomeStatement(period="FY2026", revenue=d(110)),
        ],
        cash_flow_statements=[
            CashFlowStatement(period="FY2025", free_cash_flow=d(-40)),
            CashFlowStatement(period="FY2026", free_cash_flow=d(60)),
        ],
    )
    financial_analysis = _financial_analysis(company_financials)

    forecast = ForecastingService().forecast_financials(company_financials, financial_analysis, projection_years=1)

    fcf = next(m for m in forecast.metrics if m.name == "free_cash_flow")
    assert fcf.status is MetricStatus.INVALID
    assert fcf.reason is not None and "negative" in fcf.reason
    assert "insufficient historical periods" not in fcf.reason


def test_forecast_financials_single_period_history_is_unavailable():
    company_financials = CompanyFinancials(
        company_name="Acme Corp",
        income_statements=[IncomeStatement(period="FY2025", revenue=d(100))],
    )
    financial_analysis = _financial_analysis(company_financials)

    forecast = ForecastingService().forecast_financials(company_financials, financial_analysis, projection_years=2)

    revenue = next(m for m in forecast.metrics if m.name == "revenue")
    assert revenue.status is MetricStatus.UNAVAILABLE
    assert any("one fiscal period" in w for w in forecast.warnings)


# --- forecast_valuation -------------------------------------------------------------------


def test_forecast_valuation_builds_bear_base_bull_scenarios():
    valuation_input = ValuationInput(
        company_name="Acme Corp",
        current_share_price=d(50),
        free_cash_flow=d(100),
        fcf_growth_rate=d("0.10"),
        discount_rate=d("0.20"),
        terminal_growth_rate=d("0.02"),
        projection_years=5,
        total_debt=d(50),
        cash=d(20),
        shares_outstanding=d(10),
    )

    forecast = ForecastingService().forecast_valuation(valuation_input, projection_years=5)

    names = [s.scenario for s in forecast.scenarios]
    assert names == ["bear", "base", "bull"]
    growth_rates = {s.scenario: s.fcf_growth_rate for s in forecast.scenarios}
    assert growth_rates["bear"] < growth_rates["base"] < growth_rates["bull"]
    assert all(s.result.status is MetricStatus.CALCULATED for s in forecast.scenarios)
    values = {s.scenario: s.result.value_per_share for s in forecast.scenarios}
    assert values["bear"] < values["base"] < values["bull"]


def test_forecast_valuation_missing_growth_rate_is_unavailable_for_every_scenario():
    valuation_input = ValuationInput(company_name="Acme Corp", free_cash_flow=d(100))

    forecast = ForecastingService().forecast_valuation(valuation_input, projection_years=5)

    assert all(s.result.status is MetricStatus.UNAVAILABLE for s in forecast.scenarios)
    assert any("FCF growth rate" in w for w in forecast.warnings)


# --- forecast_price_trend -----------------------------------------------------------------


def test_forecast_price_trend_extrapolates_a_rising_line():
    recent_prices = [price_point(f"2026-01-0{i}", d(100 + i * 2)) for i in range(1, 8)]

    forecast = ForecastingService().forecast_price_trend("ACME", recent_prices, projection_days=3)

    assert forecast.status is MetricStatus.CALCULATED
    assert forecast.based_on_points == 7
    assert forecast.slope_per_day == d(2)
    assert forecast.disclaimer  # always attached
    assert [p.day_offset for p in forecast.points] == [1, 2, 3]
    assert forecast.points[0].projected_price > d(100 + 6 * 2)
    # anchor is the latest observed price's date (2026-01-07)
    assert [p.date for p in forecast.points] == ["2026-01-08", "2026-01-09", "2026-01-10"]


def test_forecast_price_trend_insufficient_points_is_unavailable():
    recent_prices = [price_point("2026-01-01", d(100))]

    forecast = ForecastingService().forecast_price_trend("ACME", recent_prices, projection_days=30)

    assert forecast.status is MetricStatus.UNAVAILABLE
    assert forecast.points == []


def test_forecast_price_trend_ignores_points_missing_close():
    recent_prices = [
        price_point("2026-01-01", None),
        price_point("2026-01-02", d(100)),
    ]

    forecast = ForecastingService().forecast_price_trend("ACME", recent_prices, projection_days=1)

    assert forecast.based_on_points == 1
    assert forecast.status is MetricStatus.UNAVAILABLE


# --- forecast (combined) ------------------------------------------------------------------


def test_forecast_combines_all_three_sub_forecasts_independently():
    company_financials = _company_financials()
    financial_analysis = _financial_analysis(company_financials)
    valuation_input = ValuationInput(company_name="Acme Corp", free_cash_flow=d(100))

    result = ForecastingService().forecast(
        company_financials=company_financials,
        financial_analysis=financial_analysis,
        valuation_input=valuation_input,
        recent_prices=[],
        ticker="ACME",
    )

    assert result.company == "Acme Corp"
    assert result.financial_forecast is not None
    assert result.valuation_forecast is not None
    assert result.price_trend_forecast is not None
    assert result.price_trend_forecast.status is MetricStatus.UNAVAILABLE
    assert result.technical_forecast is not None


# --- forecast_technical -------------------------------------------------------------------


def test_forecast_technical_computes_moving_averages_and_crossover():
    # 210 rising closes: 50-day and 200-day SMA both calculable, 50 > 200 -> golden cross.
    from datetime import date, timedelta

    base = date(2026, 1, 1)
    recent_prices = [
        price_point((base + timedelta(days=i)).isoformat(), d(100 + i)) for i in range(210)
    ]

    forecast = ForecastingService().forecast_technical(
        "ACME", recent_prices, current_price=d(400), projection_days=5
    )

    assert forecast.based_on_points == 210
    sma_50 = next(ma for ma in forecast.moving_averages if ma.window == 50)
    sma_200 = next(ma for ma in forecast.moving_averages if ma.window == 200)
    assert sma_50.status is MetricStatus.CALCULATED
    assert sma_200.status is MetricStatus.CALCULATED
    assert sma_50.value > sma_200.value
    assert forecast.crossover is not None
    assert forecast.crossover.signal == "golden_cross"

    method_names = {m.method for m in forecast.methods}
    assert method_names == {
        "sma_50",
        "sma_200",
        "linear_regression",
        "sma_crossover_momentum",
        "rate_of_change_momentum",
    }
    assert all(m.status is MetricStatus.CALCULATED for m in forecast.methods)
    expected_date = (base + timedelta(days=209 + 5)).isoformat()
    assert all(m.projected_date == expected_date for m in forecast.methods)


def test_forecast_technical_insufficient_history_marks_sma_unavailable():
    recent_prices = [price_point(f"day-{i}", d(100 + i)) for i in range(10)]

    forecast = ForecastingService().forecast_technical(
        "ACME", recent_prices, current_price=d(110), projection_days=5
    )

    sma_50 = next(ma for ma in forecast.moving_averages if ma.window == 50)
    sma_200 = next(ma for ma in forecast.moving_averages if ma.window == 200)
    assert sma_50.status is MetricStatus.UNAVAILABLE
    assert sma_200.status is MetricStatus.UNAVAILABLE
    assert forecast.crossover.status is MetricStatus.UNAVAILABLE
    crossover_method = next(m for m in forecast.methods if m.method == "sma_crossover_momentum")
    assert crossover_method.status is MetricStatus.UNAVAILABLE
    assert any("50-day moving average unavailable" in w for w in forecast.warnings)


def test_forecast_technical_no_data_is_unavailable_everywhere():
    forecast = ForecastingService().forecast_technical("ACME", [], current_price=None, projection_days=5)

    assert forecast.based_on_points == 0
    assert forecast.current_price is None
    assert all(ma.status is MetricStatus.UNAVAILABLE for ma in forecast.moving_averages)
    assert all(m.status is not MetricStatus.CALCULATED for m in forecast.methods)

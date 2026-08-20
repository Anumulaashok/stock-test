from decimal import Decimal

from app.financial import calculations as calc
from app.models.financial_results import MetricStatus

P1, P2 = "FY2023", "FY2024"


def d(value) -> Decimal:
    return Decimal(str(value))


# --- Growth: normal ---------------------------------------------------------


def test_revenue_growth_normal():
    result = calc.calculate_revenue_growth(d(100), d(120), P1, P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(20)
    assert result.unit == "%"
    assert result.source_periods == [P1, P2]


def test_net_income_growth_normal():
    result = calc.calculate_net_income_growth(d(50), d(75), P1, P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(50)


def test_eps_growth_normal():
    result = calc.calculate_eps_growth(d("2.00"), d("2.50"), P1, P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(25)


def test_fcf_growth_normal():
    result = calc.calculate_fcf_growth(d(200), d(150), P1, P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(-25)


# --- Growth: edge cases -------------------------------------------------------


def test_revenue_growth_missing_previous_period():
    result = calc.calculate_revenue_growth(None, d(120), P1, P2)
    assert result.status is MetricStatus.UNAVAILABLE
    assert result.value is None
    assert "FY2023" in result.reason


def test_revenue_growth_missing_current_period():
    result = calc.calculate_revenue_growth(d(100), None, P1, P2)
    assert result.status is MetricStatus.UNAVAILABLE
    assert "FY2024" in result.reason


def test_revenue_growth_zero_previous():
    result = calc.calculate_revenue_growth(d(0), d(120), P1, P2)
    assert result.status is MetricStatus.UNAVAILABLE
    assert result.value is None


def test_revenue_growth_negative_previous_is_invalid():
    result = calc.calculate_revenue_growth(d(-100), d(120), P1, P2)
    assert result.status is MetricStatus.INVALID
    assert result.value is None


def test_net_income_growth_negative_to_positive_previous_negative_invalid():
    # Previous period is a loss — treated as invalid rather than a
    # misleading growth percentage.
    result = calc.calculate_net_income_growth(d(-10), d(20), P1, P2)
    assert result.status is MetricStatus.INVALID


# --- Free cash flow -----------------------------------------------------------


def test_free_cash_flow_normal():
    result = calc.calculate_free_cash_flow(d(300), d(100), P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(200)
    assert result.unit == "USD"


def test_free_cash_flow_negative_result_is_still_calculated():
    result = calc.calculate_free_cash_flow(d(50), d(100), P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(-50)


def test_free_cash_flow_missing_operating_cash_flow():
    result = calc.calculate_free_cash_flow(None, d(100), P2)
    assert result.status is MetricStatus.UNAVAILABLE


def test_free_cash_flow_missing_capex():
    result = calc.calculate_free_cash_flow(d(300), None, P2)
    assert result.status is MetricStatus.UNAVAILABLE


# --- Margins: normal ---------------------------------------------------------


def test_gross_margin_normal():
    result = calc.calculate_gross_margin(d(1000), d(400), P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(40)


def test_operating_margin_normal():
    result = calc.calculate_operating_margin(d(1000), d(150), P2)
    assert result.value == d("15")


def test_net_margin_normal():
    result = calc.calculate_net_margin(d(1000), d(100), P2)
    assert result.value == d(10)


def test_fcf_margin_normal():
    result = calc.calculate_fcf_margin(d(1000), d(50), P2)
    assert result.value == d(5)


# --- Margins: edge cases -------------------------------------------------------


def test_gross_margin_zero_revenue():
    result = calc.calculate_gross_margin(d(0), d(400), P2)
    assert result.status is MetricStatus.UNAVAILABLE
    assert result.value is None


def test_net_margin_negative_net_income_is_calculated():
    result = calc.calculate_net_margin(d(1000), d(-100), P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(-10)


def test_fcf_margin_negative_fcf_is_calculated():
    result = calc.calculate_fcf_margin(d(1000), d(-50), P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(-5)


def test_gross_margin_missing_gross_profit():
    result = calc.calculate_gross_margin(d(1000), None, P2)
    assert result.status is MetricStatus.UNAVAILABLE


# --- ROE / ROA -----------------------------------------------------------------


def test_roe_normal():
    result = calc.calculate_roe(d(100), d(500), P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(20)


def test_roa_normal():
    result = calc.calculate_roa(d(100), d(1000), P2)
    assert result.value == d(10)


def test_roe_zero_equity():
    result = calc.calculate_roe(d(100), d(0), P2)
    assert result.status is MetricStatus.UNAVAILABLE


def test_roe_negative_equity_is_invalid():
    result = calc.calculate_roe(d(100), d(-500), P2)
    assert result.status is MetricStatus.INVALID


def test_roa_zero_assets():
    result = calc.calculate_roa(d(100), d(0), P2)
    assert result.status is MetricStatus.UNAVAILABLE


def test_roe_negative_net_income_is_calculated():
    result = calc.calculate_roe(d(-50), d(500), P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(-10)


# --- ROIC -----------------------------------------------------------------------


def test_roic_normal():
    # operating_income=200, tax_expense=20, net_income=80
    # pre_tax_income = 80 + 20 = 100; effective_tax_rate = 20/100 = 0.2
    # NOPAT = 200 * 0.8 = 160
    # invested_capital = total_debt(300) + equity(500) - cash(100) = 700
    # ROIC = 160 / 700 * 100
    result = calc.calculate_roic(
        operating_income=d(200),
        tax_expense=d(20),
        net_income=d(80),
        total_debt=d(300),
        shareholders_equity=d(500),
        cash_and_equivalents=d(100),
        period=P2,
    )
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(160) / d(700) * d(100)


def test_roic_missing_tax_expense():
    result = calc.calculate_roic(d(200), None, d(80), d(300), d(500), d(100), P2)
    assert result.status is MetricStatus.UNAVAILABLE


def test_roic_zero_invested_capital():
    # total_debt(100) + equity(0) - cash(100) = 0
    result = calc.calculate_roic(d(200), d(20), d(80), d(100), d(0), d(100), P2)
    assert result.status is MetricStatus.UNAVAILABLE


def test_roic_negative_invested_capital_is_invalid():
    result = calc.calculate_roic(d(200), d(20), d(80), d(0), d(0), d(100), P2)
    assert result.status is MetricStatus.INVALID


def test_roic_zero_pretax_income():
    # net_income(-20) + tax_expense(20) = 0
    result = calc.calculate_roic(d(200), d(20), d(-20), d(300), d(500), d(100), P2)
    assert result.status is MetricStatus.UNAVAILABLE


# --- Leverage -------------------------------------------------------------------


def test_debt_to_equity_normal():
    result = calc.calculate_debt_to_equity(d(200), d(400), P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d("0.5")


def test_debt_to_equity_zero_debt_is_calculated_zero():
    result = calc.calculate_debt_to_equity(d(0), d(400), P2)
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(0)


def test_debt_to_equity_zero_equity():
    result = calc.calculate_debt_to_equity(d(200), d(0), P2)
    assert result.status is MetricStatus.UNAVAILABLE


def test_debt_to_equity_negative_equity_is_invalid():
    result = calc.calculate_debt_to_equity(d(200), d(-400), P2)
    assert result.status is MetricStatus.INVALID


def test_debt_to_fcf_normal():
    result = calc.calculate_debt_to_fcf(d(300), d(150), P2)
    assert result.value == d(2)


def test_debt_to_fcf_negative_fcf_is_invalid():
    result = calc.calculate_debt_to_fcf(d(300), d(-150), P2)
    assert result.status is MetricStatus.INVALID


def test_debt_to_fcf_zero_fcf():
    result = calc.calculate_debt_to_fcf(d(300), d(0), P2)
    assert result.status is MetricStatus.UNAVAILABLE


# --- Liquidity ------------------------------------------------------------------


def test_current_ratio_normal():
    result = calc.calculate_current_ratio(d(300), d(150), P2)
    assert result.value == d(2)


def test_current_ratio_zero_current_liabilities():
    result = calc.calculate_current_ratio(d(300), d(0), P2)
    assert result.status is MetricStatus.UNAVAILABLE


def test_cash_ratio_normal():
    result = calc.calculate_cash_ratio(d(90), d(150), P2)
    assert result.value == d("0.6")


def test_cash_ratio_missing_cash():
    result = calc.calculate_cash_ratio(None, d(150), P2)
    assert result.status is MetricStatus.UNAVAILABLE


# --- Coverage ----------------------------------------------------------------


def test_interest_coverage_normal():
    result = calc.calculate_interest_coverage(d(200), d(40), P2)
    assert result.value == d(5)


def test_interest_coverage_zero_interest_expense():
    result = calc.calculate_interest_coverage(d(200), d(0), P2)
    assert result.status is MetricStatus.UNAVAILABLE
    assert "interest expense is zero" in result.reason


def test_interest_coverage_negative_interest_expense_is_invalid():
    result = calc.calculate_interest_coverage(d(200), d(-40), P2)
    assert result.status is MetricStatus.INVALID

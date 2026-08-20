from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.valuation import dcf


def d(value) -> Decimal:
    return Decimal(str(value))


# --- Low-level pure helpers, hand-calculated -----------------------------------


def test_project_fcf():
    assert dcf.project_fcf(d(100), d("0.10"), 1) == d(110)
    assert dcf.project_fcf(d(100), d("0.10"), 2) == d("121.00")


def test_discount_factor():
    assert dcf.discount_factor(d("0.25"), 1) == d("0.8")


def test_calculate_terminal_value():
    # FCF_(n+1)=121, WACC=0.25, terminal growth=0.05 -> 121 / 0.20 = 605
    assert dcf.calculate_terminal_value(d(121), d("0.25"), d("0.05")) == d(605)


def test_calculate_enterprise_value():
    assert dcf.calculate_enterprise_value([d(88)], d(484)) == d(572)


def test_calculate_equity_value():
    assert dcf.calculate_equity_value(d(572), d(50), d(20)) == d(542)


def test_calculate_value_per_share():
    assert dcf.calculate_value_per_share(d(542), d(10)) == d("54.2")


# --- Full calculate_dcf, hand-calculated end to end -----------------------------


def test_calculate_dcf_hand_calculated_example():
    """
    base_fcf=100, growth=10%, WACC=25%, terminal growth=5%, 1 year projection,
    debt=50, cash=20, shares=10.

    FCF_1 = 100 * 1.10 = 110; discount factor = 1/1.25 = 0.8; PV = 88
    FCF_2 (for terminal) = 100 * 1.10^2 = 121
    TV = 121 / (0.25 - 0.05) = 605; PV(TV) = 605 * 0.8 = 484
    EV = 88 + 484 = 572
    Equity value = 572 - 50 + 20 = 542
    Value per share = 542 / 10 = 54.2
    """
    result = dcf.calculate_dcf(
        base_fcf=d(100),
        fcf_growth_rate=d("0.10"),
        discount_rate=d("0.25"),
        terminal_growth_rate=d("0.05"),
        projection_years=1,
        total_debt=d(50),
        cash=d(20),
        shares_outstanding=d(10),
    )

    assert result.status is MetricStatus.CALCULATED
    assert result.value_per_share == d("54.2")
    assert result.method == "dcf"
    assert result.assumptions["discount_rate"] == d("0.25")

    details_by_name = {detail.name: detail.value for detail in result.details}
    assert details_by_name["projected_fcf_year_1"] == d(110)
    assert details_by_name["terminal_value"] == d(605)
    assert details_by_name["present_value_terminal_value"] == d(484)
    assert details_by_name["enterprise_value"] == d(572)
    assert details_by_name["equity_value"] == d(542)


def test_calculate_dcf_multi_year_projection():
    result = dcf.calculate_dcf(
        base_fcf=d(100),
        fcf_growth_rate=d("0.10"),
        discount_rate=d("0.25"),
        terminal_growth_rate=d("0.05"),
        projection_years=2,
        total_debt=d(0),
        cash=d(0),
        shares_outstanding=d(10),
    )
    assert result.status is MetricStatus.CALCULATED
    names = [detail.name for detail in result.details]
    assert "projected_fcf_year_1" in names
    assert "projected_fcf_year_2" in names
    assert "projected_fcf_year_3" not in names


# --- Validation / edge cases --------------------------------------------------


def _dcf(**overrides):
    defaults = dict(
        base_fcf=d(100),
        fcf_growth_rate=d("0.10"),
        discount_rate=d("0.10"),
        terminal_growth_rate=d("0.03"),
        projection_years=5,
        total_debt=d(50),
        cash=d(20),
        shares_outstanding=d(10),
    )
    defaults.update(overrides)
    return dcf.calculate_dcf(**defaults)


def test_dcf_missing_fcf_is_unavailable():
    result = _dcf(base_fcf=None)
    assert result.status is MetricStatus.UNAVAILABLE
    assert "free cash flow" in result.reason


def test_dcf_missing_growth_rate_is_unavailable():
    result = _dcf(fcf_growth_rate=None)
    assert result.status is MetricStatus.UNAVAILABLE


def test_dcf_missing_discount_rate_is_unavailable():
    result = _dcf(discount_rate=None)
    assert result.status is MetricStatus.UNAVAILABLE


def test_dcf_missing_debt_is_unavailable():
    result = _dcf(total_debt=None)
    assert result.status is MetricStatus.UNAVAILABLE
    assert "debt" in result.reason


def test_dcf_missing_cash_is_unavailable():
    result = _dcf(cash=None)
    assert result.status is MetricStatus.UNAVAILABLE
    assert "cash" in result.reason


def test_dcf_discount_rate_zero_is_invalid():
    result = _dcf(discount_rate=d(0))
    assert result.status is MetricStatus.INVALID


def test_dcf_discount_rate_negative_is_invalid():
    result = _dcf(discount_rate=d("-0.05"))
    assert result.status is MetricStatus.INVALID


def test_dcf_terminal_growth_equal_to_discount_rate_is_invalid():
    result = _dcf(discount_rate=d("0.08"), terminal_growth_rate=d("0.08"))
    assert result.status is MetricStatus.INVALID


def test_dcf_terminal_growth_greater_than_discount_rate_is_invalid():
    result = _dcf(discount_rate=d("0.08"), terminal_growth_rate=d("0.10"))
    assert result.status is MetricStatus.INVALID


def test_dcf_negative_terminal_growth_is_allowed_when_below_discount_rate():
    result = _dcf(discount_rate=d("0.08"), terminal_growth_rate=d("-0.02"))
    assert result.status is MetricStatus.CALCULATED


def test_dcf_zero_shares_is_invalid():
    result = _dcf(shares_outstanding=d(0))
    assert result.status is MetricStatus.INVALID


def test_dcf_negative_shares_is_invalid():
    result = _dcf(shares_outstanding=d(-10))
    assert result.status is MetricStatus.INVALID


def test_dcf_zero_projection_years_is_invalid():
    result = _dcf(projection_years=0)
    assert result.status is MetricStatus.INVALID


def test_dcf_zero_base_fcf_still_calculates():
    result = _dcf(base_fcf=d(0))
    assert result.status is MetricStatus.CALCULATED
    # Zero FCF in perpetuity contributes zero enterprise value; equity
    # value collapses to just cash minus debt.
    assert result.value_per_share == d(20 - 50) / d(10)


def test_dcf_negative_base_fcf_still_calculates():
    result = _dcf(base_fcf=d(-100))
    assert result.status is MetricStatus.CALCULATED
    assert result.value_per_share is not None
    assert result.value_per_share < 0

from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.valuation import multiples


def d(value) -> Decimal:
    return Decimal(str(value))


# --- P/E -----------------------------------------------------------------------


def test_pe_valuation_normal():
    result = multiples.calculate_pe_valuation(eps=d("2.50"), target_pe=d(20))
    assert result.status is MetricStatus.CALCULATED
    assert result.value_per_share == d(50)
    assert result.method == "pe"


def test_pe_valuation_missing_eps():
    result = multiples.calculate_pe_valuation(eps=None, target_pe=d(20))
    assert result.status is MetricStatus.UNAVAILABLE


def test_pe_valuation_missing_target_pe():
    result = multiples.calculate_pe_valuation(eps=d("2.50"), target_pe=None)
    assert result.status is MetricStatus.UNAVAILABLE


def test_pe_valuation_negative_target_pe_is_invalid():
    result = multiples.calculate_pe_valuation(eps=d("2.50"), target_pe=d(-20))
    assert result.status is MetricStatus.INVALID


def test_pe_valuation_zero_target_pe_is_invalid():
    result = multiples.calculate_pe_valuation(eps=d("2.50"), target_pe=d(0))
    assert result.status is MetricStatus.INVALID


def test_pe_valuation_negative_eps_still_calculates():
    result = multiples.calculate_pe_valuation(eps=d("-1.00"), target_pe=d(20))
    assert result.status is MetricStatus.CALCULATED
    assert result.value_per_share == d(-20)


# --- EV/EBITDA -------------------------------------------------------------------


def test_ev_ebitda_valuation_normal():
    result = multiples.calculate_ev_ebitda_valuation(
        ebitda=d(100), target_ev_ebitda=d(8), total_debt=d(50), cash=d(20), shares_outstanding=d(10)
    )
    # EV = 100*8=800; equity = 800-50+20=770; per share = 77
    assert result.status is MetricStatus.CALCULATED
    assert result.value_per_share == d(77)


def test_ev_ebitda_valuation_missing_ebitda():
    result = multiples.calculate_ev_ebitda_valuation(
        ebitda=None, target_ev_ebitda=d(8), total_debt=d(50), cash=d(20), shares_outstanding=d(10)
    )
    assert result.status is MetricStatus.UNAVAILABLE


def test_ev_ebitda_valuation_missing_debt():
    result = multiples.calculate_ev_ebitda_valuation(
        ebitda=d(100), target_ev_ebitda=d(8), total_debt=None, cash=d(20), shares_outstanding=d(10)
    )
    assert result.status is MetricStatus.UNAVAILABLE
    assert "debt" in result.reason


def test_ev_ebitda_valuation_missing_cash():
    result = multiples.calculate_ev_ebitda_valuation(
        ebitda=d(100), target_ev_ebitda=d(8), total_debt=d(50), cash=None, shares_outstanding=d(10)
    )
    assert result.status is MetricStatus.UNAVAILABLE
    assert "cash" in result.reason


def test_ev_ebitda_valuation_zero_shares_is_invalid():
    result = multiples.calculate_ev_ebitda_valuation(
        ebitda=d(100), target_ev_ebitda=d(8), total_debt=d(50), cash=d(20), shares_outstanding=d(0)
    )
    assert result.status is MetricStatus.INVALID


def test_ev_ebitda_valuation_negative_target_multiple_is_invalid():
    result = multiples.calculate_ev_ebitda_valuation(
        ebitda=d(100), target_ev_ebitda=d(-8), total_debt=d(50), cash=d(20), shares_outstanding=d(10)
    )
    assert result.status is MetricStatus.INVALID


def test_ev_ebitda_valuation_negative_ebitda_still_calculates():
    result = multiples.calculate_ev_ebitda_valuation(
        ebitda=d(-100), target_ev_ebitda=d(8), total_debt=d(50), cash=d(20), shares_outstanding=d(10)
    )
    # EV = -800; equity = -800-50+20 = -830; per share = -83
    assert result.status is MetricStatus.CALCULATED
    assert result.value_per_share == d(-83)


# --- P/FCF -----------------------------------------------------------------------


def test_pfcf_valuation_normal():
    result = multiples.calculate_pfcf_valuation(
        free_cash_flow=d(200), target_pfcf=d(15), shares_outstanding=d(10)
    )
    # FCF/share = 20; value/share = 20*15=300
    assert result.status is MetricStatus.CALCULATED
    assert result.value_per_share == d(300)


def test_pfcf_valuation_missing_fcf():
    result = multiples.calculate_pfcf_valuation(
        free_cash_flow=None, target_pfcf=d(15), shares_outstanding=d(10)
    )
    assert result.status is MetricStatus.UNAVAILABLE


def test_pfcf_valuation_missing_shares():
    result = multiples.calculate_pfcf_valuation(
        free_cash_flow=d(200), target_pfcf=d(15), shares_outstanding=None
    )
    assert result.status is MetricStatus.UNAVAILABLE


def test_pfcf_valuation_zero_target_multiple_is_invalid():
    result = multiples.calculate_pfcf_valuation(
        free_cash_flow=d(200), target_pfcf=d(0), shares_outstanding=d(10)
    )
    assert result.status is MetricStatus.INVALID


def test_pfcf_valuation_negative_fcf_still_calculates():
    result = multiples.calculate_pfcf_valuation(
        free_cash_flow=d(-200), target_pfcf=d(15), shares_outstanding=d(10)
    )
    assert result.status is MetricStatus.CALCULATED
    assert result.value_per_share == d(-300)

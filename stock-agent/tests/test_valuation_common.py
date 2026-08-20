from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.valuation.common import calculate_upside_downside


def d(value) -> Decimal:
    return Decimal(str(value))


def test_upside_downside_positive():
    result = calculate_upside_downside(d(120), d(100))
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(20)


def test_upside_downside_negative():
    result = calculate_upside_downside(d(80), d(100))
    assert result.status is MetricStatus.CALCULATED
    assert result.value == d(-20)


def test_upside_downside_missing_intrinsic_value():
    result = calculate_upside_downside(None, d(100))
    assert result.status is MetricStatus.UNAVAILABLE


def test_upside_downside_missing_current_price():
    result = calculate_upside_downside(d(120), None)
    assert result.status is MetricStatus.UNAVAILABLE


def test_upside_downside_zero_current_price():
    result = calculate_upside_downside(d(120), d(0))
    assert result.status is MetricStatus.UNAVAILABLE


def test_upside_downside_negative_current_price_is_invalid():
    result = calculate_upside_downside(d(120), d(-10))
    assert result.status is MetricStatus.INVALID

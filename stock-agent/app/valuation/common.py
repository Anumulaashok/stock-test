"""Shared helpers used across valuation methods.

Pure functions only — no I/O, no LLM calls, no market data fetching.
"""

from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.models.valuation import ValuationMetricResult


def calculated(name: str, value: Decimal, unit: str | None) -> ValuationMetricResult:
    return ValuationMetricResult(name=name, value=value, unit=unit, status=MetricStatus.CALCULATED)


def unavailable(name: str, unit: str | None, reason: str) -> ValuationMetricResult:
    return ValuationMetricResult(
        name=name, value=None, unit=unit, status=MetricStatus.UNAVAILABLE, reason=reason
    )


def invalid(name: str, unit: str | None, reason: str) -> ValuationMetricResult:
    return ValuationMetricResult(
        name=name, value=None, unit=unit, status=MetricStatus.INVALID, reason=reason
    )


def calculate_upside_downside(
    intrinsic_value: Decimal | None, current_price: Decimal | None
) -> ValuationMetricResult:
    """Upside/downside % = (intrinsic value - current price) / current price * 100.

    A positive result means the intrinsic value exceeds the current
    market price (implied upside); negative means implied downside.
    """
    name = "upside_downside"
    unit = "%"
    if intrinsic_value is None:
        return unavailable(name, unit, "intrinsic value is missing")
    if current_price is None:
        return unavailable(name, unit, "current share price is missing")
    if current_price == 0:
        return unavailable(name, unit, "current share price is zero")
    if current_price < 0:
        return invalid(
            name, unit, "current share price is negative; upside/downside is not meaningful"
        )
    value = (intrinsic_value - current_price) / current_price * 100
    return calculated(name, value, unit)

"""Discounted cash flow (DCF) valuation.

Pure, deterministic math throughout — no I/O, no LLM calls. The
low-level helpers (`project_fcf`, `discount_factor`,
`calculate_terminal_value`, `calculate_enterprise_value`,
`calculate_equity_value`, `calculate_value_per_share`) are exposed
individually so each formula can be unit tested in isolation; the
top-level `calculate_dcf` validates inputs and composes them into a
single `ValuationResult`.

Assumption policy (documented per Step 3 requirements):

- `discount_rate` (WACC) must be strictly greater than zero.
- `terminal_growth_rate` MAY be negative — a perpetually declining
  terminal cash flow is an economically valid (if pessimistic)
  assumption — but it must always be strictly less than `discount_rate`,
  otherwise the Gordon Growth denominator is zero or negative and the
  terminal value formula is undefined/nonsensical.
- `shares_outstanding` must be strictly positive.
- `total_debt` and `cash` are required inputs for the equity-value step
  (Equity Value = Enterprise Value - Debt + Cash). If either is missing,
  the result is `unavailable` rather than silently assuming zero debt or
  zero cash.
- A zero or negative base FCF is not an error — it is projected forward
  like any other value, and the resulting valuation may itself be zero
  or negative. That is a faithful (if unflattering) DCF output for a
  loss-making or cash-burning business, not an invalid assumption.
"""

from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.models.valuation import ValuationMetricResult, ValuationResult
from app.valuation.common import calculated

_CURRENCY = "USD"


def project_fcf(base_fcf: Decimal, growth_rate: Decimal, year: int) -> Decimal:
    """Projected FCF for a future year: base_fcf * (1 + growth_rate) ** year."""
    return base_fcf * (1 + growth_rate) ** year


def discount_factor(discount_rate: Decimal, year: int) -> Decimal:
    """Present-value discount factor for cash received `year` years from now."""
    return Decimal(1) / (1 + discount_rate) ** year


def calculate_terminal_value(
    fcf_next: Decimal, discount_rate: Decimal, terminal_growth_rate: Decimal
) -> Decimal:
    """Gordon Growth terminal value: FCF_(n+1) / (discount_rate - terminal_growth_rate).

    Caller is responsible for having validated
    `terminal_growth_rate < discount_rate` beforehand.
    """
    return fcf_next / (discount_rate - terminal_growth_rate)


def calculate_enterprise_value(
    present_values_of_projected_fcf: list[Decimal], present_value_of_terminal_value: Decimal
) -> Decimal:
    """Enterprise value = sum of discounted projected FCF + discounted terminal value."""
    return sum(present_values_of_projected_fcf, start=Decimal(0)) + present_value_of_terminal_value


def calculate_equity_value(enterprise_value: Decimal, total_debt: Decimal, cash: Decimal) -> Decimal:
    """Equity value = enterprise value - total debt + cash."""
    return enterprise_value - total_debt + cash


def calculate_value_per_share(equity_value: Decimal, shares_outstanding: Decimal) -> Decimal:
    """Intrinsic value per share = equity value / shares outstanding."""
    return equity_value / shares_outstanding


def calculate_dcf(
    base_fcf: Decimal | None,
    fcf_growth_rate: Decimal | None,
    discount_rate: Decimal | None,
    terminal_growth_rate: Decimal | None,
    projection_years: int | None,
    total_debt: Decimal | None,
    cash: Decimal | None,
    shares_outstanding: Decimal | None,
) -> ValuationResult:
    """Run a full DCF: project FCF, discount it, add a terminal value, and
    convert enterprise value to an intrinsic value per share.
    """
    method = "dcf"
    assumptions = {
        "fcf_growth_rate": fcf_growth_rate,
        "discount_rate": discount_rate,
        "terminal_growth_rate": terminal_growth_rate,
        "projection_years": projection_years,
    }

    def _unavailable(reason: str) -> ValuationResult:
        return ValuationResult(
            method=method, value_per_share=None, status=MetricStatus.UNAVAILABLE,
            reason=reason, assumptions=assumptions,
        )

    def _invalid(reason: str) -> ValuationResult:
        return ValuationResult(
            method=method, value_per_share=None, status=MetricStatus.INVALID,
            reason=reason, assumptions=assumptions,
        )

    if base_fcf is None:
        return _unavailable("free cash flow is missing")
    if fcf_growth_rate is None:
        return _unavailable("FCF growth rate assumption is missing")
    if discount_rate is None:
        return _unavailable("discount rate (WACC) is missing")
    if terminal_growth_rate is None:
        return _unavailable("terminal growth rate assumption is missing")
    if projection_years is None:
        return _unavailable("projection years assumption is missing")
    if total_debt is None:
        return _unavailable("total debt is missing")
    if cash is None:
        return _unavailable("cash is missing")
    if shares_outstanding is None:
        return _unavailable("shares outstanding is missing")

    if discount_rate <= 0:
        return _invalid("discount rate must be greater than zero")
    if projection_years <= 0:
        return _invalid("projection years must be a positive integer")
    if terminal_growth_rate >= discount_rate:
        return _invalid("terminal growth rate must be less than the discount rate")
    if shares_outstanding <= 0:
        return _invalid("shares outstanding must be positive")

    details: list[ValuationMetricResult] = []
    present_values: list[Decimal] = []
    for year in range(1, projection_years + 1):
        fcf_year = project_fcf(base_fcf, fcf_growth_rate, year)
        factor = discount_factor(discount_rate, year)
        pv = fcf_year * factor
        present_values.append(pv)
        details.append(calculated(f"projected_fcf_year_{year}", fcf_year, _CURRENCY))
        details.append(calculated(f"discount_factor_year_{year}", factor, "ratio"))
        details.append(calculated(f"present_value_fcf_year_{year}", pv, _CURRENCY))

    fcf_next = project_fcf(base_fcf, fcf_growth_rate, projection_years + 1)
    terminal_value = calculate_terminal_value(fcf_next, discount_rate, terminal_growth_rate)
    terminal_discount = discount_factor(discount_rate, projection_years)
    pv_terminal_value = terminal_value * terminal_discount
    details.append(calculated("terminal_value", terminal_value, _CURRENCY))
    details.append(calculated("present_value_terminal_value", pv_terminal_value, _CURRENCY))

    enterprise_value = calculate_enterprise_value(present_values, pv_terminal_value)
    equity_value = calculate_equity_value(enterprise_value, total_debt, cash)
    value_per_share = calculate_value_per_share(equity_value, shares_outstanding)
    details.append(calculated("enterprise_value", enterprise_value, _CURRENCY))
    details.append(calculated("equity_value", equity_value, _CURRENCY))

    return ValuationResult(
        method=method,
        value_per_share=value_per_share,
        status=MetricStatus.CALCULATED,
        assumptions=assumptions,
        details=details,
    )

"""Pure, deterministic financial metric calculations.

Every function here takes plain values (never a model, an API client, a
database session, or an LLM) and returns a `FinancialMetricResult`. No
function performs I/O of any kind, which keeps this module trivially
testable and safe to call from anywhere.

Formula safety policy, applied uniformly:

- A missing (`None`) numerator or denominator produces `UNAVAILABLE`.
- A zero denominator produces `UNAVAILABLE` (division is undefined) —
  never silently coerced to zero or infinity.
- A negative denominator produces `INVALID` when the ratio would not be
  economically meaningful (e.g. negative equity, negative previous-period
  value for growth). A negative *numerator* is a normal, meaningful
  value (e.g. a net loss) and is calculated normally.
"""

from decimal import Decimal

from app.models.financial_results import FinancialMetricResult, MetricStatus

_PERCENT = "%"
_RATIO = "ratio"
_CURRENCY = "USD"


def _calculated(
    name: str, value: Decimal, unit: str | None, source_periods: list[str]
) -> FinancialMetricResult:
    return FinancialMetricResult(
        name=name,
        value=value,
        unit=unit,
        status=MetricStatus.CALCULATED,
        source_periods=source_periods,
    )


def _unavailable(
    name: str, unit: str | None, reason: str, source_periods: list[str]
) -> FinancialMetricResult:
    return FinancialMetricResult(
        name=name,
        value=None,
        unit=unit,
        status=MetricStatus.UNAVAILABLE,
        reason=reason,
        source_periods=source_periods,
    )


def _invalid(
    name: str, unit: str | None, reason: str, source_periods: list[str]
) -> FinancialMetricResult:
    return FinancialMetricResult(
        name=name,
        value=None,
        unit=unit,
        status=MetricStatus.INVALID,
        reason=reason,
        source_periods=source_periods,
    )


def _safe_ratio(
    *,
    name: str,
    unit: str | None,
    numerator: Decimal | None,
    denominator: Decimal | None,
    numerator_label: str,
    denominator_label: str,
    source_periods: list[str],
    as_percentage: bool = False,
) -> FinancialMetricResult:
    """Shared numerator/denominator safety checks for ratio-style metrics."""
    if numerator is None:
        return _unavailable(name, unit, f"{numerator_label} is missing", source_periods)
    if denominator is None:
        return _unavailable(name, unit, f"{denominator_label} is missing", source_periods)
    if denominator == 0:
        return _unavailable(name, unit, f"{denominator_label} is zero", source_periods)
    if denominator < 0:
        return _invalid(
            name,
            unit,
            f"{denominator_label} is negative; {name.replace('_', ' ')} is not meaningful",
            source_periods,
        )
    value = numerator / denominator
    if as_percentage:
        value = value * 100
    return _calculated(name, value, unit, source_periods)


def _safe_growth(
    *,
    name: str,
    previous: Decimal | None,
    current: Decimal | None,
    previous_period: str,
    current_period: str,
) -> FinancialMetricResult:
    """Shared growth-rate calculation: (current - previous) / previous * 100.

    The previous-period value is the denominator, so the same zero/negative
    safety policy applies to it as to any other ratio denominator.
    """
    source_periods = [previous_period, current_period]
    if current is None:
        return _unavailable(
            name, _PERCENT, f"{current_period} value is missing", source_periods
        )
    if previous is None:
        return _unavailable(
            name, _PERCENT, f"{previous_period} value is missing", source_periods
        )
    if previous == 0:
        return _unavailable(
            name, _PERCENT, f"{previous_period} value is zero", source_periods
        )
    if previous < 0:
        return _invalid(
            name,
            _PERCENT,
            f"{previous_period} value is negative; growth percentage is not meaningful",
            source_periods,
        )
    value = (current - previous) / previous * 100
    return _calculated(name, value, _PERCENT, source_periods)


# --- Growth -----------------------------------------------------------------


def calculate_revenue_growth(
    previous: Decimal | None,
    current: Decimal | None,
    previous_period: str,
    current_period: str,
) -> FinancialMetricResult:
    """Revenue growth = (current revenue - previous revenue) / previous revenue."""
    return _safe_growth(
        name="revenue_growth",
        previous=previous,
        current=current,
        previous_period=previous_period,
        current_period=current_period,
    )


def calculate_net_income_growth(
    previous: Decimal | None,
    current: Decimal | None,
    previous_period: str,
    current_period: str,
) -> FinancialMetricResult:
    """Net income growth = (current net income - previous net income) / previous net income."""
    return _safe_growth(
        name="net_income_growth",
        previous=previous,
        current=current,
        previous_period=previous_period,
        current_period=current_period,
    )


def calculate_eps_growth(
    previous: Decimal | None,
    current: Decimal | None,
    previous_period: str,
    current_period: str,
) -> FinancialMetricResult:
    """EPS growth = (current EPS - previous EPS) / previous EPS."""
    return _safe_growth(
        name="eps_growth",
        previous=previous,
        current=current,
        previous_period=previous_period,
        current_period=current_period,
    )


def calculate_fcf_growth(
    previous: Decimal | None,
    current: Decimal | None,
    previous_period: str,
    current_period: str,
) -> FinancialMetricResult:
    """Free cash flow growth = (current FCF - previous FCF) / previous FCF."""
    return _safe_growth(
        name="fcf_growth",
        previous=previous,
        current=current,
        previous_period=previous_period,
        current_period=current_period,
    )


# --- Cash flow ----------------------------------------------------------------


def calculate_free_cash_flow(
    operating_cash_flow: Decimal | None,
    capital_expenditure: Decimal | None,
    period: str,
) -> FinancialMetricResult:
    """Free cash flow = operating cash flow - capital expenditure.

    `capital_expenditure` is expected as a positive magnitude (cash spent).
    """
    source_periods = [period]
    if operating_cash_flow is None:
        return _unavailable(
            "free_cash_flow", _CURRENCY, "operating cash flow is missing", source_periods
        )
    if capital_expenditure is None:
        return _unavailable(
            "free_cash_flow", _CURRENCY, "capital expenditure is missing", source_periods
        )
    value = operating_cash_flow - capital_expenditure
    return _calculated("free_cash_flow", value, _CURRENCY, source_periods)


# --- Profitability --------------------------------------------------------


def calculate_gross_margin(
    revenue: Decimal | None, gross_profit: Decimal | None, period: str
) -> FinancialMetricResult:
    """Gross margin = gross profit / revenue."""
    return _safe_ratio(
        name="gross_margin",
        unit=_PERCENT,
        numerator=gross_profit,
        denominator=revenue,
        numerator_label="gross profit",
        denominator_label="revenue",
        source_periods=[period],
        as_percentage=True,
    )


def calculate_operating_margin(
    revenue: Decimal | None, operating_income: Decimal | None, period: str
) -> FinancialMetricResult:
    """Operating margin = operating income / revenue."""
    return _safe_ratio(
        name="operating_margin",
        unit=_PERCENT,
        numerator=operating_income,
        denominator=revenue,
        numerator_label="operating income",
        denominator_label="revenue",
        source_periods=[period],
        as_percentage=True,
    )


def calculate_net_margin(
    revenue: Decimal | None, net_income: Decimal | None, period: str
) -> FinancialMetricResult:
    """Net margin = net income / revenue."""
    return _safe_ratio(
        name="net_margin",
        unit=_PERCENT,
        numerator=net_income,
        denominator=revenue,
        numerator_label="net income",
        denominator_label="revenue",
        source_periods=[period],
        as_percentage=True,
    )


def calculate_fcf_margin(
    revenue: Decimal | None, free_cash_flow: Decimal | None, period: str
) -> FinancialMetricResult:
    """FCF margin = free cash flow / revenue."""
    return _safe_ratio(
        name="fcf_margin",
        unit=_PERCENT,
        numerator=free_cash_flow,
        denominator=revenue,
        numerator_label="free cash flow",
        denominator_label="revenue",
        source_periods=[period],
        as_percentage=True,
    )


def calculate_roe(
    net_income: Decimal | None, shareholders_equity: Decimal | None, period: str
) -> FinancialMetricResult:
    """Return on equity = net income / shareholders' equity."""
    return _safe_ratio(
        name="roe",
        unit=_PERCENT,
        numerator=net_income,
        denominator=shareholders_equity,
        numerator_label="net income",
        denominator_label="shareholders' equity",
        source_periods=[period],
        as_percentage=True,
    )


def calculate_roa(
    net_income: Decimal | None, total_assets: Decimal | None, period: str
) -> FinancialMetricResult:
    """Return on assets = net income / total assets."""
    return _safe_ratio(
        name="roa",
        unit=_PERCENT,
        numerator=net_income,
        denominator=total_assets,
        numerator_label="net income",
        denominator_label="total assets",
        source_periods=[period],
        as_percentage=True,
    )


def calculate_roic(
    operating_income: Decimal | None,
    tax_expense: Decimal | None,
    net_income: Decimal | None,
    total_debt: Decimal | None,
    shareholders_equity: Decimal | None,
    cash_and_equivalents: Decimal | None,
    period: str,
) -> FinancialMetricResult:
    """Return on invested capital = NOPAT / invested capital.

    This uses a simplified formulation, documented explicitly because it
    approximates figures that are not directly available from the income
    statement fields defined for this project:

        pre_tax_income   ~= net_income + tax_expense
        effective_tax_rate = tax_expense / pre_tax_income
        NOPAT             = operating_income * (1 - effective_tax_rate)
        invested_capital  = total_debt + shareholders_equity - cash_and_equivalents
        ROIC              = NOPAT / invested_capital
    """
    name = "roic"
    source_periods = [period]

    if operating_income is None:
        return _unavailable(name, _PERCENT, "operating income is missing", source_periods)
    if tax_expense is None:
        return _unavailable(name, _PERCENT, "tax expense is missing", source_periods)
    if net_income is None:
        return _unavailable(name, _PERCENT, "net income is missing", source_periods)

    pre_tax_income = net_income + tax_expense
    if pre_tax_income == 0:
        return _unavailable(
            name,
            _PERCENT,
            "pre-tax income (net income + tax expense) is zero; cannot compute effective tax rate",
            source_periods,
        )
    if pre_tax_income < 0:
        return _invalid(
            name,
            _PERCENT,
            "pre-tax income (net income + tax expense) is negative; effective tax rate is not meaningful",
            source_periods,
        )

    effective_tax_rate = tax_expense / pre_tax_income
    nopat = operating_income * (1 - effective_tax_rate)

    if total_debt is None:
        return _unavailable(name, _PERCENT, "total debt is missing", source_periods)
    if shareholders_equity is None:
        return _unavailable(name, _PERCENT, "shareholders' equity is missing", source_periods)
    if cash_and_equivalents is None:
        return _unavailable(name, _PERCENT, "cash and equivalents is missing", source_periods)

    invested_capital = total_debt + shareholders_equity - cash_and_equivalents
    if invested_capital == 0:
        return _unavailable(
            name,
            _PERCENT,
            "invested capital (total debt + equity - cash) is zero",
            source_periods,
        )
    if invested_capital < 0:
        return _invalid(
            name,
            _PERCENT,
            "invested capital (total debt + equity - cash) is negative; ROIC is not meaningful",
            source_periods,
        )

    value = (nopat / invested_capital) * 100
    return _calculated(name, value, _PERCENT, source_periods)


# --- Leverage ---------------------------------------------------------------


def calculate_debt_to_equity(
    total_debt: Decimal | None, shareholders_equity: Decimal | None, period: str
) -> FinancialMetricResult:
    """Debt / equity = total debt / shareholders' equity."""
    return _safe_ratio(
        name="debt_to_equity",
        unit=_RATIO,
        numerator=total_debt,
        denominator=shareholders_equity,
        numerator_label="total debt",
        denominator_label="shareholders' equity",
        source_periods=[period],
    )


def calculate_debt_to_fcf(
    total_debt: Decimal | None, free_cash_flow: Decimal | None, period: str
) -> FinancialMetricResult:
    """Debt / FCF = total debt / free cash flow."""
    return _safe_ratio(
        name="debt_to_fcf",
        unit=_RATIO,
        numerator=total_debt,
        denominator=free_cash_flow,
        numerator_label="total debt",
        denominator_label="free cash flow",
        source_periods=[period],
    )


# --- Liquidity ----------------------------------------------------------------


def calculate_current_ratio(
    current_assets: Decimal | None, current_liabilities: Decimal | None, period: str
) -> FinancialMetricResult:
    """Current ratio = current assets / current liabilities."""
    return _safe_ratio(
        name="current_ratio",
        unit=_RATIO,
        numerator=current_assets,
        denominator=current_liabilities,
        numerator_label="current assets",
        denominator_label="current liabilities",
        source_periods=[period],
    )


def calculate_cash_ratio(
    cash_and_equivalents: Decimal | None, current_liabilities: Decimal | None, period: str
) -> FinancialMetricResult:
    """Cash ratio = cash and equivalents / current liabilities."""
    return _safe_ratio(
        name="cash_ratio",
        unit=_RATIO,
        numerator=cash_and_equivalents,
        denominator=current_liabilities,
        numerator_label="cash and equivalents",
        denominator_label="current liabilities",
        source_periods=[period],
    )


# --- Coverage -----------------------------------------------------------------


def calculate_interest_coverage(
    operating_income: Decimal | None, interest_expense: Decimal | None, period: str
) -> FinancialMetricResult:
    """Interest coverage = operating income / interest expense."""
    return _safe_ratio(
        name="interest_coverage",
        unit=_RATIO,
        numerator=operating_income,
        denominator=interest_expense,
        numerator_label="operating income",
        denominator_label="interest expense",
        source_periods=[period],
    )

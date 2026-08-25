"""Pure, deterministic forecasting math.

Every function here takes plain values and returns either a plain
result tuple or one of the `app.models.forecasting` result models —
never I/O, never an LLM call, never a fabricated value. Two distinct
techniques live here:

- Historical CAGR extrapolation (`calculate_cagr`, `project_metric`):
  compounds the most recent reported value forward at the growth rate
  implied by the earliest and latest historical data points. This is
  the same "growth rate assumption applied to a base value" pattern
  `app/valuation/dcf.py` already uses for FCF projection — reused here
  for statement-level metrics.
- Ordinary least squares trend fitting (`fit_linear_trend`): a plain
  linear regression over recent closing prices. No external numerical
  library is used — the formulas are a handful of sums.

Safety policy mirrors `app/financial/calculations.py`: a missing input
produces `UNAVAILABLE`; a mathematically undefined or economically
meaningless input (zero/negative base for a fractional-power CAGR, a
sign flip between the two endpoints) produces `INVALID`.
"""

from decimal import Decimal, InvalidOperation

from app.models.financial_results import MetricStatus
from app.models.forecasting import ForecastMetric, ForecastYear

_PERCENT = "%"


def calculate_cagr(
    begin_value: Decimal | None,
    end_value: Decimal | None,
    periods_elapsed: int | None,
) -> tuple[Decimal | None, MetricStatus, str | None]:
    """Compound annual growth rate, as a percentage: (end/begin)^(1/n) - 1.

    `periods_elapsed` is the number of compounding steps between the two
    data points (e.g. 4 for 5 annual periods spanning FY1..FY5) — not a
    count of periods in a list.
    """
    if begin_value is None or end_value is None:
        return None, MetricStatus.UNAVAILABLE, "insufficient historical data to calculate a growth trend"
    if periods_elapsed is None or periods_elapsed <= 0:
        return None, MetricStatus.UNAVAILABLE, "at least two distinct historical periods are required"
    if begin_value == 0:
        return None, MetricStatus.UNAVAILABLE, "earliest historical value is zero"
    if begin_value < 0:
        return (
            None,
            MetricStatus.INVALID,
            "earliest historical value is negative; CAGR is not meaningful",
        )
    ratio = end_value / begin_value
    if ratio < 0:
        return (
            None,
            MetricStatus.INVALID,
            "value changed sign between the earliest and latest period; CAGR is not meaningful",
        )
    try:
        growth = ratio ** (Decimal(1) / Decimal(periods_elapsed)) - 1
    except InvalidOperation:
        return None, MetricStatus.INVALID, "growth rate could not be computed from the historical values"
    return growth * 100, MetricStatus.CALCULATED, None


def project_metric(
    *,
    name: str,
    unit: str | None,
    base_period: str | None,
    base_value: Decimal | None,
    cagr_percent: Decimal | None,
    cagr_status: MetricStatus,
    cagr_reason: str | None,
    periods_used: list[str],
    projection_years: int,
) -> ForecastMetric:
    """Project `base_value` forward `projection_years` years at `cagr_percent`."""
    if cagr_status is not MetricStatus.CALCULATED or base_value is None:
        reason = cagr_reason or "base value is missing"
        projections = [
            ForecastYear(year_offset=year, value=None, status=cagr_status, reason=reason)
            for year in range(1, projection_years + 1)
        ]
        return ForecastMetric(
            name=name,
            unit=unit,
            base_period=base_period,
            base_value=base_value,
            historical_cagr_percent=cagr_percent,
            periods_used=periods_used,
            projections=projections,
            status=cagr_status,
            reason=reason,
        )

    growth_rate = cagr_percent / 100
    projections = [
        ForecastYear(
            year_offset=year,
            value=base_value * (1 + growth_rate) ** year,
            status=MetricStatus.CALCULATED,
        )
        for year in range(1, projection_years + 1)
    ]
    return ForecastMetric(
        name=name,
        unit=unit,
        base_period=base_period,
        base_value=base_value,
        historical_cagr_percent=cagr_percent,
        periods_used=periods_used,
        projections=projections,
        status=MetricStatus.CALCULATED,
    )


def fit_linear_trend(
    values: list[Decimal],
) -> tuple[Decimal | None, Decimal | None, Decimal | None, MetricStatus, str | None]:
    """Ordinary least squares fit of `values` against their index (0, 1, 2, ...).

    Returns `(slope, intercept, r_squared, status, reason)`. `slope` is
    the per-step (e.g. per trading day) change; `intercept` is the fitted
    value at index 0.
    """
    n = len(values)
    if n < 5:
        return None, None, None, MetricStatus.UNAVAILABLE, "at least 5 historical price points are required"

    x = [Decimal(i) for i in range(n)]
    x_mean = sum(x) / n
    y_mean = sum(values) / n

    ss_xx = sum((xi - x_mean) ** 2 for xi in x)
    if ss_xx == 0:
        return None, None, None, MetricStatus.INVALID, "insufficient variation in historical data"

    ss_xy = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean

    ss_tot = sum((yi - y_mean) ** 2 for yi in values)
    if ss_tot == 0:
        r_squared = Decimal(1)
    else:
        ss_res = sum((yi - (intercept + slope * xi)) ** 2 for xi, yi in zip(x, values))
        r_squared = 1 - (ss_res / ss_tot)

    return slope, intercept, r_squared, MetricStatus.CALCULATED, None

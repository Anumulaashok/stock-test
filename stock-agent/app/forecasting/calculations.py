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

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.models.financial_results import MetricStatus
from app.models.forecasting import ForecastMetric, ForecastYear

_PERCENT = "%"


def project_calendar_date(anchor_date: str | None, day_offset: int) -> str | None:
    """`anchor_date` (the latest observed price's date, ISO YYYY-MM-DD)
    plus `day_offset` calendar days -- a naive calendar-day projection,
    not trading-day-aware (weekends/holidays are not excluded). Returns
    `None` when `anchor_date` is missing or unparseable, never a guessed
    date."""
    if not anchor_date:
        return None
    try:
        parsed = datetime.fromisoformat(anchor_date)
    except ValueError:
        return None
    return (parsed + timedelta(days=day_offset)).date().isoformat()


def project_trading_date(anchor_date: str | None, trading_days_offset: int) -> str | None:
    """`anchor_date` plus `trading_days_offset` trading days, counting only
    Monday-Friday. Used for the multi-horizon forecast's period dates
    (`app/forecasting/service.py`'s `_build_multi_horizon_forecast`),
    where a weekly/monthly point landing on a weekend would be visibly
    wrong. Market holidays are NOT modeled -- this app supports both US
    (FMP) and Indian (NSE/BSE, IndianAPI) tickers, and there is no single
    holiday calendar that is correct for both, so hardcoding one exchange's
    calendar would silently mislabel the other's dates. Skipping weekends
    only is a smaller, honestly-documented approximation than that.
    Returns `None` when `anchor_date` is missing or unparseable, exactly
    like `project_calendar_date`."""
    if not anchor_date:
        return None
    try:
        parsed = datetime.fromisoformat(anchor_date)
    except ValueError:
        return None
    current = parsed
    counted = 0
    while counted < trading_days_offset:
        current += timedelta(days=1)
        if current.weekday() < 5:
            counted += 1
    return current.date().isoformat()


def calculate_sma(values: list[Decimal], window: int) -> tuple[Decimal | None, MetricStatus, str | None]:
    """Simple moving average of the most recent `window` closes.

    `values` must already be in chronological (oldest-first) order —
    only the trailing `window` entries are used.
    """
    if window <= 0:
        return None, MetricStatus.INVALID, "moving average window must be positive"
    if len(values) < window:
        return (
            None,
            MetricStatus.UNAVAILABLE,
            f"at least {window} historical closing prices are required (found {len(values)})",
        )
    recent = values[-window:]
    return sum(recent) / window, MetricStatus.CALCULATED, None


def classify_moving_average_crossover(
    sma_short: Decimal | None,
    sma_long: Decimal | None,
) -> tuple[str | None, MetricStatus, str | None]:
    """Golden-cross ("short" SMA above "long" SMA -> bullish) / death-cross
    (short below long -> bearish) classification. Neither branch is a price
    forecast by itself -- it is a well-known technical signal describing
    trend direction, reported alongside (never blended into) the other
    forecasting methods."""
    if sma_short is None or sma_long is None:
        return None, MetricStatus.UNAVAILABLE, "both moving averages are required to classify a crossover"
    if sma_short > sma_long:
        return "golden_cross", MetricStatus.CALCULATED, None
    if sma_short < sma_long:
        return "death_cross", MetricStatus.CALCULATED, None
    return "neutral", MetricStatus.CALCULATED, None


def calculate_rate_of_change(values: list[Decimal], window: int) -> tuple[Decimal | None, MetricStatus, str | None]:
    """Percentage change between the latest close and the close `window`
    trading days earlier -- a standard momentum indicator (ROC)."""
    if window <= 0:
        return None, MetricStatus.INVALID, "rate-of-change window must be positive"
    if len(values) <= window:
        return (
            None,
            MetricStatus.UNAVAILABLE,
            f"at least {window + 1} historical closing prices are required (found {len(values)})",
        )
    begin_value = values[-(window + 1)]
    end_value = values[-1]
    if begin_value == 0:
        return None, MetricStatus.UNAVAILABLE, "earliest closing price in the window is zero"
    if begin_value < 0 or end_value < 0:
        return None, MetricStatus.INVALID, "closing price cannot be negative"
    return (end_value - begin_value) / begin_value * 100, MetricStatus.CALCULATED, None


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

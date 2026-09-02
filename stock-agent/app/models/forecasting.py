"""Forecasting domain models.

Every projected number here is a deterministic extrapolation of
already-reported historical data (financial statements, DCF cash-flow
assumptions, or recent market prices) — never an LLM guess and never a
buy/sell/hold recommendation or price target. Each projected value
carries the historical basis (`source_periods`, `based_on_points`,
assumption growth rate) it was derived from, and reports `status`
/`reason` like every other calculated metric in this codebase, so a
reader can trace exactly how a number was produced and how much
historical support stands behind it.
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.financial_results import MetricStatus
from app.models.valuation import ValuationResult

# --- Financial statement forecasting ---------------------------------------------------


class ForecastYear(BaseModel):
    """One future period's projected value for a single metric."""

    year_offset: int = Field(description="Years ahead of the latest reported period (1, 2, 3, ...).")
    value: Decimal | None
    status: MetricStatus
    reason: str | None = None


class ForecastMetric(BaseModel):
    """A single metric (revenue, net income, FCF, EPS) projected forward
    from its historical compound annual growth rate (CAGR)."""

    name: str
    unit: str | None
    base_period: str | None = None
    base_value: Decimal | None = None
    historical_cagr_percent: Decimal | None = None
    periods_used: list[str] = Field(default_factory=list)
    projections: list[ForecastYear] = Field(default_factory=list)
    status: MetricStatus
    reason: str | None = None


class FinancialForecast(BaseModel):
    """Statement-level metrics (revenue, net income, FCF, EPS) projected
    forward by historical CAGR. Never blended with valuation or scoring."""

    company: str
    projection_years: int
    metrics: list[ForecastMetric] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# --- Valuation scenario forecasting -----------------------------------------------------


class ValuationScenario(BaseModel):
    """One growth-rate scenario's DCF outcome. `result` is the same
    `ValuationResult` shape the deterministic valuation engine already
    produces — this is a reapplication of `calculate_dcf`, not a new
    valuation method."""

    scenario: str  # "bear" | "base" | "bull"
    fcf_growth_rate: Decimal | None
    result: ValuationResult


class ValuationForecastRange(BaseModel):
    """A band of DCF outcomes across bear/base/bull FCF growth
    assumptions — an explicit assumption-driven range, never a single
    asserted target price."""

    company: str
    current_share_price: Decimal | None = None
    scenarios: list[ValuationScenario] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# --- Price trend forecasting -------------------------------------------------------------


class PriceTrendPoint(BaseModel):
    day_offset: int = Field(description="Trading days ahead of the most recent observed price.")
    date: str | None = Field(
        default=None,
        description="Calendar date (ISO, YYYY-MM-DD) for this offset -- a naive "
        "calendar-day projection from the latest observed price date, not "
        "trading-day-aware (weekends/holidays are not excluded).",
    )
    projected_price: Decimal | None


class PriceTrendForecast(BaseModel):
    """A naive linear trend fit over recent closing prices, extrapolated
    forward. This is a statistical curve fit, not a prediction — the
    `disclaimer` is always attached and callers must surface it wherever
    this data is shown."""

    ticker: str
    method: str = "linear_trend"
    based_on_points: int = 0
    slope_per_day: Decimal | None = None
    r_squared: Decimal | None = None
    projection_days: int = 0
    points: list[PriceTrendPoint] = Field(default_factory=list)
    status: MetricStatus
    reason: str | None = None
    disclaimer: str = (
        "Naive statistical extrapolation of recent closing prices using linear "
        "regression. It is not a prediction of future performance, carries no "
        "confidence guarantee, and should never be treated as a price target "
        "or investment recommendation."
    )


# --- Technical indicator forecasting ------------------------------------------------------


class MovingAverageResult(BaseModel):
    """A single simple moving average (e.g. 50-day, 200-day) computed
    over recent closing prices."""

    window: int = Field(description="Number of trailing trading days averaged (e.g. 50, 200).")
    value: Decimal | None
    status: MetricStatus
    reason: str | None = None


class MovingAverageCrossover(BaseModel):
    """Golden-cross / death-cross classification of the short vs. long
    moving average -- a trend-direction signal, not a price forecast."""

    short_window: int
    long_window: int
    signal: str | None = None  # "golden_cross" | "death_cross" | "neutral"
    status: MetricStatus
    reason: str | None = None


class TechnicalForecastMethod(BaseModel):
    """One named, independently-trackable price-projection technique.

    `method` is a stable identifier (e.g. "linear_regression",
    "sma_50", "sma_200", "sma_crossover_momentum", "rate_of_change") so
    results can be logged and compared, day over day, against actual
    outcomes -- each method is reported separately and never averaged
    into a single number.
    """

    method: str
    description: str
    projected_price: Decimal | None
    projection_days: int
    projected_date: str | None = Field(
        default=None, description="Calendar date (ISO, YYYY-MM-DD) this projection targets."
    )
    status: MetricStatus
    reason: str | None = None


class TechnicalForecast(BaseModel):
    """A set of well-known technical-analysis techniques (moving
    averages, crossover signal, momentum) applied to recent closing
    prices. Each is a common market heuristic, not a prediction of
    future performance -- the `disclaimer` is always attached."""

    ticker: str
    based_on_points: int = 0
    current_price: Decimal | None = None
    projection_days: int = 0
    moving_averages: list[MovingAverageResult] = Field(default_factory=list)
    crossover: MovingAverageCrossover | None = None
    methods: list[TechnicalForecastMethod] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Technical indicators (moving averages, crossover signal, momentum) "
        "computed from recent closing prices using well-known heuristic "
        "formulas. These are not predictions of future performance, carry "
        "no confidence guarantee, and should never be treated as a price "
        "target or investment recommendation."
    )


# --- Combined forecast result --------------------------------------------------------------


class ForecastResult(BaseModel):
    """Every forecasting sub-result for one company, kept separate —
    mirrors `ValuationRange`'s policy of never blending distinct methods
    into one number."""

    company: str
    financial_forecast: FinancialForecast | None = None
    valuation_forecast: ValuationForecastRange | None = None
    price_trend_forecast: PriceTrendForecast | None = None
    technical_forecast: TechnicalForecast | None = None
    warnings: list[str] = Field(default_factory=list)

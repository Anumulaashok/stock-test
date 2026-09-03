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
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.financial_results import MetricStatus
from app.models.market import HistoricalPricePoint
from app.models.valuation import ValuationResult


class ForecastHorizon(StrEnum):
    """The three supported forecast horizons. `DAILY` is the original
    (and default) horizon -- 30 trading days -- kept identical to the
    pre-multi-horizon behavior. `WEEKLY`/`MONTHLY` reuse the exact same
    deterministic formulas (see `HorizonForecast`), evaluated at coarser
    trading-day offsets, never a new calculation technique."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


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
    period: int = Field(
        description="Horizon-relative period number (1..30 for daily, "
        "1..12 for weekly/monthly) -- what a caller iterates over to "
        "render one point per period, regardless of horizon.",
    )
    day_offset: int = Field(description="Trading days ahead of the most recent observed price.")
    date: str | None = Field(
        default=None,
        description="Calendar date (ISO, YYYY-MM-DD) for this offset, "
        "projected trading-day-aware (weekends excluded; see "
        "`app.forecasting.calculations.project_trading_date`) -- market "
        "holidays are not modeled (no single calendar is correct for "
        "both this app's US and Indian tickers).",
    )
    projected_price: Decimal | None


class PriceTrendForecast(BaseModel):
    """A naive linear trend fit over recent closing prices, extrapolated
    forward. This is a statistical curve fit, not a prediction — the
    `disclaimer` is always attached and callers must surface it wherever
    this data is shown.

    The same OLS fit is reused verbatim across horizons -- `horizon`
    only records which trading-day offsets `points` was evaluated at
    (see `app.forecasting.service.ForecastingService.forecast_price_trend`);
    it is never re-derived per horizon.
    """

    ticker: str
    method: str = "linear_trend"
    horizon: ForecastHorizon = ForecastHorizon.DAILY
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
    horizon: ForecastHorizon = ForecastHorizon.DAILY
    horizon_period: int = Field(
        description="The horizon's period count this single value targets "
        "(e.g. 30 for daily's 30th trading day, 12 for weekly's 12th week "
        "or monthly's 12th month) -- distinct from `projection_days`, "
        "which is always a trading-day count.",
    )
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
    horizon: ForecastHorizon = ForecastHorizon.DAILY
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


# --- Multi-horizon forecasting -------------------------------------------------------------


class HorizonForecast(BaseModel):
    """One horizon's (daily/weekly/monthly) price-trend line and
    technical-method projections.

    Only `price_trend` is a genuine per-period series: the same OLS fit
    (`app.forecasting.calculations.fit_linear_trend`) evaluated at that
    horizon's trading-day offsets, so its point count matches the
    horizon exactly (30 for daily, 12 for weekly, 12 for monthly).

    `technical.methods` (SMA level, moving-average-crossover momentum,
    rate-of-change momentum) stay single deterministic values at the
    horizon's terminal period, exactly as they always have been for the
    daily horizon -- turning a 14-day rate-of-change or a moving-average
    spread into a fabricated per-period path for weeks/months out would
    invent math this codebase's other methods don't have a basis for.
    Each method's `status`/`reason` still applies independently at every
    horizon (e.g. SMA-200 remains UNAVAILABLE with the same reason at
    every horizon when there isn't enough price history).
    """

    horizon: ForecastHorizon
    label: str = Field(description='Human-readable horizon label, e.g. "30 Trading Days".')
    price_trend: PriceTrendForecast
    technical: TechnicalForecast


class MultiHorizonForecast(BaseModel):
    """Daily/weekly/monthly forecasts, kept as separate named fields
    (never a list) so a caller can never confuse which horizon it read."""

    daily: HorizonForecast
    weekly: HorizonForecast
    monthly: HorizonForecast


# --- Combined forecast result --------------------------------------------------------------


class ForecastResult(BaseModel):
    """Every forecasting sub-result for one company, kept separate —
    mirrors `ValuationRange`'s policy of never blending distinct methods
    into one number.

    `price_trend_forecast`/`technical_forecast` are kept for backward
    compatibility and are identical in content to `horizons.daily`'s
    fields -- they are literally the same computed objects, not a
    separate calculation. New callers should prefer `horizons`.
    """

    company: str
    financial_forecast: FinancialForecast | None = None
    valuation_forecast: ValuationForecastRange | None = None
    price_trend_forecast: PriceTrendForecast | None = None
    technical_forecast: TechnicalForecast | None = None
    horizons: MultiHorizonForecast | None = None
    historical_prices: list[HistoricalPricePoint] = Field(
        default_factory=list,
        description="The same closing-price history the forecast was "
        "computed from (sorted, close not null) -- echoed back so a "
        "chart can render the historical segment alongside the forecast "
        "segment without a second fetch. Never recalculated here.",
    )
    warnings: list[str] = Field(default_factory=list)

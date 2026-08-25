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


# --- Combined forecast result --------------------------------------------------------------


class ForecastResult(BaseModel):
    """Every forecasting sub-result for one company, kept separate —
    mirrors `ValuationRange`'s policy of never blending distinct methods
    into one number."""

    company: str
    financial_forecast: FinancialForecast | None = None
    valuation_forecast: ValuationForecastRange | None = None
    price_trend_forecast: PriceTrendForecast | None = None
    warnings: list[str] = Field(default_factory=list)

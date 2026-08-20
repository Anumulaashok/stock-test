"""Valuation domain models.

Mirrors the shape of `app/models/financial_results.py`: inputs are
explicit and optional (real-world data is often incomplete), and every
calculated metric reports its own status/reason rather than a
best-effort guess. `MetricStatus` is reused from the financial results
module so "calculated" / "unavailable" / "invalid" mean the same thing
across the whole application.
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.financial_results import MetricStatus


class ValuationInput(BaseModel):
    """Inputs available for valuing a company.

    Nothing but `company_name` is required — each valuation method
    consumes whichever subset of these fields it needs and reports
    `unavailable` for the rest.
    """

    company_name: str

    # Market data
    current_share_price: Decimal | None = None
    shares_outstanding: Decimal | None = None

    # Cash flow / earnings basis
    free_cash_flow: Decimal | None = None
    historical_free_cash_flows: list[Decimal] = Field(default_factory=list)
    revenue: Decimal | None = None
    ebitda: Decimal | None = None
    ebit: Decimal | None = None
    net_income: Decimal | None = None
    eps: Decimal | None = None

    # Balance sheet
    total_debt: Decimal | None = None
    cash: Decimal | None = None

    # DCF assumptions
    fcf_growth_rate: Decimal | None = None
    discount_rate: Decimal | None = None
    terminal_growth_rate: Decimal | None = None
    projection_years: int | None = None

    # Multiple-based valuation assumptions
    target_pe: Decimal | None = None
    target_ev_ebitda: Decimal | None = None
    target_pfcf: Decimal | None = None


class ValuationMetricResult(BaseModel):
    """A single named intermediate or final valuation figure.

    Used both for standalone metrics (e.g. upside/downside) and for the
    transparent step-by-step breakdown attached to a `ValuationResult`
    (e.g. a DCF's projected FCF, terminal value, enterprise value).
    """

    name: str
    value: Decimal | None
    unit: str | None
    status: MetricStatus
    reason: str | None = None


class ValuationResult(BaseModel):
    """The outcome of one valuation method (DCF, P/E, EV/EBITDA, P/FCF, ...).

    `assumptions` records every input the method actually used, so the
    result is self-explanatory without needing an LLM to narrate it.
    `details` carries the intermediate figures (e.g. DCF's per-year
    projections, terminal value, enterprise value) for full transparency.
    """

    method: str
    value_per_share: Decimal | None
    unit: str = "USD per share"
    status: MetricStatus
    reason: str | None = None
    assumptions: dict[str, Decimal | int | str | None] = Field(default_factory=dict)
    details: list[ValuationMetricResult] = Field(default_factory=list)
    upside_downside_percent: Decimal | None = None
    upside_downside_status: MetricStatus | None = None
    upside_downside_reason: str | None = None


class ValuationRange(BaseModel):
    """Every valuation method's result for one company, kept separate.

    Methods are never averaged or blended here — that judgment belongs
    to a later scoring/weighting layer, not this deterministic engine.
    """

    company: str
    current_share_price: Decimal | None = None
    results: list[ValuationResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SensitivityCell(BaseModel):
    """One (discount rate, terminal growth rate) combination's DCF result."""

    discount_rate: Decimal
    terminal_growth_rate: Decimal
    value_per_share: Decimal | None
    status: MetricStatus
    reason: str | None = None


class SensitivityMatrix(BaseModel):
    """A grid of DCF outcomes across discount-rate/terminal-growth combinations."""

    discount_rates: list[Decimal]
    terminal_growth_rates: list[Decimal]
    cells: list[SensitivityCell]

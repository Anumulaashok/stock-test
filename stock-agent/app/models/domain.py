"""Conceptual domain models for the future stock-analysis system.

These describe shape only — no calculations, scoring, or business logic
are implemented yet. They exist so later steps (financial, valuation,
scoring, agents) have a shared vocabulary to build against.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Company(BaseModel):
    """A company that may be the subject of analysis."""

    name: str
    ticker: str
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    description: str | None = None


class Stock(BaseModel):
    """A tradable security tied to a Company."""

    ticker: str
    company: Company
    currency: str = "USD"
    exchange: str | None = None


class FinancialMetric(BaseModel):
    """A single named financial data point for a stock, at a point in time.

    Generic on purpose — intended to represent line items such as revenue,
    net income, free cash flow, etc. once real financial data is wired up.
    """

    ticker: str
    name: str
    value: Decimal
    unit: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    source: str | None = None


class AnalysisRequest(BaseModel):
    """A request to (eventually) run analysis on a stock.

    Only the request shape is defined here — no analysis is performed at
    this stage of the project.
    """

    ticker: str
    include_fundamentals: bool = True
    include_valuation: bool = False
    include_news: bool = False
    notes: str | None = Field(
        default=None, description="Optional free-text context from the caller."
    )

"""Result models produced by the deterministic financial calculation engine."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class MetricStatus(StrEnum):
    """Outcome of attempting to calculate a single financial metric."""

    CALCULATED = "calculated"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class FinancialMetricResult(BaseModel):
    """The outcome of calculating one financial metric.

    `value` is only meaningful when `status` is CALCULATED — an
    unavailable or invalid metric always carries `value=None` and a
    human-readable `reason` rather than a fabricated number.
    """

    name: str
    value: Decimal | None
    unit: str | None
    status: MetricStatus
    reason: str | None = None
    source_periods: list[str] = Field(default_factory=list)


class FinancialAnalysisResult(BaseModel):
    """The full set of calculated metrics for one company's analysis."""

    company: str
    periods_analyzed: list[str] = Field(default_factory=list)
    metrics: list[FinancialMetricResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

"""Scoring and risk domain models.

`ScoreStatus` intentionally reuses the same three-state vocabulary as
`MetricStatus` (calculated / unavailable / invalid) so the scoring layer
speaks the same language as the financial and valuation layers it
consumes. It is a distinct type because a *score* can be unavailable
for reasons a raw metric cannot (e.g. an entire category with zero
usable inputs), and keeping them separate avoids conflating "this
number could not be computed" with "this score could not be computed".
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class ScoreStatus(StrEnum):
    CALCULATED = "calculated"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScoreBand(StrEnum):
    EXCELLENT = "excellent"
    STRONG = "strong"
    GOOD = "good"
    FAIR = "fair"
    WEAK = "weak"
    POOR = "poor"


class ScoreComponent(BaseModel):
    """One metric's contribution to a `CategoryScore`.

    `weight` is the component's *nominal* weight within its category
    (before any renormalization for unavailable components). `value` is
    the raw underlying metric value, kept alongside `score` (0-100) for
    transparency.
    """

    name: str
    score: Decimal | None
    weight: Decimal
    status: ScoreStatus
    reason: str | None = None
    source_metric: str | None = None
    value: Decimal | None = None


class CategoryScore(BaseModel):
    """One scoring category's (e.g. Profitability) aggregated 0-100 score."""

    category: str
    score: Decimal | None
    weight: Decimal
    status: ScoreStatus
    reason: str | None = None
    components: list[ScoreComponent] = Field(default_factory=list)


class RiskIndicator(BaseModel):
    """One independently evaluated risk check."""

    name: str
    severity: Severity | None = None
    status: ScoreStatus
    value: Decimal | None = None
    threshold: Decimal | None = None
    reason: str


class ScoringResult(BaseModel):
    """The full deterministic scoring output for one company."""

    company_name: str
    overall_score: Decimal | None
    overall_status: ScoreStatus
    band: ScoreBand | None = None
    category_scores: list[CategoryScore] = Field(default_factory=list)
    risk_indicators: list[RiskIndicator] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

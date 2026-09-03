"""Market Opportunity domain models — a sector/stock ranking built
entirely from the app's own already-computed, deterministic per-ticker
scoring (`ScoringResult`, see `app/models/scoring.py`); a sector's score
is the average of its constituent tickers' `overall_score`. News (when
configured) contributes only a small, capped, clearly-labeled modifier
— never the majority of the score, and never a number the LLM invents.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class Outlook(StrEnum):
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SectorStockSummary(BaseModel):
    ticker: str
    company_name: str
    overall_score: Decimal | None
    band: str | None = None
    status: str  # "calculated" | "unavailable"


class SectorSummary(BaseModel):
    sector: str
    sector_score: Decimal | None
    outlook: Outlook
    risk: RiskLevel
    growth_score: Decimal | None = None
    valuation_score: Decimal | None = None
    momentum_score: Decimal | None = None
    news_headline_count: int = 0
    constituents_evaluated: int = 0
    constituents_total: int = 0
    top_stocks: list[SectorStockSummary] = Field(default_factory=list)


class MarketOpportunityResult(BaseModel):
    status: str  # "success" | "partial" | "unavailable"
    generated_at: str
    sectors: list[SectorSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

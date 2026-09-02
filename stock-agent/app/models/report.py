"""Structured investment research report domain models.

The report is a presentation layer over already-computed evidence
(Steps 2-8) — nothing here calculates a metric, valuation, score, or
risk severity, and nothing here contains a buy/sell/hold recommendation.
Every section carries a `source` string naming the upstream result it
was built from, so the report's data lineage stays auditable.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.analyst import AnalystEvidence


class ReportStatus(StrEnum):
    CALCULATED = "calculated"
    PARTIAL = "partial"
    FAILED = "failed"


class ReportCompany(BaseModel):
    name: str
    ticker: str | None = None
    currency: str | None = None


class ReportMetadata(BaseModel):
    report_version: str
    generated_at: str
    pipeline_version: str | None = None
    duration_ms: int | None = None


class ReportWarning(BaseModel):
    """A warning, tagged with the upstream result it came from, so a
    future UI can explain *why* something is missing rather than just
    that it is."""

    source: str  # "financial_analysis" | "valuation" | "scoring" | "forecast" | "research" | "analyst" | "pipeline" | "report"
    code: str | None = None
    message: str


class ReportSignal(BaseModel):
    """A deterministic, color-coded strength/risk indicator derived from
    the already-computed score band and risk indicators (see
    `app/reporting/signal.py`). This is a data-quality/strength signal,
    not investment advice — it never says "buy", "sell", or "hold", and
    it computes nothing new; it only recolors `ScoringResult` fields
    that already exist."""

    label: str  # "strong" | "moderate" | "weak" | "unavailable"
    color: str  # "green" | "yellow" | "red" | "gray"
    reason: str


class ReportSummary(BaseModel):
    overall_score: Decimal | None = None
    overall_status: str = "unavailable"
    score_band: str | None = None
    signal: ReportSignal | None = None
    investment_thesis: str | None = None
    key_takeaways: list[str] = Field(default_factory=list)


# --- Financial ----------------------------------------------------------------------


class ReportFinancialMetric(BaseModel):
    name: str
    value: Decimal | None
    unit: str | None
    status: str
    reason: str | None = None
    source_periods: list[str] = Field(default_factory=list)
    formatted_value: str | None = None


class ReportFinancialSection(BaseModel):
    source: str = "financial_analysis"
    periods_analyzed: list[str] = Field(default_factory=list)
    profitability: list[ReportFinancialMetric] = Field(default_factory=list)
    growth: list[ReportFinancialMetric] = Field(default_factory=list)
    financial_health: list[ReportFinancialMetric] = Field(default_factory=list)
    cash_flow: list[ReportFinancialMetric] = Field(default_factory=list)
    other: list[ReportFinancialMetric] = Field(default_factory=list)


# --- Valuation ------------------------------------------------------------------------


class ReportValuationMethod(BaseModel):
    method: str
    value_per_share: Decimal | None
    status: str
    reason: str | None = None
    upside_downside_percent: Decimal | None = None
    upside_downside_status: str | None = None
    assumptions: dict[str, str] = Field(default_factory=dict)
    formatted_value_per_share: str | None = None
    formatted_upside_downside: str | None = None


class ReportValuationSection(BaseModel):
    source: str = "valuation"
    current_share_price: Decimal | None = None
    formatted_current_share_price: str | None = None
    methods: list[ReportValuationMethod] = Field(default_factory=list)


# --- Scoring --------------------------------------------------------------------------


class ReportScoreComponent(BaseModel):
    name: str
    score: Decimal | None
    weight: Decimal
    status: str
    reason: str | None = None


class ReportCategoryScore(BaseModel):
    category: str
    score: Decimal | None
    weight: Decimal
    status: str
    band: str | None = None
    reason: str | None = None
    components: list[ReportScoreComponent] = Field(default_factory=list)


class ReportScoringSection(BaseModel):
    source: str = "scoring"
    overall_score: Decimal | None
    overall_status: str
    band: str | None = None
    categories: list[ReportCategoryScore] = Field(default_factory=list)


# --- Risk -----------------------------------------------------------------------------


class ReportRiskIndicator(BaseModel):
    name: str
    severity: str | None
    status: str
    value: Decimal | None
    threshold: Decimal | None
    reason: str


class ReportRiskSection(BaseModel):
    source: str = "scoring"
    critical: list[ReportRiskIndicator] = Field(default_factory=list)
    high: list[ReportRiskIndicator] = Field(default_factory=list)
    medium: list[ReportRiskIndicator] = Field(default_factory=list)
    low: list[ReportRiskIndicator] = Field(default_factory=list)
    informational: list[ReportRiskIndicator] = Field(default_factory=list)


# --- Research -------------------------------------------------------------------------


class ReportResearchItem(BaseModel):
    id: str
    title: str
    publisher: str | None
    published_at: str | None
    freshness: str
    relevance: Decimal | None
    summary: str | None
    url: str
    source_type: str


class ReportResearchSection(BaseModel):
    source: str = "research"
    available: bool
    items: list[ReportResearchItem] = Field(default_factory=list)


# --- Analyst --------------------------------------------------------------------------


class ReportAnalystCategoryAnalysis(BaseModel):
    category: str
    text: str
    evidence: AnalystEvidence = Field(default_factory=AnalystEvidence)


class ReportAnalystSection(BaseModel):
    source: str = "analyst"
    available: bool
    investment_thesis: str | None = None
    investment_thesis_evidence: AnalystEvidence | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    category_analysis: list[ReportAnalystCategoryAnalysis] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


# --- Forecast ---------------------------------------------------------------------------


class ReportForecastYear(BaseModel):
    year_offset: int
    value: Decimal | None
    status: str
    formatted_value: str | None = None


class ReportForecastMetric(BaseModel):
    name: str
    unit: str | None
    base_period: str | None
    base_value: Decimal | None
    historical_cagr_percent: Decimal | None
    status: str
    reason: str | None = None
    formatted_historical_cagr: str | None = None
    projections: list[ReportForecastYear] = Field(default_factory=list)


class ReportValuationScenario(BaseModel):
    scenario: str
    fcf_growth_rate: Decimal | None
    value_per_share: Decimal | None
    status: str
    reason: str | None = None
    formatted_value_per_share: str | None = None


class ReportPriceTrendPoint(BaseModel):
    day_offset: int
    date: str | None = None
    projected_price: Decimal | None
    formatted_projected_price: str | None = None


class ReportMovingAverage(BaseModel):
    window: int
    value: Decimal | None
    status: str
    reason: str | None = None
    formatted_value: str | None = None


class ReportMovingAverageCrossover(BaseModel):
    short_window: int
    long_window: int
    signal: str | None = None
    status: str
    reason: str | None = None


class ReportTechnicalMethod(BaseModel):
    method: str
    description: str
    projected_price: Decimal | None
    projection_days: int
    projected_date: str | None = None
    status: str
    reason: str | None = None
    formatted_projected_price: str | None = None


class ReportTechnicalSignal(BaseModel):
    """A deterministic, color-coded technical-trend signal derived from
    the already-computed moving-average crossover and price-vs-average
    position (see `app/reporting/technical_signal.py`). This is
    explicitly NOT a buy/sell/hold recommendation — it computes nothing
    new; it only labels a combination of signals that already exist."""

    label: str  # "bullish" | "bearish" | "neutral" | "mixed" | "unavailable"
    color: str  # "green" | "yellow" | "red" | "gray"
    reason: str


class ReportForecastSection(BaseModel):
    """Deterministic extrapolations of historical data — never a
    recommendation and never a single asserted price target. Every
    projected number carries the historical basis and/or growth-rate
    assumption it was derived from, so it stays as auditable as any
    other section."""

    source: str = "forecast"
    available: bool
    projection_years: int | None = None
    financial_metrics: list[ReportForecastMetric] = Field(default_factory=list)
    valuation_scenarios: list[ReportValuationScenario] = Field(default_factory=list)
    price_trend: list[ReportPriceTrendPoint] = Field(default_factory=list)
    price_trend_status: str | None = None
    price_trend_reason: str | None = None
    price_trend_disclaimer: str | None = None
    moving_averages: list[ReportMovingAverage] = Field(default_factory=list)
    crossover: ReportMovingAverageCrossover | None = None
    technical_methods: list[ReportTechnicalMethod] = Field(default_factory=list)
    technical_disclaimer: str | None = None
    technical_signal: ReportTechnicalSignal | None = None
    current_price: Decimal | None = None
    formatted_current_price: str | None = None


# --- Evidence / top-level report -------------------------------------------------------


class ReportEvidence(BaseModel):
    """All evidence references actually cited by the analyst, deduplicated
    and namespaced — mirrors `AnalystEvidence` but aggregated across every
    section for a single "Evidence / Sources" view."""

    financial: list[str] = Field(default_factory=list)
    valuation: list[str] = Field(default_factory=list)
    risk: list[str] = Field(default_factory=list)
    research: list[str] = Field(default_factory=list)


class InvestmentResearchReport(BaseModel):
    """The complete, structured, presentation-ready research report.

    `status` mirrors `CombinedAnalysisResult.status` exactly — the
    report never independently decides completeness. No field here is a
    buy/sell/hold recommendation or a fabricated score. `forecast` is
    the one section built from projected rather than reported numbers —
    every value in it is explicitly tied to a stated growth assumption
    or historical basis rather than asserted as a single target.
    """

    company: ReportCompany
    status: ReportStatus
    summary: ReportSummary
    financials: ReportFinancialSection | None = None
    valuation: ReportValuationSection | None = None
    scoring: ReportScoringSection | None = None
    risk: ReportRiskSection | None = None
    forecast: ReportForecastSection | None = None
    research: ReportResearchSection | None = None
    analyst: ReportAnalystSection | None = None
    evidence: ReportEvidence = Field(default_factory=ReportEvidence)
    warnings: list[ReportWarning] = Field(default_factory=list)
    metadata: ReportMetadata

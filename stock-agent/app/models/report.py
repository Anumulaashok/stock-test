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

    source: str  # "financial_analysis" | "valuation" | "scoring" | "research" | "analyst" | "pipeline" | "report"
    code: str | None = None
    message: str


class ReportSummary(BaseModel):
    overall_score: Decimal | None = None
    overall_status: str = "unavailable"
    score_band: str | None = None
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
    buy/sell/hold recommendation, a target price, or a fabricated score.
    """

    company: ReportCompany
    status: ReportStatus
    summary: ReportSummary
    financials: ReportFinancialSection | None = None
    valuation: ReportValuationSection | None = None
    scoring: ReportScoringSection | None = None
    risk: ReportRiskSection | None = None
    research: ReportResearchSection | None = None
    analyst: ReportAnalystSection | None = None
    evidence: ReportEvidence = Field(default_factory=ReportEvidence)
    warnings: list[ReportWarning] = Field(default_factory=list)
    metadata: ReportMetadata

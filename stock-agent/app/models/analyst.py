"""AI Analyst domain models.

The analyst is strictly an interpretation layer over already-calculated
deterministic results (Steps 2-4). Nothing here recalculates a metric,
score, or valuation, and nothing here represents a buy/sell/hold
recommendation — deliberately, there is no such field anywhere in this
module.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_statements import CompanyFinancials
from app.models.scoring import ScoringResult
from app.models.valuation import ValuationRange


# --- Structured, serializable context sent to the LLM ---------------------------
# Every field here is copied/reshaped from a deterministic result, never
# recomputed. Status/reason/warning fields are preserved so the model can
# see, and must respect, what is unavailable.


class AnalystCompanyContext(BaseModel):
    name: str
    ticker: str | None = None


class AnalystMetricContext(BaseModel):
    name: str
    value: Decimal | None
    unit: str | None
    status: str
    reason: str | None = None


class AnalystCategoryScoreContext(BaseModel):
    category: str
    score: Decimal | None
    status: str
    reason: str | None = None


class AnalystValuationMethodContext(BaseModel):
    method: str
    value_per_share: Decimal | None
    status: str
    reason: str | None = None
    upside_downside_percent: Decimal | None = None
    upside_downside_status: str | None = None


class AnalystRiskContext(BaseModel):
    name: str
    severity: str | None = None
    status: str
    reason: str


class AnalystContext(BaseModel):
    """The complete, serializable input given to the LLM.

    This is the *only* financial/valuation/scoring data the model ever
    sees — it is built once, deterministically, by `app/analyst/context.py`.
    """

    company: AnalystCompanyContext
    periods_analyzed: list[str] = Field(default_factory=list)

    financial_metrics: list[AnalystMetricContext] = Field(default_factory=list)
    financial_warnings: list[str] = Field(default_factory=list)

    current_share_price: Decimal | None = None
    valuation_methods: list[AnalystValuationMethodContext] = Field(default_factory=list)
    valuation_warnings: list[str] = Field(default_factory=list)

    overall_score: Decimal | None = None
    overall_status: str = "unavailable"
    band: str | None = None
    category_scores: list[AnalystCategoryScoreContext] = Field(default_factory=list)
    risk_indicators: list[AnalystRiskContext] = Field(default_factory=list)
    scoring_warnings: list[str] = Field(default_factory=list)


# --- Structured LLM output --------------------------------------------------------


class AnalystSection(BaseModel):
    """One narrative section, with evidence traceable back to `AnalystContext`.

    `evidence` holds names (metric/category/risk-indicator names) that
    must exist in the `AnalystContext` that produced this response —
    validated by the response parser, never trusted blindly.
    """

    text: str
    evidence: list[str] = Field(default_factory=list)


class AnalystResponse(BaseModel):
    """The AI analyst's structured output.

    Deliberately has no recommendation/buy/sell/hold field — the analyst
    explains deterministic evidence, it does not issue a decision.
    """

    company_name: str
    investment_thesis: AnalystSection
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    profitability_analysis: AnalystSection
    growth_analysis: AnalystSection
    financial_health_analysis: AnalystSection
    cash_flow_analysis: AnalystSection
    valuation_analysis: AnalystSection
    risk_analysis: AnalystSection
    key_takeaways: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class AnalystErrorCode(StrEnum):
    LLM_UNAVAILABLE = "llm_unavailable"
    TIMEOUT = "timeout"
    EMPTY_RESPONSE = "empty_response"
    MALFORMED_JSON = "malformed_json"
    MISSING_FIELD = "missing_field"
    INVALID_FIELD_TYPE = "invalid_field_type"
    UNEXPECTED_RECOMMENDATION_FIELD = "unexpected_recommendation_field"
    MISSING_DETERMINISTIC_INPUTS = "missing_deterministic_inputs"


class AnalystError(BaseModel):
    code: AnalystErrorCode
    message: str


class AnalystResult(BaseModel):
    """The outcome of an analyst run: exactly one of `response`/`error` is set.

    An LLM failure is never silently turned into an apparently valid
    analysis — callers must check `status` before reading `response`.
    """

    status: str  # "success" | "error"
    response: AnalystResponse | None = None
    error: AnalystError | None = None


class AnalystRequest(BaseModel):
    """Bundles the deterministic inputs the analyst consumes.

    Used by the API layer to accept already-computed domain models —
    never raw numbers the LLM would need to calculate from.
    """

    financial_analysis: FinancialAnalysisResult
    valuation: ValuationRange | None = None
    scoring: ScoringResult
    company_financials: CompanyFinancials | None = None

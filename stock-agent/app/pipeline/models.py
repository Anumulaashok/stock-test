"""Pipeline domain models: request, status, and combined result.

`AnalysisRequest` is the only input shape the pipeline accepts — the
caller supplies `CompanyFinancials` plus explicit valuation assumptions.
The pipeline never fetches data itself and never invents a missing
assumption (see `app/pipeline/adapters.py`).
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.analyst import AnalystResult
from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_statements import CompanyFinancials
from app.models.forecasting import ForecastResult
from app.models.market import HistoricalPricePoint
from app.models.report import InvestmentResearchReport
from app.models.research import ResearchResult
from app.models.scoring import ScoringResult
from app.models.valuation import ValuationRange


class ResearchOptions(BaseModel):
    """Research enrichment (Step 8) is opt-in per request — `enabled`
    defaults to `False` so existing callers are unaffected and no
    external research API call happens unless explicitly requested.
    `days`/`max_results` of `None` mean "use the research service's
    configured default"."""

    enabled: bool = False
    days: int | None = None
    max_results: int | None = None


class ValuationAssumptions(BaseModel):
    """Valuation assumptions/market data the deterministic engines cannot
    derive on their own (discount rate, target multiples, ...), or
    optional overrides for values that *can* be derived from a company's
    latest reported period (shares outstanding, total debt, cash, EPS) —
    see `adapters.build_valuation_input`. `ebitda` has no source in
    `CompanyFinancials` at all, so it must always come from the caller
    if EV/EBITDA valuation is desired.

    Shared by `AnalysisRequest` (caller supplies `CompanyFinancials`
    directly) and `TickerAnalysisRequest` (Step 7: statements are fetched
    from an external provider) so both request shapes stay identical
    apart from how financial statement data is obtained.
    """

    current_share_price: Decimal | None = None
    shares_outstanding: Decimal | None = None
    total_debt: Decimal | None = None
    cash: Decimal | None = None
    eps: Decimal | None = None
    ebitda: Decimal | None = None

    fcf_growth_rate: Decimal | None = None
    discount_rate: Decimal | None = None
    terminal_growth_rate: Decimal | None = None
    projection_years: int | None = None
    target_pe: Decimal | None = None
    target_ev_ebitda: Decimal | None = None
    target_pfcf: Decimal | None = None

    recent_prices: list[HistoricalPricePoint] = Field(
        default_factory=list,
        description="Optional recent closing-price history, used only by the "
        "forecasting stage's price-trend extrapolation. An explicit value here "
        "always wins over any fetch.",
    )
    include_price_trend_forecast: bool = Field(
        default=False,
        description="Opt-in, like `research.enabled`: fetching price history is "
        "an extra provider call, so ticker analysis only makes it when the "
        "caller actually wants a price-trend forecast.",
    )

    research: ResearchOptions = Field(default_factory=ResearchOptions)
    include_report: bool = Field(
        default=False,
        description="If true, the API attaches a structured InvestmentResearchReport "
        "(Step 9) built from this result — the pipeline itself is unaware of reports.",
    )


class AnalysisRequest(ValuationAssumptions):
    """Everything the pipeline needs to analyze one company, with
    caller-supplied financial statements."""

    company_name: str
    ticker: str | None = None
    company_financials: CompanyFinancials


class TickerAnalysisRequest(ValuationAssumptions):
    """Requests analysis for a company by ticker — financial statements
    are fetched from the configured external data provider (Step 7)
    rather than supplied directly."""

    ticker: str


class PipelineStatus(StrEnum):
    CALCULATED = "calculated"
    PARTIAL = "partial"
    FAILED = "failed"


class PipelineCompanyInfo(BaseModel):
    name: str
    ticker: str | None = None


class ExecutionMetadata(BaseModel):
    """Lightweight, non-sensitive execution info. Never includes credentials
    or LLM reasoning — only timing."""

    pipeline_version: str = "1.0"
    started_at: str
    completed_at: str
    duration_ms: int


class CombinedAnalysisResult(BaseModel):
    """The full pipeline output.

    `status` distinguishes a fully successful run (`calculated`) from one
    where the deterministic stages succeeded but the AI analyst did not
    (`partial`, deterministic results still present and usable) from one
    where a required deterministic stage itself failed (`failed`).
    """

    company: PipelineCompanyInfo
    status: PipelineStatus
    financial_analysis: FinancialAnalysisResult | None = None
    valuation: ValuationRange | None = None
    scoring: ScoringResult | None = None
    forecast: ForecastResult | None = None
    research: ResearchResult | None = None
    analyst: AnalystResult | None = None
    report: InvestmentResearchReport | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: ExecutionMetadata | None = None

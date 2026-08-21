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
from app.models.scoring import ScoringResult
from app.models.valuation import ValuationRange


class AnalysisRequest(BaseModel):
    """Everything the pipeline needs to analyze one company.

    Fields below `company_financials` are valuation assumptions/market
    data the deterministic engines cannot derive on their own (discount
    rate, target multiples, ...), or optional overrides for values that
    *can* be derived from `company_financials`' latest period (shares
    outstanding, total debt, cash, EPS) — see `adapters.build_valuation_input`.
    `ebitda` has no source in `CompanyFinancials` at all, so it must
    always come from the caller if EV/EBITDA valuation is desired.
    """

    company_name: str
    ticker: str | None = None
    company_financials: CompanyFinancials

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
    analyst: AnalystResult | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: ExecutionMetadata | None = None

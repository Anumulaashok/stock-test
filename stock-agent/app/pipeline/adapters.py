"""Adapters that reshape pipeline input for the existing deterministic
services, without performing any calculation themselves.

`build_valuation_input` is the only adapter needed today: it assembles a
`ValuationInput` from the request plus the already-computed
`FinancialAnalysisResult`. Every field is either an explicit value the
caller supplied, or a value copied verbatim from the company's latest
reported period — never invented, never estimated.
"""

from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_results import MetricStatus as FinancialMetricStatus
from app.models.financial_statements import BalanceSheet, CompanyFinancials, IncomeStatement
from app.models.valuation import ValuationInput
from app.pipeline.models import AnalysisRequest


def _latest_statements(
    company_financials: CompanyFinancials, periods_analyzed: list[str]
) -> tuple[IncomeStatement | None, BalanceSheet | None]:
    """The income statement and balance sheet for the most recent period
    `FinancialAnalysisResult` actually analyzed (already chronologically
    sorted by Step 2) — not recomputed here, only looked up."""
    if not periods_analyzed:
        return None, None
    latest_period = periods_analyzed[-1]
    income = next(
        (s for s in company_financials.income_statements if s.period == latest_period), None
    )
    balance = next(
        (s for s in company_financials.balance_sheets if s.period == latest_period), None
    )
    return income, balance


def _latest_free_cash_flow(financial_analysis: FinancialAnalysisResult):
    """The FCF Step 2 already computed for the latest period (respecting
    its stated-vs-derived fallback policy) — never recalculated here."""
    metric = next((m for m in financial_analysis.metrics if m.name == "free_cash_flow"), None)
    if metric is None or metric.status is not FinancialMetricStatus.CALCULATED:
        return None
    return metric.value


def build_valuation_input(
    request: AnalysisRequest, financial_analysis: FinancialAnalysisResult
) -> ValuationInput:
    """Assemble a `ValuationInput` for `ValuationService`.

    An explicit value on `request` always wins; otherwise the
    corresponding field is filled from the company's latest reported
    period where one exists in `CompanyFinancials`. Assumptions with no
    such source (discount rate, terminal growth, target multiples,
    EBITDA, current price) are passed through only if the caller
    supplied them — never defaulted.
    """
    income, balance = _latest_statements(
        request.company_financials, financial_analysis.periods_analyzed
    )

    def prefer(explicit, derived):
        return explicit if explicit is not None else derived

    return ValuationInput(
        company_name=request.company_name,
        current_share_price=request.current_share_price,
        shares_outstanding=prefer(
            request.shares_outstanding, income.shares_outstanding if income else None
        ),
        free_cash_flow=_latest_free_cash_flow(financial_analysis),
        revenue=income.revenue if income else None,
        ebitda=request.ebitda,
        net_income=income.net_income if income else None,
        eps=prefer(request.eps, income.eps if income else None),
        total_debt=prefer(request.total_debt, balance.total_debt if balance else None),
        cash=prefer(request.cash, balance.cash_and_equivalents if balance else None),
        fcf_growth_rate=request.fcf_growth_rate,
        discount_rate=request.discount_rate,
        terminal_growth_rate=request.terminal_growth_rate,
        projection_years=request.projection_years,
        target_pe=request.target_pe,
        target_ev_ebitda=request.target_ev_ebitda,
        target_pfcf=request.target_pfcf,
    )

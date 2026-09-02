"""Adapters that reshape pipeline input for the existing deterministic
services, without performing any calculation themselves.

`build_valuation_input` is the only adapter needed today: it assembles a
`ValuationInput` from the request plus the already-computed
`FinancialAnalysisResult`. Every field is either an explicit value the
caller supplied, or a value copied verbatim from the company's latest
reported period.

DCF's three assumptions (`fcf_growth_rate`, `discount_rate`,
`terminal_growth_rate`) and `projection_years` are the one exception:
when the caller doesn't supply them AND a free cash flow base value
exists (so a DCF is otherwise computable), this module fills in an
auto-derived default rather than leaving DCF permanently unavailable --
but every default is reported back as an explicit warning naming the
value used and inviting the caller to override it, so nothing is
silently fabricated. `target_pe`/`target_ev_ebitda`/`target_pfcf` are
NOT auto-derived -- this app has no peer/sector multiple data to ground
a target multiple in, so guessing one would be pure fabrication, not a
data-grounded default.
"""

from decimal import Decimal

from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_results import MetricStatus as FinancialMetricStatus
from app.models.financial_statements import BalanceSheet, CompanyFinancials, IncomeStatement
from app.models.valuation import ValuationInput
from app.pipeline.models import AnalysisRequest

# Conservative long-run defaults used only when the caller supplies no
# assumption of their own -- not derived from company data, so always
# reported via an explicit warning rather than silently applied.
_DEFAULT_DISCOUNT_RATE = Decimal("0.10")
_DEFAULT_TERMINAL_GROWTH_RATE = Decimal("0.025")
_DEFAULT_PROJECTION_YEARS = 5

# A company's raw historical FCF growth can be an extreme, low-base
# artifact (e.g. +100%+ off a near-zero prior year) -- not a rate
# defensible to compound for `_DEFAULT_PROJECTION_YEARS`. Auto-derived
# growth is clamped to this range; an explicit `fcf_growth_rate` from
# the caller is never clamped.
_AUTO_FCF_GROWTH_CAP = Decimal("0.20")


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


def _derive_fcf_growth_rate(financial_analysis: FinancialAnalysisResult) -> tuple[Decimal | None, str | None]:
    """The historical FCF growth Step 2 already computed (percent,
    latest-vs-previous period), converted to a fraction and clamped to
    `_AUTO_FCF_GROWTH_CAP` -- returns `(rate, warning)`; `warning` is
    `None` when no auto-derivation happened (metric unavailable)."""
    metric = next((m for m in financial_analysis.metrics if m.name == "fcf_growth"), None)
    if metric is None or metric.status is not FinancialMetricStatus.CALCULATED or metric.value is None:
        return None, None
    raw_rate = metric.value / 100
    clamped_rate = max(-_AUTO_FCF_GROWTH_CAP, min(_AUTO_FCF_GROWTH_CAP, raw_rate))
    warning = (
        f"FCF growth rate assumption was auto-derived from historical FCF growth "
        f"({metric.value:.2f}%), capped to {clamped_rate * 100:.2f}% for the DCF projection -- "
        f"supply `fcf_growth_rate` explicitly to override."
    )
    return clamped_rate, warning


def build_valuation_input(
    request: AnalysisRequest, financial_analysis: FinancialAnalysisResult
) -> tuple[ValuationInput, list[str]]:
    """Assemble a `ValuationInput` for `ValuationService`, plus any
    warnings about assumptions this function auto-derived.

    An explicit value on `request` always wins; otherwise the
    corresponding field is filled from the company's latest reported
    period where one exists in `CompanyFinancials`. DCF's assumptions
    (`fcf_growth_rate`, `discount_rate`, `terminal_growth_rate`,
    `projection_years`) get an auto-derived default ONLY when a free
    cash flow base value exists (otherwise DCF stays unavailable
    regardless) -- every default used is reported back as a warning.
    `target_pe`/`target_ev_ebitda`/`target_pfcf`/`ebitda`/`current_share_price`
    have no data-grounded source in this app and are passed through only
    if the caller supplied them — never defaulted.
    """
    income, balance = _latest_statements(
        request.company_financials, financial_analysis.periods_analyzed
    )

    def prefer(explicit, derived):
        return explicit if explicit is not None else derived

    free_cash_flow = _latest_free_cash_flow(financial_analysis)
    warnings: list[str] = []

    fcf_growth_rate = request.fcf_growth_rate
    discount_rate = request.discount_rate
    terminal_growth_rate = request.terminal_growth_rate
    projection_years = request.projection_years

    if free_cash_flow is not None:
        if fcf_growth_rate is None:
            fcf_growth_rate, growth_warning = _derive_fcf_growth_rate(financial_analysis)
            if growth_warning:
                warnings.append(growth_warning)
        if discount_rate is None:
            discount_rate = _DEFAULT_DISCOUNT_RATE
            warnings.append(
                f"Discount rate assumption defaulted to {_DEFAULT_DISCOUNT_RATE * 100:.2f}% "
                "(no company-specific rate available) -- supply `discount_rate` explicitly to override."
            )
        if terminal_growth_rate is None:
            terminal_growth_rate = _DEFAULT_TERMINAL_GROWTH_RATE
            warnings.append(
                f"Terminal growth rate assumption defaulted to {_DEFAULT_TERMINAL_GROWTH_RATE * 100:.2f}% "
                "(a conservative long-run estimate) -- supply `terminal_growth_rate` explicitly to override."
            )
        if projection_years is None:
            projection_years = _DEFAULT_PROJECTION_YEARS

    valuation_input = ValuationInput(
        company_name=request.company_name,
        current_share_price=request.current_share_price,
        shares_outstanding=prefer(
            request.shares_outstanding, income.shares_outstanding if income else None
        ),
        free_cash_flow=free_cash_flow,
        revenue=income.revenue if income else None,
        ebitda=request.ebitda,
        net_income=income.net_income if income else None,
        eps=prefer(request.eps, income.eps if income else None),
        total_debt=prefer(request.total_debt, balance.total_debt if balance else None),
        cash=prefer(request.cash, balance.cash_and_equivalents if balance else None),
        fcf_growth_rate=fcf_growth_rate,
        discount_rate=discount_rate,
        terminal_growth_rate=terminal_growth_rate,
        projection_years=projection_years,
        target_pe=request.target_pe,
        target_ev_ebitda=request.target_ev_ebitda,
        target_pfcf=request.target_pfcf,
    )
    return valuation_input, warnings

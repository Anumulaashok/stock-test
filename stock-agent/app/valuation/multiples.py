"""Comparable-multiple valuation methods (P/E, EV/EBITDA, P/FCF).

All pure and deterministic — the caller supplies the target multiple
(e.g. from peer comparables); this module never invents one.
"""

from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.models.valuation import ValuationResult


def calculate_pe_valuation(eps: Decimal | None, target_pe: Decimal | None) -> ValuationResult:
    """P/E valuation: estimated value per share = EPS * target P/E."""
    method = "pe"
    assumptions = {"target_pe": target_pe}

    if eps is None:
        return ValuationResult(
            method=method, value_per_share=None, status=MetricStatus.UNAVAILABLE,
            reason="EPS is missing", assumptions=assumptions,
        )
    if target_pe is None:
        return ValuationResult(
            method=method, value_per_share=None, status=MetricStatus.UNAVAILABLE,
            reason="target P/E multiple is missing", assumptions=assumptions,
        )
    if target_pe <= 0:
        return ValuationResult(
            method=method, value_per_share=None, status=MetricStatus.INVALID,
            reason="target P/E multiple must be positive", assumptions=assumptions,
        )

    value_per_share = eps * target_pe
    return ValuationResult(
        method=method, value_per_share=value_per_share, status=MetricStatus.CALCULATED,
        assumptions=assumptions,
    )


def calculate_ev_ebitda_valuation(
    ebitda: Decimal | None,
    target_ev_ebitda: Decimal | None,
    total_debt: Decimal | None,
    cash: Decimal | None,
    shares_outstanding: Decimal | None,
) -> ValuationResult:
    """EV/EBITDA valuation.

    Enterprise value = EBITDA * target EV/EBITDA multiple.
    Equity value = enterprise value - total debt + cash.
    Value per share = equity value / shares outstanding.
    """
    method = "ev_ebitda"
    assumptions = {"target_ev_ebitda": target_ev_ebitda}

    def _unavailable(reason: str) -> ValuationResult:
        return ValuationResult(
            method=method, value_per_share=None, status=MetricStatus.UNAVAILABLE,
            reason=reason, assumptions=assumptions,
        )

    def _invalid(reason: str) -> ValuationResult:
        return ValuationResult(
            method=method, value_per_share=None, status=MetricStatus.INVALID,
            reason=reason, assumptions=assumptions,
        )

    if ebitda is None:
        return _unavailable("EBITDA is missing")
    if target_ev_ebitda is None:
        return _unavailable("target EV/EBITDA multiple is missing")
    if total_debt is None:
        return _unavailable("total debt is missing")
    if cash is None:
        return _unavailable("cash is missing")
    if shares_outstanding is None:
        return _unavailable("shares outstanding is missing")

    if target_ev_ebitda <= 0:
        return _invalid("target EV/EBITDA multiple must be positive")
    if shares_outstanding <= 0:
        return _invalid("shares outstanding must be positive")

    enterprise_value = ebitda * target_ev_ebitda
    equity_value = enterprise_value - total_debt + cash
    value_per_share = equity_value / shares_outstanding

    return ValuationResult(
        method=method, value_per_share=value_per_share, status=MetricStatus.CALCULATED,
        assumptions=assumptions,
    )


def calculate_pfcf_valuation(
    free_cash_flow: Decimal | None,
    target_pfcf: Decimal | None,
    shares_outstanding: Decimal | None,
) -> ValuationResult:
    """P/FCF valuation.

    FCF per share = free cash flow / shares outstanding.
    Value per share = FCF per share * target P/FCF multiple.
    """
    method = "pfcf"
    assumptions = {"target_pfcf": target_pfcf}

    def _unavailable(reason: str) -> ValuationResult:
        return ValuationResult(
            method=method, value_per_share=None, status=MetricStatus.UNAVAILABLE,
            reason=reason, assumptions=assumptions,
        )

    def _invalid(reason: str) -> ValuationResult:
        return ValuationResult(
            method=method, value_per_share=None, status=MetricStatus.INVALID,
            reason=reason, assumptions=assumptions,
        )

    if free_cash_flow is None:
        return _unavailable("free cash flow is missing")
    if target_pfcf is None:
        return _unavailable("target P/FCF multiple is missing")
    if shares_outstanding is None:
        return _unavailable("shares outstanding is missing")

    if target_pfcf <= 0:
        return _invalid("target P/FCF multiple must be positive")
    if shares_outstanding <= 0:
        return _invalid("shares outstanding must be positive")

    fcf_per_share = free_cash_flow / shares_outstanding
    value_per_share = fcf_per_share * target_pfcf

    return ValuationResult(
        method=method, value_per_share=value_per_share, status=MetricStatus.CALCULATED,
        assumptions=assumptions,
    )

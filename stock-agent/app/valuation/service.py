"""Valuation service.

Wires a `ValuationInput` through every available valuation method and
assembles a `ValuationRange` — each method's result kept separate, never
averaged or blended. This is the only "orchestration" logic in the
valuation package; the actual math lives in `dcf.py` and `multiples.py`.
"""

from app.models.financial_results import MetricStatus
from app.models.valuation import ValuationInput, ValuationRange, ValuationResult
from app.valuation.common import calculate_upside_downside
from app.valuation.dcf import calculate_dcf
from app.valuation.multiples import (
    calculate_ev_ebitda_valuation,
    calculate_pe_valuation,
    calculate_pfcf_valuation,
)


def _with_upside_downside(result: ValuationResult, current_price) -> ValuationResult:
    if result.status is not MetricStatus.CALCULATED:
        return result
    upside = calculate_upside_downside(result.value_per_share, current_price)
    return result.model_copy(
        update={
            "upside_downside_percent": upside.value,
            "upside_downside_status": upside.status,
            "upside_downside_reason": upside.reason,
        }
    )


class ValuationService:
    """Runs every deterministic valuation method over a `ValuationInput`."""

    def analyze(self, valuation_input: ValuationInput) -> ValuationRange:
        results = [
            calculate_dcf(
                base_fcf=valuation_input.free_cash_flow,
                fcf_growth_rate=valuation_input.fcf_growth_rate,
                discount_rate=valuation_input.discount_rate,
                terminal_growth_rate=valuation_input.terminal_growth_rate,
                projection_years=valuation_input.projection_years,
                total_debt=valuation_input.total_debt,
                cash=valuation_input.cash,
                shares_outstanding=valuation_input.shares_outstanding,
            ),
            calculate_pe_valuation(
                eps=valuation_input.eps,
                target_pe=valuation_input.target_pe,
            ),
            calculate_ev_ebitda_valuation(
                ebitda=valuation_input.ebitda,
                target_ev_ebitda=valuation_input.target_ev_ebitda,
                total_debt=valuation_input.total_debt,
                cash=valuation_input.cash,
                shares_outstanding=valuation_input.shares_outstanding,
            ),
            calculate_pfcf_valuation(
                free_cash_flow=valuation_input.free_cash_flow,
                target_pfcf=valuation_input.target_pfcf,
                shares_outstanding=valuation_input.shares_outstanding,
            ),
        ]

        results = [
            _with_upside_downside(result, valuation_input.current_share_price)
            for result in results
        ]

        return ValuationRange(
            company=valuation_input.company_name,
            current_share_price=valuation_input.current_share_price,
            results=results,
        )

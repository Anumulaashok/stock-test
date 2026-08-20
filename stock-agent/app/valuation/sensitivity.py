"""DCF sensitivity analysis.

Runs `calculate_dcf` once per (discount rate, terminal growth rate)
combination and returns a structured matrix. This is purely a
reapplication of the DCF formula across an assumption grid — no new
math, no I/O, and no rendering (the caller decides how to display it).
"""

from decimal import Decimal

from app.models.valuation import SensitivityCell, SensitivityMatrix
from app.valuation.dcf import calculate_dcf


def calculate_dcf_sensitivity(
    base_fcf: Decimal | None,
    fcf_growth_rate: Decimal | None,
    projection_years: int | None,
    total_debt: Decimal | None,
    cash: Decimal | None,
    shares_outstanding: Decimal | None,
    discount_rates: list[Decimal],
    terminal_growth_rates: list[Decimal],
) -> SensitivityMatrix:
    """Evaluate the DCF across every (discount_rate, terminal_growth_rate) pair."""
    cells: list[SensitivityCell] = []
    for discount_rate in discount_rates:
        for terminal_growth_rate in terminal_growth_rates:
            result = calculate_dcf(
                base_fcf=base_fcf,
                fcf_growth_rate=fcf_growth_rate,
                discount_rate=discount_rate,
                terminal_growth_rate=terminal_growth_rate,
                projection_years=projection_years,
                total_debt=total_debt,
                cash=cash,
                shares_outstanding=shares_outstanding,
            )
            cells.append(
                SensitivityCell(
                    discount_rate=discount_rate,
                    terminal_growth_rate=terminal_growth_rate,
                    value_per_share=result.value_per_share,
                    status=result.status,
                    reason=result.reason,
                )
            )

    return SensitivityMatrix(
        discount_rates=discount_rates,
        terminal_growth_rates=terminal_growth_rates,
        cells=cells,
    )

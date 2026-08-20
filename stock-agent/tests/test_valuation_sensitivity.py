from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.valuation.sensitivity import calculate_dcf_sensitivity


def d(value) -> Decimal:
    return Decimal(str(value))


def test_sensitivity_matrix_shape_and_values():
    matrix = calculate_dcf_sensitivity(
        base_fcf=d(100),
        fcf_growth_rate=d("0.10"),
        projection_years=1,
        total_debt=d(50),
        cash=d(20),
        shares_outstanding=d(10),
        discount_rates=[d("0.20"), d("0.25")],
        terminal_growth_rates=[d("0.03"), d("0.05")],
    )

    assert matrix.discount_rates == [d("0.20"), d("0.25")]
    assert matrix.terminal_growth_rates == [d("0.03"), d("0.05")]
    assert len(matrix.cells) == 4

    match = [
        c
        for c in matrix.cells
        if c.discount_rate == d("0.25") and c.terminal_growth_rate == d("0.05")
    ]
    assert len(match) == 1
    cell = match[0]
    assert cell.status is MetricStatus.CALCULATED
    assert cell.value_per_share == d("54.2")  # matches the hand-calculated DCF example


def test_sensitivity_matrix_reports_invalid_combinations():
    matrix = calculate_dcf_sensitivity(
        base_fcf=d(100),
        fcf_growth_rate=d("0.10"),
        projection_years=1,
        total_debt=d(50),
        cash=d(20),
        shares_outstanding=d(10),
        discount_rates=[d("0.05")],
        terminal_growth_rates=[d("0.08")],  # >= discount rate
    )
    assert len(matrix.cells) == 1
    assert matrix.cells[0].status is MetricStatus.INVALID
    assert matrix.cells[0].value_per_share is None

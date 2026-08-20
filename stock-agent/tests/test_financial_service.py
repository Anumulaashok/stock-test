from decimal import Decimal

from app.financial.service import FinancialAnalysisService
from app.models.financial_results import MetricStatus
from app.models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFinancials,
    IncomeStatement,
)


def d(value) -> Decimal:
    return Decimal(str(value))


def _metric(result, name):
    matches = [m for m in result.metrics if m.name == name]
    assert len(matches) == 1, f"expected exactly one '{name}' metric, found {len(matches)}"
    return matches[0]


def test_analyze_two_periods_computes_growth_and_ratios():
    financials = CompanyFinancials(
        company_name="Acme Corp",
        ticker="ACME",
        income_statements=[
            IncomeStatement(
                period="FY2024",
                revenue=d(100),
                gross_profit=d(40),
                operating_income=d(20),
                net_income=d(10),
                interest_expense=d(2),
                tax_expense=d(3),
                eps=d("1.00"),
            ),
            IncomeStatement(
                period="FY2025",
                revenue=d(120),
                gross_profit=d(50),
                operating_income=d(25),
                net_income=d(15),
                interest_expense=d(2),
                tax_expense=d(4),
                eps=d("1.50"),
            ),
        ],
        balance_sheets=[
            BalanceSheet(
                period="FY2024",
                total_assets=d(200),
                current_assets=d(80),
                cash_and_equivalents=d(30),
                current_liabilities=d(40),
                total_debt=d(50),
                shareholders_equity=d(100),
            ),
            BalanceSheet(
                period="FY2025",
                total_assets=d(220),
                current_assets=d(90),
                cash_and_equivalents=d(35),
                current_liabilities=d(45),
                total_debt=d(55),
                shareholders_equity=d(120),
            ),
        ],
        cash_flow_statements=[
            CashFlowStatement(period="FY2024", operating_cash_flow=d(30), capital_expenditure=d(10)),
            CashFlowStatement(period="FY2025", operating_cash_flow=d(40), capital_expenditure=d(15)),
        ],
    )

    result = FinancialAnalysisService().analyze(financials)

    assert result.company == "Acme Corp"
    assert result.periods_analyzed == ["FY2024", "FY2025"]
    assert result.warnings == []

    revenue_growth = _metric(result, "revenue_growth")
    assert revenue_growth.status is MetricStatus.CALCULATED
    assert revenue_growth.value == d(20)
    assert revenue_growth.source_periods == ["FY2024", "FY2025"]

    fcf = _metric(result, "free_cash_flow")
    assert fcf.status is MetricStatus.CALCULATED
    assert fcf.value == d(25)  # 40 - 15, derived (no stated FCF given)

    roe = _metric(result, "roe")
    assert roe.status is MetricStatus.CALCULATED
    assert roe.value == d(15) / d(120) * d(100)


def test_analyze_handles_unsorted_input_periods():
    financials = CompanyFinancials(
        company_name="Acme Corp",
        income_statements=[
            IncomeStatement(period="FY2025", revenue=d(120)),
            IncomeStatement(period="FY2023", revenue=d(80)),
            IncomeStatement(period="FY2024", revenue=d(100)),
        ],
    )

    result = FinancialAnalysisService().analyze(financials)

    assert result.periods_analyzed == ["FY2023", "FY2024", "FY2025"]
    # Growth must compare FY2024 -> FY2025 (the latest two), not input order.
    revenue_growth = _metric(result, "revenue_growth")
    assert revenue_growth.value == d(20)
    assert revenue_growth.source_periods == ["FY2024", "FY2025"]


def test_analyze_single_period_marks_growth_unavailable_with_warning():
    financials = CompanyFinancials(
        company_name="Acme Corp",
        income_statements=[IncomeStatement(period="FY2024", revenue=d(100), net_income=d(10))],
    )

    result = FinancialAnalysisService().analyze(financials)

    assert any("Only one fiscal period" in w for w in result.warnings)
    for name in ("revenue_growth", "net_income_growth", "eps_growth", "fcf_growth"):
        metric = _metric(result, name)
        assert metric.status is MetricStatus.UNAVAILABLE
        assert metric.value is None


def test_analyze_no_data_returns_empty_result_with_warning():
    financials = CompanyFinancials(company_name="Empty Co")

    result = FinancialAnalysisService().analyze(financials)

    assert result.periods_analyzed == []
    assert result.metrics == []
    assert result.warnings == ["No financial statement data was provided."]


def test_analyze_missing_balance_sheet_for_latest_period_reports_unavailable():
    financials = CompanyFinancials(
        company_name="Acme Corp",
        income_statements=[
            IncomeStatement(period="FY2024", revenue=d(100), net_income=d(10)),
        ],
        balance_sheets=[],
    )

    result = FinancialAnalysisService().analyze(financials)

    roe = _metric(result, "roe")
    assert roe.status is MetricStatus.UNAVAILABLE
    assert "equity" in roe.reason


def test_analyze_uses_stated_fcf_over_derived_when_present():
    financials = CompanyFinancials(
        company_name="Acme Corp",
        cash_flow_statements=[
            CashFlowStatement(
                period="FY2024",
                operating_cash_flow=d(100),
                capital_expenditure=d(20),
                free_cash_flow=d(999),
            )
        ],
    )

    result = FinancialAnalysisService().analyze(financials)

    fcf = _metric(result, "free_cash_flow")
    assert fcf.value == d(999)

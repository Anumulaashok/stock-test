"""Normalized financial statement models.

These represent input data to the financial calculation engine
(`app/financial/`). Real-world financial data is frequently incomplete,
so every line item except `period` is optional — callers may supply
whatever they have and the calculation engine reports individual
metrics as unavailable rather than guessing.
"""

from decimal import Decimal

from pydantic import BaseModel, Field


class IncomeStatement(BaseModel):
    """A single fiscal period's income statement."""

    period: str = Field(description="Fiscal period label, e.g. 'FY2024' or '2024-Q4'.")
    revenue: Decimal | None = None
    cost_of_revenue: Decimal | None = None
    gross_profit: Decimal | None = None
    operating_income: Decimal | None = None
    net_income: Decimal | None = None
    interest_expense: Decimal | None = None
    tax_expense: Decimal | None = None
    shares_outstanding: Decimal | None = None
    eps: Decimal | None = None


class BalanceSheet(BaseModel):
    """A single fiscal period's balance sheet, as of period end."""

    period: str = Field(description="Fiscal period label, e.g. 'FY2024' or '2024-Q4'.")
    total_assets: Decimal | None = None
    current_assets: Decimal | None = None
    cash_and_equivalents: Decimal | None = None
    total_liabilities: Decimal | None = None
    current_liabilities: Decimal | None = None
    total_debt: Decimal | None = None
    shareholders_equity: Decimal | None = None


class CashFlowStatement(BaseModel):
    """A single fiscal period's cash flow statement.

    `capital_expenditure` is expected as a positive magnitude representing
    cash spent on capex. `free_cash_flow` may be supplied directly by the
    source data; when absent, the calculation engine derives it from
    `operating_cash_flow` and `capital_expenditure` where both are present.
    """

    period: str = Field(description="Fiscal period label, e.g. 'FY2024' or '2024-Q4'.")
    operating_cash_flow: Decimal | None = None
    capital_expenditure: Decimal | None = None
    free_cash_flow: Decimal | None = None
    dividends_paid: Decimal | None = None


class CompanyFinancials(BaseModel):
    """The normalized financial statement history for one company.

    Statement lists are not required to be in any particular order or to
    cover the same set of periods as one another — the calculation
    engine sorts and aligns periods itself.
    """

    company_name: str
    ticker: str | None = None
    fiscal_periods: list[str] = Field(
        default_factory=list,
        description="Optional, informational list of known fiscal period labels.",
    )
    income_statements: list[IncomeStatement] = Field(default_factory=list)
    balance_sheets: list[BalanceSheet] = Field(default_factory=list)
    cash_flow_statements: list[CashFlowStatement] = Field(default_factory=list)

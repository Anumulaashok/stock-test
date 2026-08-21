"""Maps IndianAPI's (stock.indianapi.in) raw JSON schema into `CompanyFinancials`.

Pure functions only — no HTTP. Verified against a real, live `/stock`
response (not assumed): each entry in the response's `financials` list
looks like:

    {
      "FiscalYear": 2026, "EndDate": "2026-03-31", "Type": "Annual",
      "stockFinancialMap": {
        "INC": [{"key": "Revenue", "value": "1075675.00", ...}, ...],
        "BAL": [{"key": "TotalAssets", "value": "2178140.00", ...}, ...],
        "CAS": [{"key": "CashfromOperatingActivities", "value": "192113.00", ...}, ...]
      }
    }

Only `"Type": "Annual"` entries are used (quarterly entries are marked
`"Interim"` and filtered out), matching this project's Step 7 decision
to support annual statements only for the first implementation.

Units: this provider's aggregate line items (revenue, profit, assets,
debt, cash, shares outstanding, ...) are reported in INR **Crore**,
uniformly, across every field — confirmed live by cross-referencing
Reliance Industries' real-world revenue and share-count scale during
implementation. Per-share fields (EPS) are already absolute INR. No
conversion is applied here: because every aggregate field is
consistently Crore-scaled, downstream per-share math (equity value /
shares outstanding) still produces a correct absolute-INR result — the
scale factor cancels between numerator and denominator. This mapper
never re-derives EPS from net_income/shares_outstanding, which is the
one place that invariant would matter.

Currency: this endpoint does not report a currency field anywhere in
the response, so `CompanyFinancials.currency` is always left `None`
here rather than assumed to be "INR".
"""

from decimal import Decimal, InvalidOperation

from app.models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFinancials,
    IncomeStatement,
)


def _to_decimal(value: object, field_name: str, period: str, warnings: list[str]) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        warnings.append(f"{period}: '{field_name}' was not a valid number and was left unavailable")
        return None


def _positive_magnitude(value: Decimal | None) -> Decimal | None:
    return abs(value) if value is not None else None


def _is_annual(entry: dict) -> bool:
    return entry.get("Type") == "Annual"


def _extract_period(entry: dict, warnings: list[str]) -> str | None:
    fiscal_year = entry.get("FiscalYear")
    try:
        year = int(fiscal_year)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        warnings.append("skipped a statement record with no usable fiscal year")
        return None
    return f"FY{year}"


def _section_map(entry: dict, section: str) -> dict[str, object]:
    """Flattens one `stockFinancialMap` section's `[{key, value}, ...]`
    list into a `{key: value}` dict for simple lookup."""
    items = entry.get("stockFinancialMap", {})
    items = items.get(section) if isinstance(items, dict) else None
    if not isinstance(items, list):
        return {}
    result: dict[str, object] = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("key"), str):
            result[item["key"]] = item.get("value")
    return result


def _interest_expense(inc: dict[str, object], period: str, warnings: list[str]) -> Decimal | None:
    """This provider reports *net* interest income/expense as a single
    signed figure. A negative value is a net expense (magnitude
    returned); a non-negative value is net interest *income*, which our
    domain model has no field for — left unavailable rather than
    mislabeled as an expense of zero or of the wrong sign."""
    value = _to_decimal(inc.get("InterestInc(Exp)Net-Non-OpTotal"), "interest_expense", period, warnings)
    if value is None:
        return None
    if value < 0:
        return -value
    warnings.append(f"{period}: net interest was income, not expense; interest_expense left unavailable")
    return None


def _dedupe_by_period(items: list[tuple[str, object]], statement_kind: str, warnings: list[str]) -> list[object]:
    seen: dict[str, object] = {}
    for period, statement in items:
        if period in seen:
            warnings.append(
                f"duplicate {statement_kind} record for {period}; kept the first one returned"
            )
            continue
        seen[period] = statement
    return list(seen.values())


def map_income_statements(financials_raw: list[dict]) -> tuple[list[IncomeStatement], list[str]]:
    warnings: list[str] = []
    parsed: list[tuple[str, IncomeStatement]] = []
    for entry in financials_raw:
        if not _is_annual(entry):
            continue
        period = _extract_period(entry, warnings)
        if period is None:
            continue
        inc = _section_map(entry, "INC")
        revenue = inc.get("Revenue", inc.get("TotalRevenue"))
        parsed.append(
            (
                period,
                IncomeStatement(
                    period=period,
                    revenue=_to_decimal(revenue, "revenue", period, warnings),
                    cost_of_revenue=_to_decimal(inc.get("CostofRevenueTotal"), "cost_of_revenue", period, warnings),
                    gross_profit=_to_decimal(inc.get("GrossProfit"), "gross_profit", period, warnings),
                    operating_income=_to_decimal(inc.get("OperatingIncome"), "operating_income", period, warnings),
                    net_income=_to_decimal(inc.get("NetIncome"), "net_income", period, warnings),
                    interest_expense=_interest_expense(inc, period, warnings),
                    tax_expense=_to_decimal(inc.get("ProvisionforIncomeTaxes"), "tax_expense", period, warnings),
                    shares_outstanding=_to_decimal(
                        inc.get("DilutedWeightedAverageShares"), "shares_outstanding", period, warnings
                    ),
                    eps=_to_decimal(inc.get("DilutedNormalizedEPS"), "eps", period, warnings),
                ),
            )
        )
    return _dedupe_by_period(parsed, "income statement", warnings), warnings


def map_balance_sheets(financials_raw: list[dict]) -> tuple[list[BalanceSheet], list[str]]:
    warnings: list[str] = []
    parsed: list[tuple[str, BalanceSheet]] = []
    for entry in financials_raw:
        if not _is_annual(entry):
            continue
        period = _extract_period(entry, warnings)
        if period is None:
            continue
        bal = _section_map(entry, "BAL")
        parsed.append(
            (
                period,
                BalanceSheet(
                    period=period,
                    total_assets=_to_decimal(bal.get("TotalAssets"), "total_assets", period, warnings),
                    current_assets=_to_decimal(bal.get("TotalCurrentAssets"), "current_assets", period, warnings),
                    cash_and_equivalents=_to_decimal(bal.get("Cash"), "cash_and_equivalents", period, warnings),
                    total_liabilities=_to_decimal(bal.get("TotalLiabilities"), "total_liabilities", period, warnings),
                    current_liabilities=_to_decimal(
                        bal.get("TotalCurrentLiabilities"), "current_liabilities", period, warnings
                    ),
                    total_debt=_to_decimal(bal.get("TotalDebt"), "total_debt", period, warnings),
                    shareholders_equity=_to_decimal(
                        bal.get("TotalEquity"), "shareholders_equity", period, warnings
                    ),
                ),
            )
        )
    return _dedupe_by_period(parsed, "balance sheet", warnings), warnings


def map_cash_flow_statements(financials_raw: list[dict]) -> tuple[list[CashFlowStatement], list[str]]:
    warnings: list[str] = []
    parsed: list[tuple[str, CashFlowStatement]] = []
    for entry in financials_raw:
        if not _is_annual(entry):
            continue
        period = _extract_period(entry, warnings)
        if period is None:
            continue
        cas = _section_map(entry, "CAS")
        capex = _positive_magnitude(
            _to_decimal(cas.get("CapitalExpenditures"), "capital_expenditure", period, warnings)
        )
        dividends = _positive_magnitude(
            _to_decimal(cas.get("TotalCashDividendsPaid"), "dividends_paid", period, warnings)
        )
        parsed.append(
            (
                period,
                CashFlowStatement(
                    period=period,
                    operating_cash_flow=_to_decimal(
                        cas.get("CashfromOperatingActivities"), "operating_cash_flow", period, warnings
                    ),
                    capital_expenditure=capex,
                    # Not provided by this API — Step 2's engine derives it
                    # from operating_cash_flow - capital_expenditure.
                    free_cash_flow=None,
                    dividends_paid=dividends,
                ),
            )
        )
    return _dedupe_by_period(parsed, "cash flow statement", warnings), warnings


def build_company_financials(
    company_name: str, ticker: str, financials_raw: list[dict]
) -> tuple[CompanyFinancials, str | None, list[str]]:
    """Map one `/stock` response's `financials` list into one
    `CompanyFinancials`. Never raises for data-quality issues — those
    become warnings and missing (`None`) fields, never a fabricated value.
    """
    income_statements, income_warnings = map_income_statements(financials_raw)
    balance_sheets, balance_warnings = map_balance_sheets(financials_raw)
    cash_flow_statements, cash_flow_warnings = map_cash_flow_statements(financials_raw)
    warnings = income_warnings + balance_warnings + cash_flow_warnings

    currency = None  # never reported by this endpoint; never guessed.

    fiscal_periods = sorted(
        {s.period for s in income_statements}
        | {s.period for s in balance_sheets}
        | {s.period for s in cash_flow_statements}
    )

    company_financials = CompanyFinancials(
        company_name=company_name,
        ticker=ticker,
        currency=currency,
        fiscal_periods=fiscal_periods,
        income_statements=income_statements,
        balance_sheets=balance_sheets,
        cash_flow_statements=cash_flow_statements,
    )
    return company_financials, currency, warnings

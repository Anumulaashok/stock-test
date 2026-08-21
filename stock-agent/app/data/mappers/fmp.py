"""Maps Financial Modeling Prep's raw JSON schema into `CompanyFinancials`.

Pure functions only — no HTTP, no I/O. Verified against FMP's documented
stable API response shape for `income-statement`, `balance-sheet-statement`,
and `cash-flow-statement`.

Units: FMP reports absolute currency units, not scaled to
thousands/millions — confirmed directly against FMP's own published
example response (a real bank's `"revenue": 47104000000`, matching its
actual ~$47B reported revenue). Values are therefore mapped as-is; this
mapper does not attempt to detect or correct scale.

Only annual records (`"period": "FY"`) are used for this first
implementation — any quarterly record present in the raw response is
silently filtered out (not an error, just out of scope; see Step 7
report for the documented decision).

`capitalExpenditure` and `dividendsPaid` are reported by FMP as negative
numbers (cash outflow convention); this mapper takes their absolute
value to match `CashFlowStatement`'s documented positive-magnitude
convention.
"""

import re
from decimal import Decimal, InvalidOperation

from app.models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFinancials,
    IncomeStatement,
)

_DATE_RE = re.compile(r"^(\d{4})-\d{2}-\d{2}")


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


def _is_annual(raw: dict) -> bool:
    return raw.get("period") == "FY"


def _extract_period(raw: dict, warnings: list[str]) -> str | None:
    date = raw.get("date")
    if not isinstance(date, str):
        warnings.append("skipped a statement record with no reporting date")
        return None
    match = _DATE_RE.match(date)
    if not match:
        warnings.append(f"skipped a statement record with an unparseable date: {date!r}")
        return None
    return f"FY{match.group(1)}"


def _dedupe_by_period(
    items: list[tuple[str, object]], statement_kind: str, warnings: list[str]
) -> list[object]:
    seen: dict[str, object] = {}
    for period, statement in items:
        if period in seen:
            warnings.append(
                f"duplicate {statement_kind} record for {period}; kept the first one returned"
            )
            continue
        seen[period] = statement
    return list(seen.values())


def map_income_statements(raw_records: list[dict]) -> tuple[list[IncomeStatement], list[str]]:
    warnings: list[str] = []
    parsed: list[tuple[str, IncomeStatement]] = []
    for raw in raw_records:
        if not _is_annual(raw):
            continue
        period = _extract_period(raw, warnings)
        if period is None:
            continue
        parsed.append(
            (
                period,
                IncomeStatement(
                    period=period,
                    revenue=_to_decimal(raw.get("revenue"), "revenue", period, warnings),
                    cost_of_revenue=_to_decimal(
                        raw.get("costOfRevenue"), "cost_of_revenue", period, warnings
                    ),
                    gross_profit=_to_decimal(
                        raw.get("grossProfit"), "gross_profit", period, warnings
                    ),
                    operating_income=_to_decimal(
                        raw.get("operatingIncome"), "operating_income", period, warnings
                    ),
                    net_income=_to_decimal(raw.get("netIncome"), "net_income", period, warnings),
                    interest_expense=_to_decimal(
                        raw.get("interestExpense"), "interest_expense", period, warnings
                    ),
                    tax_expense=_to_decimal(
                        raw.get("incomeTaxExpense"), "tax_expense", period, warnings
                    ),
                    shares_outstanding=_to_decimal(
                        raw.get("weightedAverageShsOut"), "shares_outstanding", period, warnings
                    ),
                    eps=_to_decimal(raw.get("eps"), "eps", period, warnings),
                ),
            )
        )
    return _dedupe_by_period(parsed, "income statement", warnings), warnings


def map_balance_sheets(raw_records: list[dict]) -> tuple[list[BalanceSheet], list[str]]:
    warnings: list[str] = []
    parsed: list[tuple[str, BalanceSheet]] = []
    for raw in raw_records:
        if not _is_annual(raw):
            continue
        period = _extract_period(raw, warnings)
        if period is None:
            continue
        parsed.append(
            (
                period,
                BalanceSheet(
                    period=period,
                    total_assets=_to_decimal(
                        raw.get("totalAssets"), "total_assets", period, warnings
                    ),
                    current_assets=_to_decimal(
                        raw.get("totalCurrentAssets"), "current_assets", period, warnings
                    ),
                    cash_and_equivalents=_to_decimal(
                        raw.get("cashAndCashEquivalents"), "cash_and_equivalents", period, warnings
                    ),
                    total_liabilities=_to_decimal(
                        raw.get("totalLiabilities"), "total_liabilities", period, warnings
                    ),
                    current_liabilities=_to_decimal(
                        raw.get("totalCurrentLiabilities"), "current_liabilities", period, warnings
                    ),
                    total_debt=_to_decimal(raw.get("totalDebt"), "total_debt", period, warnings),
                    shareholders_equity=_to_decimal(
                        raw.get("totalStockholdersEquity"), "shareholders_equity", period, warnings
                    ),
                ),
            )
        )
    return _dedupe_by_period(parsed, "balance sheet", warnings), warnings


def map_cash_flow_statements(raw_records: list[dict]) -> tuple[list[CashFlowStatement], list[str]]:
    warnings: list[str] = []
    parsed: list[tuple[str, CashFlowStatement]] = []
    for raw in raw_records:
        if not _is_annual(raw):
            continue
        period = _extract_period(raw, warnings)
        if period is None:
            continue
        capex = _positive_magnitude(
            _to_decimal(raw.get("capitalExpenditure"), "capital_expenditure", period, warnings)
        )
        dividends = _positive_magnitude(
            _to_decimal(raw.get("dividendsPaid"), "dividends_paid", period, warnings)
        )
        parsed.append(
            (
                period,
                CashFlowStatement(
                    period=period,
                    operating_cash_flow=_to_decimal(
                        raw.get("operatingCashFlow"), "operating_cash_flow", period, warnings
                    ),
                    capital_expenditure=capex,
                    free_cash_flow=_to_decimal(
                        raw.get("freeCashFlow"), "free_cash_flow", period, warnings
                    ),
                    dividends_paid=dividends,
                ),
            )
        )
    return _dedupe_by_period(parsed, "cash flow statement", warnings), warnings


def extract_currency(all_raw_records: list[dict]) -> tuple[str | None, list[str]]:
    """The reported currency, plus a warning if it's inconsistent across records."""
    warnings: list[str] = []
    currencies = {r.get("reportedCurrency") for r in all_raw_records if r.get("reportedCurrency")}
    if not currencies:
        return None, warnings
    if len(currencies) > 1:
        warnings.append(
            f"inconsistent reported currency across periods ({', '.join(sorted(currencies))}); "
            "using the most recently reported one"
        )
        # FMP returns records newest-first.
        return all_raw_records[0].get("reportedCurrency"), warnings
    return currencies.pop(), warnings


def build_company_financials(
    company_name: str,
    ticker: str,
    income_raw: list[dict],
    balance_raw: list[dict],
    cash_flow_raw: list[dict],
) -> tuple[CompanyFinancials, str | None, list[str]]:
    """Map all three raw FMP statement lists into one `CompanyFinancials`.

    Returns `(company_financials, currency, warnings)`. Never raises for
    data-quality issues — those become warnings and missing (`None`)
    fields, never a fabricated value.
    """
    income_statements, income_warnings = map_income_statements(income_raw)
    balance_sheets, balance_warnings = map_balance_sheets(balance_raw)
    cash_flow_statements, cash_flow_warnings = map_cash_flow_statements(cash_flow_raw)
    currency, currency_warnings = extract_currency(income_raw + balance_raw + cash_flow_raw)

    warnings = income_warnings + balance_warnings + cash_flow_warnings + currency_warnings

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

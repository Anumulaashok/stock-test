"""Maps IndianAPI's `/historical_stats` schema into the same canonical
`CompanyFinancials` model `app.data.mappers.indianapi` builds from
`/stock`'s `financials` list. Pure functions only -- no HTTP.

This is the fallback source used when `/stock`'s own `financials` field
is `null` (verified live for HUDCO on 2026-09-03: `/stock` returns 200
with every other field populated but `financials`/`keyMetrics`/
`stockFinancialData`/`recentNews` all `null`, while `/historical_stats`
for the same ticker returns real, populated data). This is a genuine
per-company data gap on IndianAPI's `/stock` endpoint, not a different
API version or a category-wide gap -- other companies in the same
industry (e.g. BAJFINANCE, also "Consumer Financial Services") return a
normal `/stock.financials` list.

Response shape, verified live against HUDCO (2026-09-03):

    GET /historical_stats?stock_name=HUDCO&stats=balancesheet
    {"Equity Capital": {"Mar 2025": 2002, "Mar 2026": 2002, ...},
     "Reserves": {...}, "Borrowing": {...}, "Other Liabilities": {...},
     "Total Liabilities": {...}, "Fixed Assets": {...}, "CWIP": {...},
     "Investments": {...}, "Other Assets": {...}, "Total Assets": {...}}

    GET /historical_stats?stock_name=HUDCO&stats=cashflow
    {"Cash from Operating Activity": {...}, "Cash from Investing Activity": {...},
     "Cash from Financing Activity": {...}, "Net Cash Flow": {...},
     "Free Cash Flow": {...}}

    GET /historical_stats?stock_name=HUDCO&stats=ratios
    {"ROE %": {"Mar 2025": 16.0, "Mar 2026": 20.0}}

    GET /historical_stats?stock_name=HUDCO&stats=quarter_results
    {"Revenue": {"Jun 2026": 3717.0, ...}, "Interest": {...}, "Expenses": {...},
     "Financing Profit": {...}, "Financing Margin %": {...}, ...}

Every endpoint is shaped `{metric_name: {period_label: numeric_value}}`
-- a metric-major, not period-major, layout (the opposite orientation
from `/stock`'s `financials` list of per-period objects). Period labels
are `"Mon YYYY"` (e.g. `"Mar 2026"`); this project's existing period
convention (see `app.data.mappers.indianapi`) is `"FY{year}"`, taken
from the year component only -- consistent with the primary mapper,
which also keys purely off the calendar year a fiscal period ends in.

Units: same INR Crore convention as the primary `/stock`-based mapper
(verified consistent by cross-referencing HUDCO's reported figures
against public filings during implementation) -- no conversion applied
here either, for the same reason: every aggregate field is uniformly
Crore-scaled, so downstream per-share math is unaffected.

Scope note: `ratios` and `quarter_results` are parsed here (and their
client/provider plumbing exists) because the fallback fetches them for
completeness, but neither is merged into `CompanyFinancials` --
`quarter_results` reports interim (non-annual) figures under the same
metric names as annual income-statement fields (Revenue, Net Profit,
EPS), and mixing those into `income_statements` would silently present
one quarter's numbers as a full fiscal year to the valuation engine
(per-share math, growth rates) with no `period_type` field on the
model to distinguish them (see the "quarterly financial integration"
item flagged as a future architecture change, not part of this fix).
`ratios` (e.g. `ROE %`) has no analog field on `IncomeStatement`/
`BalanceSheet` at all -- and isn't needed, since the deterministic
financial engine already derives its own ratios from net_income/equity
rather than consuming a source-reported ratio. Both are still returned
here as parsed, tested data (`parse_metric_series`-shaped) for
validation/logging and for the analysis engine to draw on later, should
a quarterly-aware model ever exist.
"""

from decimal import Decimal, InvalidOperation

from app.models.financial_statements import BalanceSheet, CashFlowStatement


def _to_decimal(value: object, field_name: str, period: str, warnings: list[str]) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        warnings.append(f"{period}: '{field_name}' was not a valid number and was left unavailable")
        return None


def _period_to_fiscal_year(period_label: str) -> str | None:
    """`"Mar 2026"` -> `"FY2026"`. Keys off the year token only, matching
    `app.data.mappers.indianapi`'s own `"FY{year}"` convention (which is
    itself keyed off `/stock`'s `FiscalYear` -- the calendar year a
    fiscal period ends in, not the month)."""
    parts = period_label.strip().split()
    if len(parts) != 2:
        return None
    year_token = parts[-1]
    if not year_token.isdigit() or len(year_token) != 4:
        return None
    return f"FY{year_token}"


def parse_metric_series(raw: dict) -> dict[str, dict[str, Decimal | None]]:
    """Flattens `{metric: {period_label: value}}` into
    `{metric: {period_label: Decimal|None}}`. Tolerates any metric set --
    an unrecognized or missing key is simply absent from the result,
    never an error, matching this endpoint's documented tendency to
    return a different metric set per company/period."""
    if not isinstance(raw, dict):
        return {}
    warnings: list[str] = []
    result: dict[str, dict[str, Decimal | None]] = {}
    for metric, series in raw.items():
        if not isinstance(metric, str) or not isinstance(series, dict):
            continue
        parsed_series: dict[str, Decimal | None] = {}
        for period_label, value in series.items():
            if not isinstance(period_label, str):
                continue
            parsed_series[period_label] = _to_decimal(value, metric, period_label, warnings)
        result[metric] = parsed_series
    return result


def _fiscal_year_periods(series_by_metric: dict[str, dict[str, Decimal | None]]) -> list[str]:
    """Every distinct `"Mon YYYY"` period label across all metrics,
    mapped to `FY{year}` and de-duplicated, in the order first seen --
    not sorted here, since annual balance sheet/cash flow periods are
    already reported oldest-to-newest by this endpoint."""
    periods: list[str] = []
    seen: set[str] = set()
    for series in series_by_metric.values():
        for period_label in series:
            fiscal_year = _period_to_fiscal_year(period_label)
            if fiscal_year is None or fiscal_year in seen:
                continue
            seen.add(fiscal_year)
            periods.append(fiscal_year)
    return periods


def _period_label_for_fiscal_year(series_by_metric: dict[str, dict[str, Decimal | None]], fiscal_year: str) -> str | None:
    for series in series_by_metric.values():
        for period_label in series:
            if _period_to_fiscal_year(period_label) == fiscal_year:
                return period_label
    return None


def map_historical_balance_sheets(raw: dict) -> tuple[list[BalanceSheet], list[str]]:
    warnings: list[str] = []
    series_by_metric = parse_metric_series(raw)
    fiscal_years = _fiscal_year_periods(series_by_metric)

    statements: list[BalanceSheet] = []
    for fiscal_year in fiscal_years:
        period_label = _period_label_for_fiscal_year(series_by_metric, fiscal_year)
        if period_label is None:
            continue

        def value(metric: str) -> Decimal | None:
            return series_by_metric.get(metric, {}).get(period_label)

        equity_capital = value("Equity Capital")
        reserves = value("Reserves")
        shareholders_equity = (
            equity_capital + reserves if equity_capital is not None and reserves is not None else None
        )

        statements.append(
            BalanceSheet(
                period=fiscal_year,
                total_assets=value("Total Assets"),
                current_assets=None,  # not reported by this endpoint
                cash_and_equivalents=None,  # not reported by this endpoint
                total_liabilities=value("Total Liabilities"),
                current_liabilities=None,  # not reported by this endpoint
                total_debt=value("Borrowing"),
                shareholders_equity=shareholders_equity,
            )
        )
    return statements, warnings


def map_historical_cash_flow_statements(raw: dict) -> tuple[list[CashFlowStatement], list[str]]:
    warnings: list[str] = []
    series_by_metric = parse_metric_series(raw)
    fiscal_years = _fiscal_year_periods(series_by_metric)

    statements: list[CashFlowStatement] = []
    for fiscal_year in fiscal_years:
        period_label = _period_label_for_fiscal_year(series_by_metric, fiscal_year)
        if period_label is None:
            continue

        def value(metric: str) -> Decimal | None:
            return series_by_metric.get(metric, {}).get(period_label)

        statements.append(
            CashFlowStatement(
                period=fiscal_year,
                operating_cash_flow=value("Cash from Operating Activity"),
                capital_expenditure=None,  # not broken out by this endpoint
                # This endpoint reports FCF directly -- used as-is per this
                # project's existing "prefer a directly stated value" policy
                # (see `app.financial.service`), not recalculated here.
                free_cash_flow=value("Free Cash Flow"),
                dividends_paid=None,  # not broken out by this endpoint
            )
        )
    return statements, warnings


def map_historical_ratios(raw: dict) -> dict[str, dict[str, Decimal | None]]:
    """Returns the parsed `{metric: {period_label: value}}` series as-is
    -- not merged into `CompanyFinancials` (see module docstring)."""
    return parse_metric_series(raw)


def map_historical_quarter_results(raw: dict) -> dict[str, dict[str, Decimal | None]]:
    """Returns the parsed `{metric: {period_label: value}}` series as-is
    -- not merged into `CompanyFinancials` (see module docstring)."""
    return parse_metric_series(raw)

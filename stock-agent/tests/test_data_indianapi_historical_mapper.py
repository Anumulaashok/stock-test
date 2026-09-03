from decimal import Decimal

from app.data.mappers.indianapi_historical import (
    map_historical_balance_sheets,
    map_historical_cash_flow_statements,
    map_historical_quarter_results,
    map_historical_ratios,
    parse_metric_series,
)

# Shapes below are the actual live `/historical_stats?stock_name=HUDCO`
# response fields (verified live, 2026-09-03) -- HUDCO is the ticker
# whose `/stock.financials` field is `null`, which is what this fallback
# mapper exists for.

_HUDCO_BALANCE_SHEET_RAW = {
    "Equity Capital": {"Mar 2025": 2002, "Mar 2026": 2002},
    "Reserves": {"Mar 2025": 15966, "Mar 2026": 19974},
    "Borrowing": {"Mar 2025": 107297, "Mar 2026": 141677},
    "Other Liabilities": {"Mar 2025": 3231, "Mar 2026": 3186},
    "Total Liabilities": {"Mar 2025": 128496, "Mar 2026": 166838},
    "Total Assets": {"Mar 2025": 128496, "Mar 2026": 166838},
}

_HUDCO_CASH_FLOW_RAW = {
    "Cash from Operating Activity": {"Mar 2025": -31421, "Mar 2026": -33912},
    "Cash from Investing Activity": {"Mar 2025": -1041, "Mar 2026": -884},
    "Cash from Financing Activity": {"Mar 2025": 32218, "Mar 2026": 34793},
    "Net Cash Flow": {"Mar 2025": -244, "Mar 2026": -3},
    "Free Cash Flow": {"Mar 2025": -31442, "Mar 2026": -33906},
}

_HUDCO_RATIOS_RAW = {"ROE %": {"Mar 2025": 16.0, "Mar 2026": 20.0}}

_HUDCO_QUARTER_RESULTS_RAW = {
    "Revenue": {"Mar 2026": 3563.0, "Jun 2026": 3717.0},
    "Net Profit": {"Mar 2026": 1981.0, "Jun 2026": 851.0},
    "EPS in Rs": {"Mar 2026": 9.9, "Jun 2026": 4.25},
}


def d(value) -> Decimal:
    return Decimal(str(value))


# --- balance sheet -----------------------------------------------------------------


def test_hudco_balance_sheet_maps_borrowing_and_total_assets():
    statements, warnings = map_historical_balance_sheets(_HUDCO_BALANCE_SHEET_RAW)
    by_period = {s.period: s for s in statements}

    assert by_period["FY2025"].total_debt == d(107297)
    assert by_period["FY2026"].total_debt == d(141677)
    assert by_period["FY2025"].total_assets == d(128496)
    assert by_period["FY2026"].total_assets == d(166838)
    assert warnings == []


def test_hudco_balance_sheet_derives_shareholders_equity_from_capital_plus_reserves():
    statements, _ = map_historical_balance_sheets(_HUDCO_BALANCE_SHEET_RAW)
    by_period = {s.period: s for s in statements}
    assert by_period["FY2026"].shareholders_equity == d(2002) + d(19974)


def test_balance_sheet_missing_fields_stay_none_not_fabricated():
    statements, _ = map_historical_balance_sheets(_HUDCO_BALANCE_SHEET_RAW)
    by_period = {s.period: s for s in statements}
    assert by_period["FY2026"].current_assets is None
    assert by_period["FY2026"].current_liabilities is None
    assert by_period["FY2026"].cash_and_equivalents is None


# --- cash flow -----------------------------------------------------------------------


def test_hudco_cash_flow_operating_activity():
    statements, warnings = map_historical_cash_flow_statements(_HUDCO_CASH_FLOW_RAW)
    by_period = {s.period: s for s in statements}
    assert by_period["FY2025"].operating_cash_flow == d(-31421)
    assert by_period["FY2026"].operating_cash_flow == d(-33912)
    assert warnings == []


def test_hudco_cash_flow_uses_source_supplied_free_cash_flow_directly():
    statements, _ = map_historical_cash_flow_statements(_HUDCO_CASH_FLOW_RAW)
    by_period = {s.period: s for s in statements}
    assert by_period["FY2025"].free_cash_flow == d(-31442)
    assert by_period["FY2026"].free_cash_flow == d(-33906)
    # Not recalculated from operating_cash_flow - capex -- capex isn't
    # reported by this endpoint at all, so it must stay None, not derived.
    assert by_period["FY2026"].capital_expenditure is None


# --- ratios (parsed, not merged into CompanyFinancials) -----------------------------


def test_hudco_ratios_roe_is_parsed():
    parsed = map_historical_ratios(_HUDCO_RATIOS_RAW)
    assert parsed["ROE %"]["Mar 2026"] == d(20)


def test_ratios_tolerates_missing_or_extra_metrics():
    parsed = map_historical_ratios({"Some New Ratio %": {"Mar 2026": 5}})
    assert parsed["Some New Ratio %"]["Mar 2026"] == d(5)
    assert "ROE %" not in parsed


# --- quarterly results (parsed, not merged into CompanyFinancials) ------------------


def test_hudco_quarterly_results():
    parsed = map_historical_quarter_results(_HUDCO_QUARTER_RESULTS_RAW)
    assert parsed["Revenue"]["Jun 2026"] == d(3717)
    assert parsed["Net Profit"]["Jun 2026"] == d(851)
    assert parsed["EPS in Rs"]["Jun 2026"] == d("4.25")


# --- generic parsing edge cases -------------------------------------------------------


def test_parse_metric_series_handles_non_numeric_values():
    parsed = parse_metric_series({"Total Assets": {"Mar 2026": "not-a-number"}})
    assert parsed["Total Assets"]["Mar 2026"] is None


def test_parse_metric_series_tolerates_non_dict_input():
    assert parse_metric_series(None) == {}
    assert parse_metric_series("invalid") == {}

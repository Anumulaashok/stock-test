from decimal import Decimal

from app.data.mappers.fmp import (
    build_company_financials,
    extract_currency,
    map_balance_sheets,
    map_cash_flow_statements,
    map_income_statements,
)


def d(value) -> Decimal:
    return Decimal(str(value))


def income_record(**overrides):
    record = {
        "date": "2024-12-31",
        "symbol": "ACME",
        "reportedCurrency": "USD",
        "period": "FY",
        "revenue": 1000,
        "costOfRevenue": 600,
        "grossProfit": 400,
        "operatingIncome": 200,
        "netIncome": 100,
        "interestExpense": 10,
        "incomeTaxExpense": 30,
        "eps": 2.0,
        "weightedAverageShsOut": 50,
    }
    record.update(overrides)
    return record


def balance_record(**overrides):
    record = {
        "date": "2024-12-31",
        "reportedCurrency": "USD",
        "period": "FY",
        "totalAssets": 5000,
        "totalCurrentAssets": 2000,
        "cashAndCashEquivalents": 500,
        "totalLiabilities": 3000,
        "totalCurrentLiabilities": 1000,
        "totalDebt": 1500,
        "totalStockholdersEquity": 2000,
    }
    record.update(overrides)
    return record


def cash_flow_record(**overrides):
    record = {
        "date": "2024-12-31",
        "reportedCurrency": "USD",
        "period": "FY",
        "operatingCashFlow": 300,
        "capitalExpenditure": -100,  # FMP convention: negative = cash outflow
        "freeCashFlow": 200,
        "dividendsPaid": -50,
    }
    record.update(overrides)
    return record


# --- Income statement -------------------------------------------------------------


def test_map_income_statement_complete():
    statements, warnings = map_income_statements([income_record()])
    assert warnings == []
    assert len(statements) == 1
    s = statements[0]
    assert s.period == "FY2024"
    assert s.revenue == d(1000)
    assert s.net_income == d(100)
    assert s.eps == d("2.0")
    assert s.shares_outstanding == d(50)


def test_map_income_statement_missing_field_is_none_not_zero():
    statements, warnings = map_income_statements([income_record(interestExpense=None)])
    assert statements[0].interest_expense is None
    assert warnings == []  # missing (None) is not a data-quality warning, just absent


def test_map_income_statement_malformed_number_left_unavailable():
    statements, warnings = map_income_statements([income_record(revenue="not-a-number")])
    assert statements[0].revenue is None
    assert any("revenue" in w for w in warnings)


def test_map_income_statement_filters_quarterly():
    records = [income_record(period="Q1", date="2024-03-31"), income_record(period="FY")]
    statements, _ = map_income_statements(records)
    assert len(statements) == 1
    assert statements[0].period == "FY2024"


def test_map_income_statement_negative_and_zero_values_preserved():
    statements, _ = map_income_statements([income_record(netIncome=-50, interestExpense=0)])
    assert statements[0].net_income == d(-50)
    assert statements[0].interest_expense == d(0)


def test_map_income_statement_duplicate_periods_deduped_with_warning():
    records = [income_record(), income_record(netIncome=999)]
    statements, warnings = map_income_statements(records)
    assert len(statements) == 1
    assert statements[0].net_income == d(100)  # first one kept
    assert any("duplicate" in w for w in warnings)


def test_map_income_statement_unparseable_date_skipped():
    statements, warnings = map_income_statements([income_record(date="not-a-date")])
    assert statements == []
    assert any("unparseable date" in w for w in warnings)


def test_map_income_statement_missing_date_skipped():
    statements, warnings = map_income_statements([income_record(date=None)])
    assert statements == []
    assert any("no reporting date" in w for w in warnings)


def test_map_income_statement_unsorted_input_preserved_order_agnostic():
    records = [income_record(date="2023-12-31"), income_record(date="2022-12-31"), income_record(date="2024-12-31")]
    statements, _ = map_income_statements(records)
    periods = {s.period for s in statements}
    assert periods == {"FY2022", "FY2023", "FY2024"}


def test_map_income_statement_unknown_fields_ignored():
    statements, warnings = map_income_statements([income_record(someUnknownField="whatever")])
    assert statements[0].revenue == d(1000)
    assert warnings == []


# --- Balance sheet -----------------------------------------------------------------


def test_map_balance_sheet_complete():
    statements, warnings = map_balance_sheets([balance_record()])
    assert warnings == []
    s = statements[0]
    assert s.total_assets == d(5000)
    assert s.cash_and_equivalents == d(500)
    assert s.total_debt == d(1500)
    assert s.shareholders_equity == d(2000)


def test_map_balance_sheet_missing_field_is_none():
    statements, _ = map_balance_sheets([balance_record(totalDebt=None)])
    assert statements[0].total_debt is None


# --- Cash flow -----------------------------------------------------------------------


def test_map_cash_flow_capex_and_dividends_converted_to_positive_magnitude():
    statements, _ = map_cash_flow_statements([cash_flow_record()])
    s = statements[0]
    assert s.capital_expenditure == d(100)  # was -100
    assert s.dividends_paid == d(50)  # was -50
    assert s.free_cash_flow == d(200)  # stated value used as-is
    assert s.operating_cash_flow == d(300)


def test_map_cash_flow_missing_capex_is_none():
    statements, _ = map_cash_flow_statements([cash_flow_record(capitalExpenditure=None)])
    assert statements[0].capital_expenditure is None


# --- Currency -----------------------------------------------------------------------


def test_extract_currency_consistent():
    currency, warnings = extract_currency([income_record(), balance_record(), cash_flow_record()])
    assert currency == "USD"
    assert warnings == []


def test_extract_currency_missing_returns_none():
    currency, warnings = extract_currency([income_record(reportedCurrency=None)])
    assert currency is None
    assert warnings == []


def test_extract_currency_inconsistent_warns_and_uses_first():
    records = [income_record(reportedCurrency="EUR"), income_record(reportedCurrency="USD")]
    currency, warnings = extract_currency(records)
    assert currency == "EUR"  # first record (newest, per FMP ordering)
    assert any("inconsistent" in w for w in warnings)


# --- build_company_financials --------------------------------------------------------


def test_build_company_financials_full_pipeline():
    company_financials, currency, warnings = build_company_financials(
        company_name="ACME",
        ticker="ACME",
        income_raw=[income_record()],
        balance_raw=[balance_record()],
        cash_flow_raw=[cash_flow_record()],
    )
    assert warnings == []
    assert currency == "USD"
    assert company_financials.company_name == "ACME"
    assert company_financials.currency == "USD"
    assert company_financials.fiscal_periods == ["FY2024"]
    assert len(company_financials.income_statements) == 1
    assert len(company_financials.balance_sheets) == 1
    assert len(company_financials.cash_flow_statements) == 1


def test_build_company_financials_mixed_annual_and_quarterly_filters_quarterly():
    income_raw = [
        income_record(period="FY", date="2024-12-31"),
        income_record(period="Q1", date="2024-03-31"),
        income_record(period="Q2", date="2024-06-30"),
    ]
    company_financials, _, _ = build_company_financials(
        company_name="ACME", ticker="ACME", income_raw=income_raw, balance_raw=[], cash_flow_raw=[]
    )
    assert len(company_financials.income_statements) == 1
    assert company_financials.income_statements[0].period == "FY2024"


def test_build_company_financials_no_invented_zeros():
    company_financials, _, _ = build_company_financials(
        company_name="ACME", ticker="ACME",
        income_raw=[income_record(interestExpense=None, taxExpense=None)],
        balance_raw=[], cash_flow_raw=[],
    )
    assert company_financials.income_statements[0].interest_expense is None


def test_build_company_financials_empty_input_produces_empty_but_valid_result():
    company_financials, currency, warnings = build_company_financials(
        company_name="ACME", ticker="ACME", income_raw=[], balance_raw=[], cash_flow_raw=[]
    )
    assert company_financials.income_statements == []
    assert company_financials.balance_sheets == []
    assert company_financials.cash_flow_statements == []
    assert currency is None
    assert warnings == []

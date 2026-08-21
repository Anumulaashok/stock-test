from decimal import Decimal

from app.data.mappers.indianapi import (
    build_company_financials,
    map_balance_sheets,
    map_cash_flow_statements,
    map_income_statements,
)


def d(value) -> Decimal:
    return Decimal(str(value))


def _item(key, value):
    return {"displayName": key, "key": key, "value": value, "qoQComp": None, "yqoQComp": None}


def entry(
    fiscal_year=2026,
    end_date="2026-03-31",
    type_="Annual",
    inc_overrides=None,
    bal_overrides=None,
    cas_overrides=None,
):
    inc = {
        "Revenue": "1075675.00",
        "CostofRevenueTotal": "738135.00",
        "GrossProfit": "337540.00",
        "OperatingIncome": "121342.00",
        "NetIncome": "80775.00",
        "InterestInc(Exp)Net-Non-OpTotal": "-1461",
        "ProvisionforIncomeTaxes": "27552.00",
        "DilutedWeightedAverageShares": "1353.27",
        "DilutedNormalizedEPS": "59.76",
        "periodType": "Months",
        "periodLength": "12",
    }
    if inc_overrides:
        inc.update(inc_overrides)

    bal = {
        "TotalAssets": "2178140.00",
        "TotalCurrentAssets": "594249.00",
        "Cash": "98592.00",
        "TotalLiabilities": "1274110.00",
        "TotalCurrentLiabilities": "541254.00",
        "TotalDebt": "398000.00",
        "TotalEquity": "904030.00",
    }
    if bal_overrides:
        bal.update(bal_overrides)

    cas = {
        "CashfromOperatingActivities": "192113.00",
        "CapitalExpenditures": "-122916",
        "TotalCashDividendsPaid": "-7443",
        "periodType": "Months",
    }
    if cas_overrides:
        cas.update(cas_overrides)

    return {
        "FiscalYear": fiscal_year,
        "EndDate": end_date,
        "Type": type_,
        "StatementDate": "2021-03-31",
        "fiscalPeriodNumber": 0,
        "stockFinancialMap": {
            "INC": [_item(k, v) for k, v in inc.items()] if inc is not None else [],
            "BAL": [_item(k, v) for k, v in bal.items()] if bal is not None else [],
            "CAS": [_item(k, v) for k, v in cas.items()] if cas is not None else [],
        },
    }


# --- Income statement -------------------------------------------------------------


def test_map_income_statement_valid_annual():
    statements, warnings = map_income_statements([entry()])
    assert warnings == []
    s = statements[0]
    assert s.period == "FY2026"
    assert s.revenue == d("1075675.00")
    assert s.net_income == d("80775.00")
    assert s.eps == d("59.76")
    assert s.shares_outstanding == d("1353.27")


def test_map_income_statement_negative_net_interest_becomes_positive_expense():
    statements, _ = map_income_statements([entry()])
    # provider value was "-1461" (net expense) -> stored as a positive magnitude
    assert statements[0].interest_expense == d("1461")


def test_map_income_statement_positive_net_interest_income_left_unavailable():
    statements, warnings = map_income_statements(
        [entry(inc_overrides={"InterestInc(Exp)Net-Non-OpTotal": "500"})]
    )
    assert statements[0].interest_expense is None
    assert any("net interest was income" in w for w in warnings)


def test_map_income_statement_filters_interim_periods():
    statements, _ = map_income_statements([entry(type_="Interim"), entry(type_="Annual")])
    assert len(statements) == 1


def test_map_income_statement_multiple_periods():
    statements, _ = map_income_statements([entry(fiscal_year=2026), entry(fiscal_year=2025)])
    periods = {s.period for s in statements}
    assert periods == {"FY2026", "FY2025"}


def test_map_income_statement_missing_field_is_none_not_zero():
    statements, warnings = map_income_statements(
        [entry(inc_overrides={"ProvisionforIncomeTaxes": None})]
    )
    assert statements[0].tax_expense is None
    assert warnings == []  # a missing (None) value is not itself a data-quality warning


def test_map_income_statement_malformed_numeric_value():
    statements, warnings = map_income_statements([entry(inc_overrides={"Revenue": "not-a-number"})])
    assert statements[0].revenue is None
    assert any("revenue" in w for w in warnings)


def test_map_income_statement_negative_and_zero_values_preserved():
    statements, _ = map_income_statements(
        [entry(inc_overrides={"NetIncome": "-500", "ProvisionforIncomeTaxes": "0"})]
    )
    assert statements[0].net_income == d("-500")
    assert statements[0].tax_expense == d("0")


def test_map_income_statement_missing_fiscal_year_skipped():
    bad_entry = entry()
    del bad_entry["FiscalYear"]
    statements, warnings = map_income_statements([bad_entry])
    assert statements == []
    assert any("no usable fiscal year" in w for w in warnings)


def test_map_income_statement_duplicate_period_deduped_with_warning():
    statements, warnings = map_income_statements(
        [entry(fiscal_year=2026), entry(fiscal_year=2026, inc_overrides={"NetIncome": "999"})]
    )
    assert len(statements) == 1
    assert statements[0].net_income == d("80775.00")  # first one kept
    assert any("duplicate" in w for w in warnings)


def test_map_income_statement_unknown_fields_ignored():
    statements, warnings = map_income_statements([entry(inc_overrides={"SomeFutureField": "123"})])
    assert statements[0].revenue == d("1075675.00")
    assert warnings == []


# --- Balance sheet -----------------------------------------------------------------


def test_map_balance_sheet_valid():
    statements, warnings = map_balance_sheets([entry()])
    assert warnings == []
    s = statements[0]
    assert s.total_assets == d("2178140.00")
    assert s.cash_and_equivalents == d("98592.00")
    assert s.total_debt == d("398000.00")
    assert s.shareholders_equity == d("904030.00")


def test_map_balance_sheet_missing_field_is_none():
    statements, _ = map_balance_sheets([entry(bal_overrides={"TotalDebt": None})])
    assert statements[0].total_debt is None


# --- Cash flow -----------------------------------------------------------------------


def test_map_cash_flow_capex_and_dividends_to_positive_magnitude():
    statements, _ = map_cash_flow_statements([entry()])
    s = statements[0]
    assert s.operating_cash_flow == d("192113.00")
    assert s.capital_expenditure == d("122916")  # was "-122916"
    assert s.dividends_paid == d("7443")  # was "-7443"
    assert s.free_cash_flow is None  # not provided by this API; Step 2 derives it


def test_map_cash_flow_missing_capex_is_none():
    statements, _ = map_cash_flow_statements([entry(cas_overrides={"CapitalExpenditures": None})])
    assert statements[0].capital_expenditure is None


# --- build_company_financials --------------------------------------------------------


def test_build_company_financials_full_pipeline():
    company_financials, currency, warnings = build_company_financials(
        company_name="Reliance Industries", ticker="Reliance", financials_raw=[entry()]
    )
    assert warnings == []
    assert currency is None  # never reported by this endpoint; never guessed
    assert company_financials.currency is None
    assert company_financials.company_name == "Reliance Industries"
    assert company_financials.fiscal_periods == ["FY2026"]
    assert len(company_financials.income_statements) == 1
    assert len(company_financials.balance_sheets) == 1
    assert len(company_financials.cash_flow_statements) == 1


def test_build_company_financials_mixed_annual_and_interim_filters_interim():
    financials_raw = [entry(type_="Annual", fiscal_year=2026), entry(type_="Interim", fiscal_year=2027)]
    company_financials, _, _ = build_company_financials(
        company_name="Reliance", ticker="Reliance", financials_raw=financials_raw
    )
    assert company_financials.fiscal_periods == ["FY2026"]


def test_build_company_financials_empty_input_produces_empty_but_valid_result():
    company_financials, currency, warnings = build_company_financials(
        company_name="Acme", ticker="Acme", financials_raw=[]
    )
    assert company_financials.income_statements == []
    assert company_financials.balance_sheets == []
    assert company_financials.cash_flow_statements == []
    assert currency is None
    assert warnings == []


def test_build_company_financials_unexpected_schema_does_not_crash():
    # Missing 'stockFinancialMap' entirely for one record.
    malformed = {"FiscalYear": 2026, "Type": "Annual"}
    company_financials, _, _ = build_company_financials(
        company_name="Acme", ticker="Acme", financials_raw=[malformed]
    )
    assert len(company_financials.income_statements) == 1
    assert company_financials.income_statements[0].revenue is None

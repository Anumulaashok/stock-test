"""IndianAPIProvider's /stock -> /historical_stats fallback (see
app/data/providers/indianapi.py). Uses a fake client (no real HTTP) so
call counts can be asserted directly -- the only reliable way to prove
"historical_stats was/wasn't called unnecessarily".
"""

from decimal import Decimal

import pytest

from app.data.exceptions import ProviderError
from app.data.models import CompanyIdentifier, FinancialDataErrorCode
from app.data.providers.indianapi import IndianAPIProvider

_RELIANCE_STOCK_RESPONSE = {
    "companyName": "Reliance Industries",
    "financials": [
        {
            "FiscalYear": 2026,
            "Type": "Annual",
            "stockFinancialMap": {
                "INC": [{"key": "Revenue", "value": "1075675.00"}, {"key": "NetIncome", "value": "80775.00"}],
                "BAL": [{"key": "TotalAssets", "value": "2178140.00"}],
                "CAS": [{"key": "CashfromOperatingActivities", "value": "192113.00"}],
            },
        }
    ],
}

_HUDCO_STOCK_RESPONSE = {"companyName": "Housing & Urban Development Corporation Ltd", "financials": None}

_HUDCO_BALANCE_SHEET = {
    "Equity Capital": {"Mar 2026": 2002},
    "Reserves": {"Mar 2026": 19974},
    "Borrowing": {"Mar 2026": 141677},
    "Total Assets": {"Mar 2026": 166838},
}
_HUDCO_CASH_FLOW = {
    "Cash from Operating Activity": {"Mar 2026": -33912},
    "Free Cash Flow": {"Mar 2026": -33906},
}
_HUDCO_RATIOS = {"ROE %": {"Mar 2026": 20.0}}
_HUDCO_QUARTER_RESULTS = {"Revenue": {"Jun 2026": 3717.0}}


class FakeIndianAPIClient:
    """Stands in for `IndianAPIClient` -- counts calls per endpoint so
    tests can assert exactly what was (and wasn't) fetched."""

    def __init__(
        self,
        stock_response: dict,
        balance_sheet=None,
        cash_flow=None,
        ratios=None,
        quarter_results=None,
        historical_error: ProviderError | None = None,
    ):
        self._stock_response = stock_response
        self._balance_sheet = balance_sheet
        self._cash_flow = cash_flow
        self._ratios = ratios
        self._quarter_results = quarter_results
        self._historical_error = historical_error
        self.calls: dict[str, int] = {
            "stock": 0, "balancesheet": 0, "cashflow": 0, "ratios": 0, "quarter_results": 0,
        }

    async def get_stock(self, name: str) -> dict:
        self.calls["stock"] += 1
        return self._stock_response

    async def get_historical_balance_sheet(self, name: str) -> dict:
        self.calls["balancesheet"] += 1
        if self._historical_error:
            raise self._historical_error
        return self._balance_sheet or {}

    async def get_historical_cash_flow(self, name: str) -> dict:
        self.calls["cashflow"] += 1
        if self._historical_error:
            raise self._historical_error
        return self._cash_flow or {}

    async def get_historical_ratios(self, name: str) -> dict:
        self.calls["ratios"] += 1
        if self._historical_error:
            raise self._historical_error
        return self._ratios or {}

    async def get_historical_quarter_results(self, name: str) -> dict:
        self.calls["quarter_results"] += 1
        if self._historical_error:
            raise self._historical_error
        return self._quarter_results or {}


def d(value) -> Decimal:
    return Decimal(str(value))


# --- Case A: normal stock -- historical_stats never called --------------------------


@pytest.mark.asyncio
async def test_normal_stock_uses_existing_mapper_and_never_calls_historical_stats():
    client = FakeIndianAPIClient(stock_response=_RELIANCE_STOCK_RESPONSE)
    provider = IndianAPIProvider(client)

    result = await provider.get_company_financials(CompanyIdentifier(ticker="RELIANCE"))

    assert result.company_financials.income_statements[0].revenue == d("1075675.00")
    assert client.calls["stock"] == 1
    assert client.calls["balancesheet"] == 0
    assert client.calls["cashflow"] == 0
    assert client.calls["ratios"] == 0
    assert client.calls["quarter_results"] == 0


# --- Case B: HUDCO-like stock -- fallback succeeds -----------------------------------


@pytest.mark.asyncio
async def test_hudco_like_stock_falls_back_to_historical_stats_and_succeeds():
    client = FakeIndianAPIClient(
        stock_response=_HUDCO_STOCK_RESPONSE,
        balance_sheet=_HUDCO_BALANCE_SHEET,
        cash_flow=_HUDCO_CASH_FLOW,
        ratios=_HUDCO_RATIOS,
        quarter_results=_HUDCO_QUARTER_RESULTS,
    )
    provider = IndianAPIProvider(client)

    result = await provider.get_company_financials(CompanyIdentifier(ticker="HUDCO"))

    assert result.company_financials.balance_sheets[0].total_debt == d(141677)
    assert result.company_financials.cash_flow_statements[0].free_cash_flow == d(-33906)
    assert "FY2026" in result.company_financials.fiscal_periods
    assert client.calls["stock"] == 1
    assert client.calls["balancesheet"] == 1
    assert client.calls["cashflow"] == 1
    assert client.calls["ratios"] == 1
    assert client.calls["quarter_results"] == 1


# --- Case C: /stock.financials null + historical_stats unavailable ------------------


@pytest.mark.asyncio
async def test_stock_financials_null_and_historical_unavailable_raises_missing_required_data():
    client = FakeIndianAPIClient(
        stock_response=_HUDCO_STOCK_RESPONSE,
        historical_error=ProviderError(FinancialDataErrorCode.PROVIDER_UNAVAILABLE, "down"),
    )
    provider = IndianAPIProvider(client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.get_company_financials(CompanyIdentifier(ticker="HUDCO"))

    assert exc_info.value.code is FinancialDataErrorCode.MISSING_REQUIRED_DATA
    assert exc_info.value.code is not FinancialDataErrorCode.SCHEMA_MISMATCH


# --- Case D: malformed /stock response -----------------------------------------------


@pytest.mark.asyncio
async def test_malformed_financials_field_raises_schema_mismatch():
    client = FakeIndianAPIClient(stock_response={"companyName": "Bad Co", "financials": "invalid"})
    provider = IndianAPIProvider(client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.get_company_financials(CompanyIdentifier(ticker="BADCO"))

    assert exc_info.value.code is FinancialDataErrorCode.SCHEMA_MISMATCH

import json
import time

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _db_override(db_dependency_override):
    """The endpoints under test now read/write a cache table via
    `get_db` (see app/cache/) -- give every test an isolated in-memory
    SQLite DB (tests/conftest.py's `db_dependency_override`)."""

FMP_BASE = "http://test-fmp:9999/stable"

INCOME_RECORD = {
    "date": "2024-12-31", "period": "FY", "reportedCurrency": "USD",
    "revenue": 1000, "costOfRevenue": 600, "grossProfit": 400, "operatingIncome": 200,
    "netIncome": 100, "interestExpense": 10, "incomeTaxExpense": 30, "eps": 2.0,
    "weightedAverageShsOut": 50,
}
BALANCE_RECORD = {
    "date": "2024-12-31", "period": "FY", "reportedCurrency": "USD",
    "totalAssets": 5000, "totalCurrentAssets": 2000, "cashAndCashEquivalents": 500,
    "totalLiabilities": 3000, "totalCurrentLiabilities": 1000, "totalDebt": 1500,
    "totalStockholdersEquity": 2000,
}
CASH_FLOW_RECORD = {
    "date": "2024-12-31", "period": "FY", "reportedCurrency": "USD",
    "operatingCashFlow": 300, "capitalExpenditure": -100, "freeCashFlow": 200, "dividendsPaid": -50,
}

VALID_ANALYST_RESPONSE = {
    "investment_thesis": {"text": "Solid.", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "strengths": [], "weaknesses": [],
    "profitability_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "growth_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "financial_health_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "cash_flow_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "valuation_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "risk_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "key_takeaways": [], "caveats": [],
}


def _set_env(monkeypatch, fmp_key="fmp-secret-key", llm_configured=True):
    monkeypatch.setenv("FINANCIAL_DATA_PROVIDER", "fmp")
    monkeypatch.setenv("FMP_BASE_URL", FMP_BASE)
    monkeypatch.setenv("FMP_API_KEY", fmp_key)
    # Step 4: this test file exercises FMP market-data wiring specifically,
    # so MARKET_DATA_PROVIDER is pinned to "fmp" (the app's own default can
    # point elsewhere depending on deployment) and reuses FMP_API_KEY --
    # every test below that doesn't explicitly mock GET {FMP_BASE}/quote
    # relies on respx's "unmocked request" failure being caught by
    # AnalysisApplicationService's broad except (see test below verifying
    # that this degrades to a warning, not a crash).
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "fmp")
    if llm_configured:
        monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")
        monkeypatch.setenv("LOCAL_LLM_API_KEY", "llm-secret-key")
    else:
        monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "")


def _mock_fmp_success():
    respx.get(f"{FMP_BASE}/income-statement").mock(return_value=httpx.Response(200, json=[INCOME_RECORD]))
    respx.get(f"{FMP_BASE}/balance-sheet-statement").mock(return_value=httpx.Response(200, json=[BALANCE_RECORD]))
    respx.get(f"{FMP_BASE}/cash-flow-statement").mock(return_value=httpx.Response(200, json=[CASH_FLOW_RECORD]))


def _mock_llm_success():
    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(VALID_ANALYST_RESPONSE)}}]})
    )


@respx.mock
def test_valid_ticker_full_success(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "calculated"
        assert body["company"]["ticker"] == "ACME"
        assert body["financial_analysis"] is not None
        assert body["valuation"] is not None
        assert body["scoring"] is not None
        assert body["analyst"]["status"] == "success"
        assert "fmp-secret-key" not in response.text
        assert "llm-secret-key" not in response.text
    finally:
        get_settings.cache_clear()


def test_missing_ticker_returns_422():
    response = client.post("/api/v1/analyze/ticker", json={})
    assert response.status_code == 422


@respx.mock
def test_invalid_ticker_not_found(monkeypatch):
    _set_env(monkeypatch)
    respx.get(f"{FMP_BASE}/income-statement").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{FMP_BASE}/balance-sheet-statement").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{FMP_BASE}/cash-flow-statement").mock(return_value=httpx.Response(200, json=[]))

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "NOTATICKER"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
        assert body["financial_analysis"] is None
        assert any("retrieve financial data" in w for w in body["warnings"])
    finally:
        get_settings.cache_clear()


@respx.mock
def test_provider_failure_returns_failed_status(monkeypatch):
    _set_env(monkeypatch)
    respx.get(f"{FMP_BASE}/income-statement").mock(side_effect=httpx.ConnectError("refused"))
    respx.get(f"{FMP_BASE}/balance-sheet-statement").mock(side_effect=httpx.ConnectError("refused"))
    respx.get(f"{FMP_BASE}/cash-flow-statement").mock(side_effect=httpx.ConnectError("refused"))

    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/v1/analyze/ticker", json={"ticker": "ACME"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
    finally:
        get_settings.cache_clear()


@respx.mock
def test_provider_authentication_failure(monkeypatch):
    _set_env(monkeypatch, fmp_key="bad-key")
    respx.get(f"{FMP_BASE}/income-statement").mock(return_value=httpx.Response(401))
    respx.get(f"{FMP_BASE}/balance-sheet-statement").mock(return_value=httpx.Response(401))
    respx.get(f"{FMP_BASE}/cash-flow-statement").mock(return_value=httpx.Response(401))

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
        assert "bad-key" not in response.text
    finally:
        get_settings.cache_clear()


@respx.mock
def test_malformed_provider_data_still_returns_a_result(monkeypatch):
    _set_env(monkeypatch)
    # Missing 'date' fields -> the mapper skips these records but doesn't crash.
    respx.get(f"{FMP_BASE}/income-statement").mock(
        return_value=httpx.Response(200, json=[{"period": "FY", "revenue": 1000}])
    )
    respx.get(f"{FMP_BASE}/balance-sheet-statement").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{FMP_BASE}/cash-flow-statement").mock(return_value=httpx.Response(200, json=[]))
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        # Either genuinely no usable statements (failed) or an empty-but-valid
        # analysis (calculated/partial) -- either way, no crash, no 500.
        assert response.json()["status"] in ("failed", "calculated", "partial")
    finally:
        get_settings.cache_clear()


@respx.mock
def test_deterministic_pipeline_result_with_analyst_unavailable_is_partial(monkeypatch):
    _set_env(monkeypatch, llm_configured=False)
    _mock_fmp_success()

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "partial"
        assert body["financial_analysis"] is not None
        assert body["analyst"]["status"] == "error"
    finally:
        get_settings.cache_clear()


@respx.mock
def test_response_never_contains_raw_provider_field_names(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        text = response.text
        # FMP's raw camelCase field names must never leak into the response.
        assert "netIncome" not in text
        assert "cashAndCashEquivalents" not in text
        assert "weightedAverageShsOut" not in text
    finally:
        get_settings.cache_clear()


@respx.mock
def test_response_never_leaks_stack_trace(monkeypatch):
    _set_env(monkeypatch)
    respx.get(f"{FMP_BASE}/income-statement").mock(side_effect=httpx.ConnectError("refused"))
    respx.get(f"{FMP_BASE}/balance-sheet-statement").mock(side_effect=httpx.ConnectError("refused"))
    respx.get(f"{FMP_BASE}/cash-flow-statement").mock(side_effect=httpx.ConnectError("refused"))

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert "Traceback" not in response.text
        assert "File \"" not in response.text
    finally:
        get_settings.cache_clear()


def test_financial_data_provider_misconfigured_returns_failed(monkeypatch):
    monkeypatch.setenv("FINANCIAL_DATA_PROVIDER", "fmp")
    monkeypatch.setenv("FMP_API_KEY", "")

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
        assert "not configured" in " ".join(body["warnings"]).lower()
    finally:
        get_settings.cache_clear()


# --- Step 4: market-data-to-valuation wiring --------------------------------------

QUOTE_RECORD = {
    "symbol": "ACME", "price": 55.0, "previousClose": 50.0, "change": 5.0,
    "changePercentage": 10.0, "currency": "USD", "timestamp": int(time.time()),
}


def _mock_fmp_quote(freshness_record=None):
    respx.get(f"{FMP_BASE}/quote").mock(
        return_value=httpx.Response(200, json=[freshness_record or QUOTE_RECORD])
    )


@respx.mock
def test_ticker_analysis_automatically_resolves_current_price_into_valuation(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    _mock_fmp_quote()
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        # target_pe supplies the one extra assumption P/E valuation needs
        # (EPS itself already comes from INCOME_RECORD) -- everything else
        # about the request is untouched, so this isolates the effect of
        # the automatically-resolved current price on upside/downside.
        response = client.post(
            "/api/v1/analyze/ticker", json={"ticker": "ACME", "target_pe": "25"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "calculated"
        assert body["valuation"]["current_share_price"] == "55.0"
        pe_result = next(r for r in body["valuation"]["results"] if r["method"] == "pe")
        assert pe_result["status"] == "calculated"
        assert pe_result["upside_downside_status"] == "calculated"
        assert "fmp-secret-key" not in response.text
    finally:
        get_settings.cache_clear()


@respx.mock
def test_stale_quote_is_excluded_from_valuation(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    # timestamp far enough in the past to be classified STALE by the mapper.
    respx.get(f"{FMP_BASE}/quote").mock(
        return_value=httpx.Response(200, json=[{**QUOTE_RECORD, "timestamp": 1}])
    )
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        assert body["valuation"]["current_share_price"] is None
        assert any("stale" in w.lower() for w in body["warnings"])
        # Financial analysis must still be present -- a stale price never
        # takes down the rest of the analysis.
        assert body["financial_analysis"] is not None
    finally:
        get_settings.cache_clear()


@respx.mock
def test_market_quote_not_found_leaves_price_unavailable_without_crashing(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    respx.get(f"{FMP_BASE}/quote").mock(return_value=httpx.Response(200, json=[]))
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "calculated"
        assert body["valuation"]["current_share_price"] is None
        assert any("current market price is unavailable" in w.lower() for w in body["warnings"])
    finally:
        get_settings.cache_clear()


@respx.mock
def test_market_provider_failure_does_not_break_financial_analysis(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    respx.get(f"{FMP_BASE}/quote").mock(side_effect=httpx.ConnectError("refused"))
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        # The whole point of Step 4: a market outage degrades gracefully,
        # it never fails the request that financial data succeeded for.
        assert body["status"] == "calculated"
        assert body["financial_analysis"] is not None
        assert body["valuation"]["current_share_price"] is None
    finally:
        get_settings.cache_clear()


@respx.mock
def test_unmocked_quote_request_degrades_gracefully_not_a_crash(monkeypatch):
    """Every other test in this file that doesn't mock GET /quote relies
    on this exact behavior: an unconfigured/unmocked market request must
    never turn into a 500 or an unhandled exception."""
    _set_env(monkeypatch)
    _mock_fmp_success()
    _mock_llm_success()
    # Deliberately no respx mock for GET {FMP_BASE}/quote.

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "calculated"
        assert body["valuation"]["current_share_price"] is None
    finally:
        get_settings.cache_clear()


@respx.mock
def test_market_data_provider_misconfigured_still_runs_financial_analysis(monkeypatch):
    _set_env(monkeypatch)
    # An unknown MARKET_DATA_PROVIDER identifier must degrade cleanly --
    # financial data provider selection is untouched (FINANCIAL_DATA_PROVIDER
    # stays "fmp" via _set_env), only market-price resolution is skipped.
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "not-a-real-provider")
    _mock_fmp_success()
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "calculated"
        assert body["valuation"]["current_share_price"] is None
    finally:
        get_settings.cache_clear()


def test_generic_analyze_endpoint_still_accepts_explicit_current_share_price():
    """Step 4 must not touch the generic /analyze contract: it never
    fetches market data and an explicitly supplied current_share_price
    must still flow straight into valuation, exactly as before."""
    body = {
        "company_name": "Acme Corp",
        "ticker": "ACME",
        "current_share_price": "123.45",
        "company_financials": {
            "company_name": "Acme Corp",
            "ticker": "ACME",
            "income_statements": [{"period": "FY2024", "revenue": 1000, "eps": 2}],
        },
        "target_pe": "20",
    }
    response = client.post("/api/v1/analyze", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["valuation"]["current_share_price"] == "123.45"

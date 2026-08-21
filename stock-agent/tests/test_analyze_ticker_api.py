import json

import httpx
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)

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
    monkeypatch.setenv("FINANCIAL_DATA_BASE_URL", FMP_BASE)
    monkeypatch.setenv("FINANCIAL_DATA_API_KEY", fmp_key)
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
    monkeypatch.setenv("FINANCIAL_DATA_API_KEY", "")

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
        assert "not configured" in " ".join(body["warnings"]).lower()
    finally:
        get_settings.cache_clear()

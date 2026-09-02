import json

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

VALID_QA_RESPONSE = {
    "answer": "ROE is calculated at 24%, reflecting strong profitability based on the supplied data.",
    "evidence": {"financial": ["roe"], "valuation": [], "risk": [], "research": []},
    "recommendation_declined": False,
}

DECLINED_QA_RESPONSE = {
    "answer": "This assistant doesn't give buy/sell recommendations. ROE is calculated at 24%.",
    "evidence": {"financial": ["roe"], "valuation": [], "risk": [], "research": []},
    "recommendation_declined": True,
}


def _set_env(monkeypatch, llm_configured=True):
    monkeypatch.setenv("FINANCIAL_DATA_PROVIDER", "fmp")
    monkeypatch.setenv("FMP_BASE_URL", FMP_BASE)
    monkeypatch.setenv("FMP_API_KEY", "fmp-secret-key")
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


def _mock_llm(response=VALID_QA_RESPONSE):
    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(response)}}]})
    )


@respx.mock
def test_qa_ticker_endpoint_success(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    _mock_llm()

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/qa/ticker", json={"ticker": "ACME", "question": "How is profitability?"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert "24%" in body["response"]["answer"]
        assert body["response"]["recommendation_declined"] is False
        assert "fmp-secret-key" not in response.text
        assert "llm-secret-key" not in response.text
    finally:
        get_settings.cache_clear()


@respx.mock
def test_qa_ticker_endpoint_declines_buy_sell_question(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    _mock_llm(DECLINED_QA_RESPONSE)

    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/v1/qa/ticker", json={"ticker": "ACME", "question": "Is now the right time to buy?"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["response"]["recommendation_declined"] is True
    finally:
        get_settings.cache_clear()


def test_qa_ticker_endpoint_missing_question_returns_422():
    response = client.post("/api/v1/qa/ticker", json={"ticker": "ACME"})
    assert response.status_code == 422


def test_qa_ticker_endpoint_empty_question_returns_422():
    response = client.post("/api/v1/qa/ticker", json={"ticker": "ACME", "question": ""})
    assert response.status_code == 422


@respx.mock
def test_qa_ticker_endpoint_ticker_not_found(monkeypatch):
    _set_env(monkeypatch)
    respx.get(f"{FMP_BASE}/income-statement").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{FMP_BASE}/balance-sheet-statement").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{FMP_BASE}/cash-flow-statement").mock(return_value=httpx.Response(200, json=[]))

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/qa/ticker", json={"ticker": "NOTATICKER", "question": "Any good?"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["error"]["code"] == "data_unavailable"
    finally:
        get_settings.cache_clear()


@respx.mock
def test_qa_ticker_endpoint_llm_unconfigured(monkeypatch):
    _set_env(monkeypatch, llm_configured=False)

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/qa/ticker", json={"ticker": "ACME", "question": "Any good?"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["error"]["code"] == "llm_unavailable"
    finally:
        get_settings.cache_clear()


def test_qa_ticker_endpoint_financial_data_provider_misconfigured(monkeypatch):
    monkeypatch.setenv("FINANCIAL_DATA_PROVIDER", "fmp")
    monkeypatch.setenv("FMP_API_KEY", "")

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/qa/ticker", json={"ticker": "ACME", "question": "Any good?"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["error"]["code"] == "data_unavailable"
    finally:
        get_settings.cache_clear()

"""HTTP-level tests for `POST /api/v1/research/ticker` and the read-only
history/predictions endpoints -- end-to-end wiring through the real
FastAPI app, an in-memory SQLite DB, and mocked provider/LLM HTTP calls
(mirrors `tests/test_analyze_ticker_api.py`'s pattern)."""

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
    pass


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


def _set_env(monkeypatch):
    monkeypatch.setenv("FINANCIAL_DATA_PROVIDER", "fmp")
    monkeypatch.setenv("FMP_BASE_URL", FMP_BASE)
    monkeypatch.setenv("FMP_API_KEY", "fmp-secret-key")
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "fmp")
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")
    monkeypatch.setenv("LOCAL_LLM_API_KEY", "llm-secret-key")


def _mock_fmp_success():
    respx.get(f"{FMP_BASE}/income-statement").mock(return_value=httpx.Response(200, json=[INCOME_RECORD]))
    respx.get(f"{FMP_BASE}/balance-sheet-statement").mock(return_value=httpx.Response(200, json=[BALANCE_RECORD]))
    respx.get(f"{FMP_BASE}/cash-flow-statement").mock(return_value=httpx.Response(200, json=[CASH_FLOW_RECORD]))


def _mock_llm_success():
    return respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(VALID_ANALYST_RESPONSE)}}]})
    )


@respx.mock
def test_first_research_run_succeeds_and_saves_a_snapshot(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/research/ticker", json={"ticker": "ACME"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "COMPLETED"
        assert body["is_new_run"] is True
        assert body["run_type"] == "NORMAL"
        assert body["result"]["status"] == "calculated"
        assert body["result"]["analyst"]["status"] == "success"
        assert "fmp-secret-key" not in response.text
        assert "llm-secret-key" not in response.text
    finally:
        get_settings.cache_clear()


@respx.mock
def test_second_identical_request_reuses_snapshot_no_new_provider_or_llm_calls(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    llm_route = _mock_llm_success()

    get_settings.cache_clear()
    try:
        first = client.post("/api/v1/research/ticker", json={"ticker": "ACME"})
        assert first.status_code == 200
        first_body = first.json()

        second = client.post("/api/v1/research/ticker", json={"ticker": "ACME"})
        assert second.status_code == 200
        second_body = second.json()

        assert second_body["is_new_run"] is False
        assert second_body["research_run_id"] == first_body["research_run_id"]
        assert llm_route.call_count == 1
    finally:
        get_settings.cache_clear()


@respx.mock
def test_force_refresh_creates_a_new_run_and_history_keeps_both(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    llm_route = _mock_llm_success()

    get_settings.cache_clear()
    try:
        normal = client.post("/api/v1/research/ticker", json={"ticker": "ACME"}).json()
        forced = client.post(
            "/api/v1/research/ticker", json={"ticker": "ACME", "force_refresh": True}
        ).json()

        assert forced["is_new_run"] is True
        assert forced["run_type"] == "FORCE_REFRESH"
        assert forced["research_run_id"] != normal["research_run_id"]
        assert llm_route.call_count == 2

        history = client.get("/api/v1/research/ACME/history").json()
        run_ids = {row["id"] for row in history}
        assert run_ids == {normal["research_run_id"], forced["research_run_id"]}
        assert llm_route.call_count == 2  # history is a pure read, no recomputation

        specific = client.get(f"/api/v1/research/ACME/history/{normal['research_run_id']}").json()
        assert specific["research_run_id"] == normal["research_run_id"]
        assert specific["result"]["status"] == "calculated"
        assert llm_route.call_count == 2  # still no recomputation
    finally:
        get_settings.cache_clear()


@respx.mock
def test_failed_research_returns_failed_status_and_is_not_saved_as_a_report(monkeypatch):
    _set_env(monkeypatch)
    respx.get(f"{FMP_BASE}/income-statement").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{FMP_BASE}/balance-sheet-statement").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{FMP_BASE}/cash-flow-statement").mock(return_value=httpx.Response(200, json=[]))

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/research/ticker", json={"ticker": "NOTATICKER"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "FAILED"
        assert body["result"]["status"] == "failed"
    finally:
        get_settings.cache_clear()


def test_get_latest_research_404_when_none_exists():
    response = client.get("/api/v1/research/NEVERSEEN")
    assert response.status_code == 404


# --- GET /{ticker} overlays a live quote (opening a stock must never show a stale price) ---

_FRESH_QUOTE = {
    "symbol": "ACME", "price": 123.45, "previousClose": 120.0, "change": 3.45,
    "changePercentage": 2.875, "currency": "USD", "timestamp": int(time.time()),
}


@respx.mock
def test_opening_a_saved_snapshot_overlays_a_live_quote(monkeypatch):
    """The report saved at research time can be hours old by the time
    someone opens the stock -- GET /{ticker} must show a current price,
    not whatever was frozen into the report when it was computed."""
    _set_env(monkeypatch)
    _mock_fmp_success()
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        created = client.post("/api/v1/research/ticker", json={"ticker": "ACME"}).json()
        assert created["result"]["market_quote"] is None  # nothing configured a quote at creation time

        respx.get(f"{FMP_BASE}/quote").mock(return_value=httpx.Response(200, json=[_FRESH_QUOTE]))
        opened = client.get("/api/v1/research/ACME").json()

        assert opened["research_run_id"] == created["research_run_id"]  # same saved snapshot
        assert opened["result"]["market_quote"]["current_price"] == "123.45"
        assert opened["result"]["report"]["market"]["current_price"] == "123.45"
    finally:
        get_settings.cache_clear()


@respx.mock
def test_a_failed_live_quote_fetch_still_returns_the_saved_snapshot(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        client.post("/api/v1/research/ticker", json={"ticker": "ACME"})

        respx.get(f"{FMP_BASE}/quote").mock(side_effect=httpx.ConnectError("refused"))
        opened = client.get("/api/v1/research/ACME")

        assert opened.status_code == 200
        assert opened.json()["result"]["market_quote"] is None
    finally:
        get_settings.cache_clear()


@respx.mock
def test_predictions_endpoint_returns_forecast_rows_with_target_dates(monkeypatch):
    _set_env(monkeypatch)
    _mock_fmp_success()
    _mock_llm_success()

    get_settings.cache_clear()
    try:
        client.post("/api/v1/research/ticker", json={"ticker": "ACME"})
        predictions = client.get("/api/v1/research/ACME/predictions").json()
        assert len(predictions) > 0
        assert {p["horizon"] for p in predictions} <= {"DAILY", "WEEKLY", "MONTHLY"}
        for p in predictions:
            assert "prediction_date" in p and p["prediction_date"] is not None
            assert "target_date" in p  # may be None only when status != calculated

        daily_only = client.get("/api/v1/research/ACME/predictions", params={"horizon": "DAILY"}).json()
        assert all(p["horizon"] == "DAILY" for p in daily_only)
    finally:
        get_settings.cache_clear()


def test_missing_ticker_returns_422():
    response = client.post("/api/v1/research/ticker", json={})
    assert response.status_code == 422

import json
from decimal import Decimal

import httpx
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def d(value) -> Decimal:
    return Decimal(str(value))


VALID_ANALYST_RESPONSE = {
    "investment_thesis": {"text": "Solid fundamentals.", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "strengths": ["Positive revenue"],
    "weaknesses": [],
    "profitability_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "growth_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "financial_health_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "cash_flow_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "valuation_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "risk_analysis": {"text": "n/a", "evidence": {"financial": [], "valuation": [], "risk": [], "research": []}},
    "key_takeaways": [],
    "caveats": [],
}


def _minimal_request_body(**overrides):
    body = {
        "company_name": "Acme Corp",
        "ticker": "ACME",
        "company_financials": {
            "company_name": "Acme Corp",
            "ticker": "ACME",
            "income_statements": [
                {"period": "FY2024", "revenue": "1000", "net_income": "100", "eps": "2.00", "shares_outstanding": "50"}
            ],
            "balance_sheets": [
                {"period": "FY2024", "total_debt": "200", "cash_and_equivalents": "80"}
            ],
            "cash_flow_statements": [],
        },
    }
    body.update(overrides)
    return body


@respx.mock
def test_analyze_endpoint_with_research_enabled(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")
    monkeypatch.setenv("RESEARCH_PROVIDER", "finnhub")
    monkeypatch.setenv("RESEARCH_API_KEY", "research-secret-key")
    monkeypatch.setenv("RESEARCH_BASE_URL", "http://test-finnhub:9999/api/v1")

    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(VALID_ANALYST_RESPONSE)}}]}
        )
    )
    respx.get("http://test-finnhub:9999/api/v1/company-news").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "category": "company", "datetime": 1767225600, "headline": "Acme Corp expands",
                    "source": "Example News", "summary": "Expansion news.", "url": "https://example.com/a",
                }
            ],
        )
    )

    get_settings.cache_clear()
    try:
        body = _minimal_request_body(research={"enabled": True})
        response = client.post("/api/v1/analyze", json=body)
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "calculated"
        assert result["research"] is not None
        assert result["research"]["status"] == "success"
        assert len(result["research"]["items"]) == 1
        assert result["research"]["items"][0]["id"] == "research_001"
        assert "research-secret-key" not in response.text
    finally:
        get_settings.cache_clear()


@respx.mock
def test_analyze_endpoint_research_not_requested_by_default(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")
    monkeypatch.setenv("RESEARCH_PROVIDER", "finnhub")
    monkeypatch.setenv("RESEARCH_API_KEY", "research-secret-key")

    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(VALID_ANALYST_RESPONSE)}}]}
        )
    )
    # No respx route registered for company-news -- if the app called it
    # unexpectedly, respx would raise, failing this test.

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze", json=_minimal_request_body())
        assert response.status_code == 200
        assert response.json()["research"] is None
    finally:
        get_settings.cache_clear()


@respx.mock
def test_analyze_endpoint_full_success(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")
    monkeypatch.setenv("LOCAL_LLM_API_KEY", "super-secret-key")

    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(VALID_ANALYST_RESPONSE)}}]}
        )
    )

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze", json=_minimal_request_body())
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "calculated"
        assert body["company"]["name"] == "Acme Corp"
        assert body["financial_analysis"] is not None
        assert body["valuation"] is not None
        assert body["scoring"] is not None
        assert body["analyst"]["status"] == "success"
        assert "super-secret-key" not in response.text
    finally:
        get_settings.cache_clear()


@respx.mock
def test_analyze_endpoint_partial_when_analyst_unavailable(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")

    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze", json=_minimal_request_body())
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "partial"
        assert body["financial_analysis"] is not None
        assert body["valuation"] is not None
        assert body["scoring"] is not None
        assert body["analyst"]["status"] == "error"
    finally:
        get_settings.cache_clear()


def test_analyze_endpoint_partial_when_llm_misconfigured(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "")

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze", json=_minimal_request_body())
        assert response.status_code == 200
        body = response.json()
        # Deterministic stages still ran despite the LLM being unusable.
        assert body["status"] == "partial"
        assert body["financial_analysis"] is not None
        assert body["analyst"]["status"] == "error"
        assert body["analyst"]["error"]["code"] == "llm_unavailable"
    finally:
        get_settings.cache_clear()


def test_analyze_endpoint_invalid_request_missing_required_field():
    response = client.post("/api/v1/analyze", json={"ticker": "ACME"})  # missing company_name, company_financials
    assert response.status_code == 422


def test_analyze_endpoint_invalid_request_wrong_type():
    body = _minimal_request_body(discount_rate="not-a-number")
    response = client.post("/api/v1/analyze", json=body)
    assert response.status_code == 422


def test_analyze_endpoint_response_never_leaks_stack_trace(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "")

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze", json=_minimal_request_body())
        assert "Traceback" not in response.text
        assert "File \"" not in response.text
    finally:
        get_settings.cache_clear()


def test_analyze_endpoint_deterministic_result_usable_with_no_valuation_assumptions(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "")

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze", json=_minimal_request_body())
        body = response.json()
        # No discount rate etc. supplied -> DCF must be unavailable, not fabricated.
        dcf = next(r for r in body["valuation"]["results"] if r["method"] == "dcf")
        assert dcf["status"] == "unavailable"
        assert dcf["value_per_share"] is None
    finally:
        get_settings.cache_clear()

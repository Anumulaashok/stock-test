import json

import httpx
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)

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
def test_analyze_with_include_report_returns_structured_report(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")
    monkeypatch.setenv("LOCAL_LLM_API_KEY", "super-secret-key")

    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(VALID_ANALYST_RESPONSE)}}]})
    )

    get_settings.cache_clear()
    try:
        body = _minimal_request_body(include_report=True)
        response = client.post("/api/v1/analyze", json=body)
        assert response.status_code == 200
        result = response.json()
        assert result["report"] is not None
        assert result["report"]["status"] == "calculated"
        assert result["report"]["company"]["name"] == "Acme Corp"
        assert result["report"]["metadata"]["report_version"] == "1.0"
        assert "super-secret-key" not in response.text
    finally:
        get_settings.cache_clear()


@respx.mock
def test_analyze_without_include_report_omits_report(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")

    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(VALID_ANALYST_RESPONSE)}}]})
    )

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze", json=_minimal_request_body())
        assert response.status_code == 200
        assert response.json()["report"] is None
    finally:
        get_settings.cache_clear()


def test_analyze_with_include_report_partial_when_llm_unavailable(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "")

    get_settings.cache_clear()
    try:
        body = _minimal_request_body(include_report=True)
        response = client.post("/api/v1/analyze", json=body)
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "partial"
        assert result["report"]["status"] == "partial"
        assert result["report"]["analyst"]["available"] is False
        # Deterministic sections still fully populated in the report.
        assert result["report"]["financials"] is not None
        assert result["report"]["valuation"] is not None
    finally:
        get_settings.cache_clear()


def test_analyze_invalid_request_missing_required_field():
    response = client.post("/api/v1/analyze", json={"include_report": True})
    assert response.status_code == 422


def test_analyze_with_report_no_stack_trace_leaked(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "")

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze", json=_minimal_request_body(include_report=True))
        assert "Traceback" not in response.text
        assert "File \"" not in response.text
    finally:
        get_settings.cache_clear()


def test_analyze_report_serializes_cleanly_end_to_end(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "")

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyze", json=_minimal_request_body(include_report=True))
        body = response.json()
        # DCF unavailable (no assumptions supplied) -- report reflects it, never fabricates a value.
        dcf = next(m for m in body["report"]["valuation"]["methods"] if m["method"] == "dcf")
        assert dcf["status"] == "unavailable"
        assert dcf["value_per_share"] is None
    finally:
        get_settings.cache_clear()

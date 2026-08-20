import json
from decimal import Decimal

import httpx
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models.financial_results import FinancialAnalysisResult, FinancialMetricResult
from app.models.financial_results import MetricStatus as FMS
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult

client = TestClient(app)


def d(value) -> Decimal:
    return Decimal(str(value))


VALID_RESPONSE = {
    "investment_thesis": {"text": "Strong profitability.", "evidence": ["roe"]},
    "strengths": ["High ROE"],
    "weaknesses": [],
    "profitability_analysis": {"text": "ROE is strong.", "evidence": ["roe"]},
    "growth_analysis": {"text": "unavailable", "evidence": []},
    "financial_health_analysis": {"text": "n/a", "evidence": []},
    "cash_flow_analysis": {"text": "n/a", "evidence": []},
    "valuation_analysis": {"text": "n/a", "evidence": []},
    "risk_analysis": {"text": "n/a", "evidence": []},
    "key_takeaways": ["ROE is a strength"],
    "caveats": ["Limited data available"],
}


def _request_body():
    financial_analysis = FinancialAnalysisResult(
        company="Acme Corp",
        periods_analyzed=["FY2024"],
        metrics=[FinancialMetricResult(name="roe", value=d(24), unit="%", status=FMS.CALCULATED)],
    )
    scoring = ScoringResult(
        company_name="Acme Corp",
        overall_score=d(78),
        overall_status=ScoreStatus.CALCULATED,
        category_scores=[
            CategoryScore(category="profitability", score=d(87), weight=d("0.20"), status=ScoreStatus.CALCULATED),
        ],
    )
    return {
        "financial_analysis": json.loads(financial_analysis.model_dump_json()),
        "valuation": None,
        "scoring": json.loads(scoring.model_dump_json()),
        "company_financials": None,
    }


@respx.mock
def test_analyst_endpoint_success(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")
    monkeypatch.setenv("LOCAL_LLM_API_KEY", "super-secret-key")

    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(VALID_RESPONSE)}}]}
        )
    )

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyst", json=_request_body())
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["response"]["company_name"] == "Acme Corp"
        assert "super-secret-key" not in response.text
    finally:
        get_settings.cache_clear()


@respx.mock
def test_analyst_endpoint_llm_unavailable(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")

    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyst", json=_request_body())
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["error"]["code"] == "llm_unavailable"
    finally:
        get_settings.cache_clear()


def test_analyst_endpoint_misconfigured(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "")

    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/analyst", json=_request_body())
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["error"]["code"] == "llm_unavailable"
    finally:
        get_settings.cache_clear()

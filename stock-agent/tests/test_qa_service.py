import json
from decimal import Decimal
from typing import Any

import pytest

from app.analyst.context import build_analyst_context
from app.llm.base import LLMProvider, LLMProviderError
from app.models.financial_results import FinancialAnalysisResult, FinancialMetricResult
from app.models.financial_results import MetricStatus as FMS
from app.models.qa import QAErrorCode
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult
from app.qa.service import QAService


def d(value) -> Decimal:
    return Decimal(str(value))


def _financial_analysis():
    return FinancialAnalysisResult(
        company="Acme Corp",
        periods_analyzed=["FY2024"],
        metrics=[FinancialMetricResult(name="roe", value=d(24), unit="%", status=FMS.CALCULATED)],
    )


def _scoring():
    return ScoringResult(
        company_name="Acme Corp",
        overall_score=d(78),
        overall_status=ScoreStatus.CALCULATED,
        category_scores=[
            CategoryScore(category="profitability", score=d(87), weight=d("0.20"), status=ScoreStatus.CALCULATED),
        ],
    )


def _context():
    return build_analyst_context(_financial_analysis(), None, _scoring())


_EMPTY_EVIDENCE = {"financial": [], "valuation": [], "risk": [], "research": []}


def _evidence(**overrides):
    e = dict(_EMPTY_EVIDENCE)
    e.update(overrides)
    return e


VALID_RESPONSE = {
    "answer": "ROE is 24%, which is calculated and reflects strong profitability.",
    "evidence": _evidence(financial=["roe"]),
    "recommendation_declined": False,
}

DECLINED_RESPONSE = {
    "answer": "I can't give a buy/sell recommendation or a price probability. ROE is 24%.",
    "evidence": _evidence(financial=["roe"]),
    "recommendation_declined": True,
}


class FakeLLMProvider(LLMProvider):
    def __init__(self, responses: list[str] | None = None, error: Exception | None = None):
        self._responses = list(responses or [])
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def generate(self, prompt: str, system_prompt: str | None = None, **kwargs: Any) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt, **kwargs})
        if self._error is not None:
            raise self._error
        return self._responses.pop(0)

    async def generate_structured(self, prompt: str, schema: dict, **kwargs: Any) -> dict:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_service_successful_response():
    provider = FakeLLMProvider(responses=[json.dumps(VALID_RESPONSE)])
    service = QAService(provider)

    result = await service.answer(_context(), "How is Acme Corp's profitability?")

    assert result.status == "success"
    assert "24%" in result.response.answer
    assert result.response.evidence.financial == ["roe"]
    assert result.response.recommendation_declined is False


@pytest.mark.asyncio
async def test_service_sends_system_prompt_with_guardrails_and_question():
    provider = FakeLLMProvider(responses=[json.dumps(VALID_RESPONSE)])
    service = QAService(provider)

    await service.answer(_context(), "Is it the right time to buy?")

    call = provider.calls[0]
    assert "buy" in call["system_prompt"].lower()
    assert "probability" in call["system_prompt"].lower()
    assert "Is it the right time to buy?" in call["prompt"]
    assert "Structured Context" in call["prompt"]


@pytest.mark.asyncio
async def test_service_reports_declined_recommendation():
    provider = FakeLLMProvider(responses=[json.dumps(DECLINED_RESPONSE)])
    service = QAService(provider)

    result = await service.answer(_context(), "Should I buy this stock right now?")

    assert result.status == "success"
    assert result.response.recommendation_declined is True


@pytest.mark.asyncio
async def test_service_uses_default_max_response_tokens():
    provider = FakeLLMProvider(responses=[json.dumps(VALID_RESPONSE)])
    service = QAService(provider)

    await service.answer(_context(), "How is profitability?")

    assert provider.calls[0]["max_tokens"] == 400


@pytest.mark.asyncio
async def test_service_uses_configured_max_response_tokens():
    provider = FakeLLMProvider(responses=[json.dumps(VALID_RESPONSE)])
    service = QAService(provider, max_response_tokens=1200)

    await service.answer(_context(), "How is profitability?")

    assert provider.calls[0]["max_tokens"] == 1200


@pytest.mark.asyncio
async def test_service_llm_timeout_returns_structured_error():
    provider = FakeLLMProvider(error=LLMProviderError("Local LLM request timed out"))
    service = QAService(provider)

    result = await service.answer(_context(), "How is profitability?")

    assert result.status == "error"
    assert result.error.code is QAErrorCode.TIMEOUT


@pytest.mark.asyncio
async def test_service_empty_response_after_retries_returns_error():
    provider = FakeLLMProvider(responses=["", ""])
    service = QAService(provider, max_retries=1)

    result = await service.answer(_context(), "How is profitability?")

    assert result.status == "error"
    assert result.error.code is QAErrorCode.EMPTY_RESPONSE
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_service_malformed_json_after_retries_returns_error():
    provider = FakeLLMProvider(responses=["not json", "still not json"])
    service = QAService(provider, max_retries=1)

    result = await service.answer(_context(), "How is profitability?")

    assert result.status == "error"
    assert result.error.code is QAErrorCode.MALFORMED_JSON


@pytest.mark.asyncio
async def test_service_missing_field_after_retries_returns_error():
    incomplete = dict(VALID_RESPONSE)
    del incomplete["evidence"]
    provider = FakeLLMProvider(responses=[json.dumps(incomplete), json.dumps(incomplete)])
    service = QAService(provider, max_retries=1)

    result = await service.answer(_context(), "How is profitability?")

    assert result.status == "error"
    assert result.error.code is QAErrorCode.MISSING_FIELD


@pytest.mark.asyncio
async def test_service_filters_invalid_evidence_reference():
    tainted = dict(VALID_RESPONSE)
    tainted["evidence"] = _evidence(financial=["not_a_real_metric"])
    provider = FakeLLMProvider(responses=[json.dumps(tainted)])
    service = QAService(provider)

    result = await service.answer(_context(), "How is profitability?")

    assert result.status == "success"
    assert result.response.evidence.financial == []


@pytest.mark.asyncio
async def test_service_rejects_recommendation_field_in_response():
    tainted = dict(VALID_RESPONSE)
    tainted["recommendation"] = "BUY"
    provider = FakeLLMProvider(responses=[json.dumps(tainted), json.dumps(tainted)])
    service = QAService(provider, max_retries=1)

    result = await service.answer(_context(), "Should I buy this stock?")

    assert result.status == "error"
    assert result.error.code is QAErrorCode.UNEXPECTED_RECOMMENDATION_FIELD


@pytest.mark.asyncio
async def test_service_retries_once_then_succeeds():
    provider = FakeLLMProvider(responses=["not json", json.dumps(VALID_RESPONSE)])
    service = QAService(provider, max_retries=1)

    result = await service.answer(_context(), "How is profitability?")

    assert result.status == "success"
    assert len(provider.calls) == 2

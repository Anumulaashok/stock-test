import json
from decimal import Decimal
from typing import Any

import pytest

from app.analyst.service import AnalystService
from app.llm.base import LLMProvider, LLMProviderError
from app.models.analyst import AnalystErrorCode
from app.models.financial_results import FinancialAnalysisResult, FinancialMetricResult
from app.models.financial_results import MetricStatus as FMS
from app.models.research import ResearchError, ResearchErrorCode, ResearchItem, ResearchResult, ResearchSource
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult


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


_EMPTY_EVIDENCE = {"financial": [], "valuation": [], "risk": [], "research": []}


def _evidence(**overrides):
    e = dict(_EMPTY_EVIDENCE)
    e.update(overrides)
    return e


VALID_RESPONSE = {
    "investment_thesis": {"text": "Strong profitability.", "evidence": _evidence(financial=["roe"])},
    "strengths": ["High ROE"],
    "weaknesses": [],
    "profitability_analysis": {"text": "ROE is strong.", "evidence": _evidence(financial=["roe"])},
    "growth_analysis": {"text": "unavailable", "evidence": _evidence()},
    "financial_health_analysis": {"text": "n/a", "evidence": _evidence()},
    "cash_flow_analysis": {"text": "n/a", "evidence": _evidence()},
    "valuation_analysis": {"text": "n/a", "evidence": _evidence()},
    "risk_analysis": {"text": "n/a", "evidence": _evidence()},
    "key_takeaways": ["ROE is a strength"],
    "caveats": ["Limited data available"],
}


class FakeLLMProvider(LLMProvider):
    """Scripted fake used to test the service without a real HTTP call."""

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
    service = AnalystService(provider)

    result = await service.analyze(_financial_analysis(), None, _scoring())

    assert result.status == "success"
    assert result.response.company_name == "Acme Corp"
    assert result.response.investment_thesis.text == "Strong profitability."
    assert result.error is None


@pytest.mark.asyncio
async def test_service_sends_system_prompt_and_user_prompt():
    provider = FakeLLMProvider(responses=[json.dumps(VALID_RESPONSE)])
    service = AnalystService(provider)

    await service.analyze(_financial_analysis(), None, _scoring())

    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call["system_prompt"] is not None
    assert "buy" in call["system_prompt"].lower() or "recommendation" in call["system_prompt"].lower()
    assert "Structured Context" in call["prompt"]


@pytest.mark.asyncio
async def test_service_uses_default_max_response_tokens():
    provider = FakeLLMProvider(responses=[json.dumps(VALID_RESPONSE)])
    service = AnalystService(provider)

    await service.analyze(_financial_analysis(), None, _scoring())

    assert provider.calls[0]["max_tokens"] == 700


@pytest.mark.asyncio
async def test_service_uses_configured_max_response_tokens():
    provider = FakeLLMProvider(responses=[json.dumps(VALID_RESPONSE)])
    service = AnalystService(provider, max_response_tokens=2200)

    await service.analyze(_financial_analysis(), None, _scoring())

    assert provider.calls[0]["max_tokens"] == 2200


@pytest.mark.asyncio
async def test_service_llm_timeout_returns_structured_error():
    provider = FakeLLMProvider(error=LLMProviderError("Local LLM request timed out"))
    service = AnalystService(provider)

    result = await service.analyze(_financial_analysis(), None, _scoring())

    assert result.status == "error"
    assert result.error.code is AnalystErrorCode.TIMEOUT
    assert result.response is None


@pytest.mark.asyncio
async def test_service_llm_unavailable_returns_structured_error():
    provider = FakeLLMProvider(error=LLMProviderError("Local LLM request failed"))
    service = AnalystService(provider)

    result = await service.analyze(_financial_analysis(), None, _scoring())

    assert result.status == "error"
    assert result.error.code is AnalystErrorCode.LLM_UNAVAILABLE


@pytest.mark.asyncio
async def test_service_empty_response_after_retries_returns_error():
    provider = FakeLLMProvider(responses=["", ""])
    service = AnalystService(provider, max_retries=1)

    result = await service.analyze(_financial_analysis(), None, _scoring())

    assert result.status == "error"
    assert result.error.code is AnalystErrorCode.EMPTY_RESPONSE
    assert len(provider.calls) == 2  # initial + 1 retry


@pytest.mark.asyncio
async def test_service_malformed_json_after_retries_returns_error():
    provider = FakeLLMProvider(responses=["not json", "still not json"])
    service = AnalystService(provider, max_retries=1)

    result = await service.analyze(_financial_analysis(), None, _scoring())

    assert result.status == "error"
    assert result.error.code is AnalystErrorCode.MALFORMED_JSON


@pytest.mark.asyncio
async def test_service_missing_fields_after_retries_returns_error():
    incomplete = dict(VALID_RESPONSE)
    del incomplete["risk_analysis"]
    provider = FakeLLMProvider(responses=[json.dumps(incomplete), json.dumps(incomplete)])
    service = AnalystService(provider, max_retries=1)

    result = await service.analyze(_financial_analysis(), None, _scoring())

    assert result.status == "error"
    assert result.error.code is AnalystErrorCode.MISSING_FIELD


@pytest.mark.asyncio
async def test_service_retries_once_then_succeeds():
    provider = FakeLLMProvider(responses=["not json", json.dumps(VALID_RESPONSE)])
    service = AnalystService(provider, max_retries=1)

    result = await service.analyze(_financial_analysis(), None, _scoring())

    assert result.status == "success"
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_service_rejects_recommendation_field_in_response():
    tainted = dict(VALID_RESPONSE)
    tainted["recommendation"] = "BUY"
    provider = FakeLLMProvider(responses=[json.dumps(tainted), json.dumps(tainted)])
    service = AnalystService(provider, max_retries=1)

    result = await service.analyze(_financial_analysis(), None, _scoring())

    assert result.status == "error"
    assert result.error.code is AnalystErrorCode.UNEXPECTED_RECOMMENDATION_FIELD


@pytest.mark.asyncio
async def test_service_never_raises_on_missing_valuation_or_minimal_scoring():
    minimal_scoring = ScoringResult(
        company_name="Acme Corp", overall_score=None, overall_status=ScoreStatus.UNAVAILABLE,
    )
    provider = FakeLLMProvider(responses=[json.dumps(VALID_RESPONSE)])
    service = AnalystService(provider)

    result = await service.analyze(_financial_analysis(), None, minimal_scoring)

    assert result.status == "success"


# --- Research integration (Step 8) --------------------------------------------------


def _research_result(item_id="research_001", status="success"):
    if status != "success":
        return ResearchResult(
            status="error", error=ResearchError(code=ResearchErrorCode.PROVIDER_UNAVAILABLE, message="down"),
            retrieved_at="2026-01-01T00:00:00+00:00",
        )
    item = ResearchItem(
        id=item_id, title="Acme Corp expands into new market", summary="A summary.",
        source=ResearchSource(title="Acme Corp expands into new market", publisher="Example News",
                               url="https://example.com/a", published_at="2026-01-01T00:00:00+00:00"),
        published_at="2026-01-01T00:00:00+00:00",
    )
    return ResearchResult(status="success", items=[item], sources=[item.source], retrieved_at="2026-01-01T00:00:00+00:00")


@pytest.mark.asyncio
async def test_service_includes_research_context_in_prompt_when_available():
    response_with_research = dict(VALID_RESPONSE)
    response_with_research["risk_analysis"] = {
        "text": "context", "evidence": _evidence(risk=["high_debt_to_equity"], research=["research_001"]),
    }
    provider = FakeLLMProvider(responses=[json.dumps(response_with_research)])
    service = AnalystService(provider)

    result = await service.analyze(_financial_analysis(), None, _scoring(), research=_research_result())

    assert result.status == "success"
    assert "research_001" in provider.calls[0]["prompt"]
    assert "EXTERNAL RESEARCH CONTEXT" in provider.calls[0]["prompt"]
    assert result.response.risk_analysis.evidence.research == ["research_001"]


@pytest.mark.asyncio
async def test_service_omits_research_items_when_research_unavailable():
    provider = FakeLLMProvider(responses=[json.dumps(VALID_RESPONSE)])
    service = AnalystService(provider)

    await service.analyze(_financial_analysis(), None, _scoring(), research=_research_result(status="error"))

    prompt = provider.calls[0]["prompt"]
    assert '"research_available":false' in prompt.replace(" ", "")
    assert '"research_items":[]' in prompt.replace(" ", "")
    # The actual article content must not appear -- only the fixed schema
    # instructions may mention the literal string "research_001" as an example.
    assert "Acme Corp expands into new market" not in prompt
    assert "example.com/a" not in prompt


@pytest.mark.asyncio
async def test_service_filters_invalid_research_reference():
    response_with_bad_research = dict(VALID_RESPONSE)
    response_with_bad_research["risk_analysis"] = {
        "text": "context", "evidence": _evidence(research=["research_999"]),  # not in supplied research
    }
    provider = FakeLLMProvider(responses=[json.dumps(response_with_bad_research)])
    service = AnalystService(provider)

    result = await service.analyze(_financial_analysis(), None, _scoring(), research=_research_result())

    assert result.status == "success"
    assert result.response.risk_analysis.evidence.research == []


@pytest.mark.asyncio
async def test_service_financial_and_research_evidence_stay_separate():
    response = dict(VALID_RESPONSE)
    response["risk_analysis"] = {
        "text": "context",
        "evidence": _evidence(financial=["roe"], research=["research_001"]),
    }
    provider = FakeLLMProvider(responses=[json.dumps(response)])
    service = AnalystService(provider)

    result = await service.analyze(_financial_analysis(), None, _scoring(), research=_research_result())

    assert result.response.risk_analysis.evidence.financial == ["roe"]
    assert result.response.risk_analysis.evidence.research == ["research_001"]

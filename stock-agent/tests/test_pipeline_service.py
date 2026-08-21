from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.analyst import AnalystError, AnalystErrorCode, AnalystResponse, AnalystResult, AnalystSection
from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_statements import CompanyFinancials
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult
from app.models.valuation import ValuationRange
from app.pipeline.models import AnalysisRequest, PipelineStatus
from app.pipeline.service import AnalysisPipelineService


def d(value) -> Decimal:
    return Decimal(str(value))


def _request():
    return AnalysisRequest(
        company_name="Acme Corp", ticker="ACME",
        company_financials=CompanyFinancials(company_name="Acme Corp"),
    )


def _financial_analysis(warnings=None):
    return FinancialAnalysisResult(
        company="Acme Corp", periods_analyzed=["FY2024"], metrics=[], warnings=warnings or [],
    )


def _valuation(warnings=None):
    return ValuationRange(company="Acme Corp", results=[], warnings=warnings or [])


def _scoring(warnings=None):
    return ScoringResult(
        company_name="Acme Corp", overall_score=d(70), overall_status=ScoreStatus.CALCULATED,
        category_scores=[
            CategoryScore(category="profitability", score=d(70), weight=d("1.0"), status=ScoreStatus.CALCULATED),
        ],
        warnings=warnings or [],
    )


def _analyst_success():
    section = AnalystSection(text="ok")
    return AnalystResult(
        status="success",
        response=AnalystResponse(
            company_name="Acme Corp", investment_thesis=section, profitability_analysis=section,
            growth_analysis=section, financial_health_analysis=section, cash_flow_analysis=section,
            valuation_analysis=section, risk_analysis=section,
        ),
    )


class FakeFinancialService:
    def __init__(self, result=None, raises=None):
        self._result = result or _financial_analysis()
        self._raises = raises

    def analyze(self, company_financials):
        if self._raises:
            raise self._raises
        return self._result


class FakeValuationService:
    def __init__(self, result=None, raises=None):
        self._result = result or _valuation()
        self._raises = raises
        self.calls = []

    def analyze(self, valuation_input):
        self.calls.append(valuation_input)
        if self._raises:
            raise self._raises
        return self._result


class FakeScoringService:
    def __init__(self, result=None, raises=None):
        self._result = result or _scoring()
        self._raises = raises

    def analyze(self, financial_analysis, valuation):
        if self._raises:
            raise self._raises
        return self._result


class FakeAnalystService:
    def __init__(self, result=None, raises=None):
        self._result = result or _analyst_success()
        self._raises = raises
        self.calls = []

    async def analyze(self, financial_analysis, valuation, scoring, company_financials=None, research=None):
        self.calls.append((financial_analysis, valuation, scoring, company_financials))
        if self._raises:
            raise self._raises
        return self._result


def _pipeline(financial=None, valuation=None, scoring=None, analyst=None, clock=None):
    return AnalysisPipelineService(
        financial_service=financial or FakeFinancialService(),
        valuation_service=valuation or FakeValuationService(),
        scoring_service=scoring or FakeScoringService(),
        analyst_service=analyst or FakeAnalystService(),
        clock=clock,
    )


@pytest.mark.asyncio
async def test_full_pipeline_success_is_calculated():
    pipeline = _pipeline()
    result = await pipeline.analyze(_request())

    assert result.status is PipelineStatus.CALCULATED
    assert result.company.name == "Acme Corp"
    assert result.company.ticker == "ACME"
    assert result.financial_analysis is not None
    assert result.valuation is not None
    assert result.scoring is not None
    assert result.analyst.status == "success"


@pytest.mark.asyncio
async def test_financial_analysis_failure_yields_failed_status():
    pipeline = _pipeline(financial=FakeFinancialService(raises=RuntimeError("boom")))
    result = await pipeline.analyze(_request())

    assert result.status is PipelineStatus.FAILED
    assert result.financial_analysis is None
    assert result.valuation is None
    assert result.scoring is None
    assert result.analyst is None
    assert any("financial_analysis" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_valuation_failure_keeps_financial_analysis_and_fails():
    pipeline = _pipeline(valuation=FakeValuationService(raises=RuntimeError("boom")))
    result = await pipeline.analyze(_request())

    assert result.status is PipelineStatus.FAILED
    assert result.financial_analysis is not None  # deterministic result already computed is kept
    assert result.valuation is None
    assert result.scoring is None


@pytest.mark.asyncio
async def test_scoring_failure_keeps_financial_and_valuation_and_fails():
    pipeline = _pipeline(scoring=FakeScoringService(raises=RuntimeError("boom")))
    result = await pipeline.analyze(_request())

    assert result.status is PipelineStatus.FAILED
    assert result.financial_analysis is not None
    assert result.valuation is not None
    assert result.scoring is None
    assert result.analyst is None


@pytest.mark.asyncio
async def test_analyst_error_yields_partial_status_with_deterministic_results_intact():
    error_result = AnalystResult(
        status="error", error=AnalystError(code=AnalystErrorCode.TIMEOUT, message="Local LLM request timed out")
    )
    pipeline = _pipeline(analyst=FakeAnalystService(result=error_result))
    result = await pipeline.analyze(_request())

    assert result.status is PipelineStatus.PARTIAL
    assert result.financial_analysis is not None
    assert result.valuation is not None
    assert result.scoring is not None
    assert result.analyst.status == "error"
    assert result.analyst.error.code is AnalystErrorCode.TIMEOUT
    assert any("analyst" in w.lower() for w in result.warnings)


@pytest.mark.asyncio
async def test_analyst_timeout_specifically():
    error_result = AnalystResult(
        status="error", error=AnalystError(code=AnalystErrorCode.TIMEOUT, message="timed out")
    )
    pipeline = _pipeline(analyst=FakeAnalystService(result=error_result))
    result = await pipeline.analyze(_request())
    assert result.status is PipelineStatus.PARTIAL
    assert result.analyst.error.code is AnalystErrorCode.TIMEOUT


@pytest.mark.asyncio
async def test_analyst_malformed_response_specifically():
    error_result = AnalystResult(
        status="error", error=AnalystError(code=AnalystErrorCode.MALFORMED_JSON, message="bad json")
    )
    pipeline = _pipeline(analyst=FakeAnalystService(result=error_result))
    result = await pipeline.analyze(_request())
    assert result.status is PipelineStatus.PARTIAL
    assert result.analyst.error.code is AnalystErrorCode.MALFORMED_JSON


@pytest.mark.asyncio
async def test_analyst_unexpected_exception_degrades_to_partial_not_failed():
    pipeline = _pipeline(analyst=FakeAnalystService(raises=RuntimeError("unexpected")))
    result = await pipeline.analyze(_request())

    assert result.status is PipelineStatus.PARTIAL
    assert result.analyst.status == "error"
    assert result.financial_analysis is not None
    assert result.scoring is not None


@pytest.mark.asyncio
async def test_warnings_propagate_from_every_stage():
    pipeline = _pipeline(
        financial=FakeFinancialService(result=_financial_analysis(warnings=["financial warning"])),
        valuation=FakeValuationService(result=_valuation(warnings=["valuation warning"])),
        scoring=FakeScoringService(result=_scoring(warnings=["scoring warning"])),
    )
    result = await pipeline.analyze(_request())

    assert "financial warning" in result.warnings
    assert "valuation warning" in result.warnings
    assert "scoring warning" in result.warnings


@pytest.mark.asyncio
async def test_no_fabricated_assumptions_flow_through_to_valuation_input():
    financial = FakeFinancialService()
    valuation = FakeValuationService()
    pipeline = _pipeline(financial=financial, valuation=valuation)
    request = AnalysisRequest(
        company_name="Acme Corp", company_financials=CompanyFinancials(company_name="Acme Corp"),
    )
    await pipeline.analyze(request)

    assert len(valuation.calls) == 1
    valuation_input = valuation.calls[0]
    assert valuation_input.discount_rate is None
    assert valuation_input.terminal_growth_rate is None
    assert valuation_input.target_pe is None
    assert valuation_input.ebitda is None


@pytest.mark.asyncio
async def test_dependency_injection_with_all_fakes_and_fixed_clock():
    fixed_times = [datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)]

    def clock():
        return fixed_times.pop(0)

    pipeline = _pipeline(clock=clock)
    result = await pipeline.analyze(_request())

    assert result.metadata.started_at == "2026-01-01T00:00:00+00:00"
    assert result.metadata.completed_at == "2026-01-01T00:00:01+00:00"
    assert result.metadata.duration_ms == 1000


@pytest.mark.asyncio
async def test_analyst_service_receives_deterministic_outputs_not_raw_financials():
    analyst = FakeAnalystService()
    pipeline = _pipeline(analyst=analyst)
    await pipeline.analyze(_request())

    assert len(analyst.calls) == 1
    financial_analysis, valuation, scoring, company_financials = analyst.calls[0]
    assert isinstance(financial_analysis, FinancialAnalysisResult)
    assert isinstance(valuation, ValuationRange)
    assert isinstance(scoring, ScoringResult)

from decimal import Decimal

import pytest

from app.models.analyst import AnalystResponse, AnalystResult, AnalystSection
from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_statements import CompanyFinancials
from app.models.research import ResearchError, ResearchErrorCode, ResearchItem, ResearchResult, ResearchSource
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult
from app.models.valuation import ValuationRange
from app.pipeline.models import AnalysisRequest, PipelineStatus
from app.pipeline.service import AnalysisPipelineService


def d(value) -> Decimal:
    return Decimal(str(value))


def _request(research_enabled=False, **overrides):
    defaults = dict(
        company_name="Acme Corp", ticker="ACME",
        company_financials=CompanyFinancials(company_name="Acme Corp"),
        research={"enabled": research_enabled},
    )
    defaults.update(overrides)
    return AnalysisRequest(**defaults)


class FakeFinancialService:
    def analyze(self, company_financials):
        return FinancialAnalysisResult(company="Acme Corp", periods_analyzed=["FY2024"], metrics=[])


class FakeValuationService:
    def analyze(self, valuation_input):
        return ValuationRange(company="Acme Corp", results=[])


class FakeScoringService:
    def analyze(self, financial_analysis, valuation):
        return ScoringResult(
            company_name="Acme Corp", overall_score=d(70), overall_status=ScoreStatus.CALCULATED,
            category_scores=[CategoryScore(category="profitability", score=d(70), weight=d("1.0"), status=ScoreStatus.CALCULATED)],
        )


class FakeAnalystService:
    def __init__(self):
        self.calls = []

    async def analyze(self, financial_analysis, valuation, scoring, company_financials=None, research=None):
        self.calls.append(research)
        section = AnalystSection(text="ok")
        return AnalystResult(status="success", response=AnalystResponse(
            company_name="Acme Corp", investment_thesis=section, profitability_analysis=section,
            growth_analysis=section, financial_health_analysis=section, cash_flow_analysis=section,
            valuation_analysis=section, risk_analysis=section,
        ))


class FakeResearchService:
    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises
        self.calls = []

    async def search(self, query):
        self.calls.append(query)
        if self._raises:
            raise self._raises
        return self._result


def _success_research():
    item = ResearchItem(
        id="research_001", title="Acme Corp expands", summary="Summary.",
        source=ResearchSource(title="Acme Corp expands", publisher="News", url="https://a.com/1",
                               published_at="2026-01-01T00:00:00+00:00"),
        published_at="2026-01-01T00:00:00+00:00",
    )
    return ResearchResult(status="success", items=[item], sources=[item.source], retrieved_at="2026-01-10T00:00:00+00:00")


def _pipeline(research_service=None):
    return AnalysisPipelineService(
        financial_service=FakeFinancialService(),
        valuation_service=FakeValuationService(),
        scoring_service=FakeScoringService(),
        analyst_service=FakeAnalystService(),
        research_service=research_service,
    )


@pytest.mark.asyncio
async def test_research_disabled_by_default_service_never_called():
    research_service = FakeResearchService(result=_success_research())
    pipeline = _pipeline(research_service=research_service)

    result = await pipeline.analyze(_request())  # research_enabled defaults to False

    assert research_service.calls == []
    assert result.research is None
    assert result.status is PipelineStatus.CALCULATED


@pytest.mark.asyncio
async def test_research_enabled_and_successful_flows_into_result_and_analyst():
    research_service = FakeResearchService(result=_success_research())
    pipeline = _pipeline(research_service=research_service)

    result = await pipeline.analyze(_request(research_enabled=True))

    assert len(research_service.calls) == 1
    assert result.research is not None
    assert result.research.status == "success"
    assert result.status is PipelineStatus.CALCULATED  # analyst still succeeds


@pytest.mark.asyncio
async def test_research_enabled_but_no_service_configured_adds_warning_not_failure():
    pipeline = _pipeline(research_service=None)

    result = await pipeline.analyze(_request(research_enabled=True))

    assert result.status is PipelineStatus.CALCULATED
    assert result.research is None
    assert any("no research service is configured" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_research_provider_failure_does_not_fail_pipeline():
    research_service = FakeResearchService(
        result=ResearchResult(
            status="error", error=ResearchError(code=ResearchErrorCode.PROVIDER_UNAVAILABLE, message="down"),
            retrieved_at="2026-01-10T00:00:00+00:00",
        )
    )
    pipeline = _pipeline(research_service=research_service)

    result = await pipeline.analyze(_request(research_enabled=True))

    assert result.status is PipelineStatus.CALCULATED  # deterministic + analyst both fine
    assert any("Research enrichment unavailable" in w for w in result.warnings)
    assert result.financial_analysis is not None
    assert result.valuation is not None
    assert result.scoring is not None


@pytest.mark.asyncio
async def test_research_service_raising_unexpectedly_does_not_crash_pipeline():
    research_service = FakeResearchService(raises=RuntimeError("boom"))
    pipeline = _pipeline(research_service=research_service)

    result = await pipeline.analyze(_request(research_enabled=True))

    assert result.status is PipelineStatus.CALCULATED
    assert result.research is None


@pytest.mark.asyncio
async def test_research_empty_results_is_still_success_status():
    empty_research = ResearchResult(status="success", items=[], warnings=["no relevant research results were found"], retrieved_at="2026-01-10T00:00:00+00:00")
    research_service = FakeResearchService(result=empty_research)
    pipeline = _pipeline(research_service=research_service)

    result = await pipeline.analyze(_request(research_enabled=True))

    assert result.status is PipelineStatus.CALCULATED
    assert result.research.items == []
    assert "no relevant research results were found" in result.warnings


@pytest.mark.asyncio
async def test_deterministic_stages_unaffected_by_research_options():
    research_service = FakeResearchService(result=_success_research())
    pipeline_with = _pipeline(research_service=research_service)
    pipeline_without = _pipeline(research_service=None)

    result_with = await pipeline_with.analyze(_request(research_enabled=True))
    result_without = await pipeline_without.analyze(_request(research_enabled=False))

    assert result_with.financial_analysis == result_without.financial_analysis
    assert result_with.scoring == result_without.scoring


@pytest.mark.asyncio
async def test_dependency_injection_research_service_is_optional_constructor_arg():
    # Constructing without research_service at all must still work (Step 6 callers unaffected).
    pipeline = AnalysisPipelineService(
        financial_service=FakeFinancialService(),
        valuation_service=FakeValuationService(),
        scoring_service=FakeScoringService(),
        analyst_service=FakeAnalystService(),
    )
    result = await pipeline.analyze(_request())
    assert result.status is PipelineStatus.CALCULATED

"""Thin transport layer for the end-to-end analysis pipeline.

This module must never contain orchestration or calculation logic — it
only builds the (already-existing) services, hands the request to
`AnalysisPipelineService`, and returns its result.
"""

import logging

from fastapi import APIRouter, Depends

from app.analyst.service import AnalystService
from app.application.service import AnalysisApplicationService
from app.core.config import Settings, get_settings
from app.data.factory import get_financial_data_provider
from app.data.service import FinancialDataService
from app.financial.service import FinancialAnalysisService
from app.llm.factory import get_llm_provider
from app.models.analyst import AnalystError, AnalystErrorCode, AnalystResult
from app.pipeline.models import (
    AnalysisRequest,
    CombinedAnalysisResult,
    PipelineCompanyInfo,
    PipelineStatus,
    TickerAnalysisRequest,
)
from app.pipeline.service import AnalysisPipelineService
from app.reporting.service import ReportService
from app.research.factory import get_research_provider
from app.research.service import ResearchService
from app.scoring.service import ScoringService
from app.valuation.service import ValuationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analyze"])


class _MisconfiguredAnalystService:
    """Stand-in for `AnalystService` when no LLM provider can be built.

    Lets the deterministic stages complete normally (`status="partial"`)
    instead of failing the whole request over an LLM configuration issue.
    """

    def __init__(self, message: str) -> None:
        self._message = message

    async def analyze(self, *_args, **_kwargs) -> AnalystResult:
        return AnalystResult(
            status="error",
            error=AnalystError(code=AnalystErrorCode.LLM_UNAVAILABLE, message=self._message),
        )


def _build_research_service(settings: Settings) -> ResearchService | None:
    """Returns `None` (not an error) when unconfigured — research is
    always optional; a caller who didn't opt in never even calls this."""
    try:
        provider = get_research_provider(settings)
    except ValueError as exc:
        logger.info("Research provider not configured: %s", exc)
        return None
    return ResearchService(
        provider,
        default_date_range_days=settings.research_default_days,
        default_max_results=settings.research_default_max_results,
        stale_after_days=settings.research_stale_after_days,
    )


def _build_pipeline(settings: Settings) -> AnalysisPipelineService:
    try:
        provider = get_llm_provider(settings)
        analyst_service = AnalystService(provider)
    except ValueError as exc:
        logger.warning("Analyst LLM provider misconfigured: %s", exc)
        analyst_service = _MisconfiguredAnalystService(str(exc))

    return AnalysisPipelineService(
        financial_service=FinancialAnalysisService(),
        valuation_service=ValuationService(),
        scoring_service=ScoringService(),
        analyst_service=analyst_service,
        research_service=_build_research_service(settings),
    )


def _with_report_if_requested(
    result: CombinedAnalysisResult, include_report: bool
) -> CombinedAnalysisResult:
    """Step 9: report generation is pure post-processing over an already
    -complete `CombinedAnalysisResult` — no pipeline stage needs to know
    about it, and no analysis logic is duplicated here."""
    if not include_report:
        return result
    report = ReportService().generate(result)
    return result.model_copy(update={"report": report})


@router.post("/analyze")
async def analyze(
    request: AnalysisRequest, settings: Settings = Depends(get_settings)
) -> CombinedAnalysisResult:
    pipeline = _build_pipeline(settings)
    result = await pipeline.analyze(request)
    return _with_report_if_requested(result, request.include_report)


@router.post("/analyze/ticker")
async def analyze_ticker(
    request: TickerAnalysisRequest, settings: Settings = Depends(get_settings)
) -> CombinedAnalysisResult:
    try:
        provider = get_financial_data_provider(settings)
    except ValueError as exc:
        logger.warning("Financial data provider misconfigured: %s", exc)
        return CombinedAnalysisResult(
            company=PipelineCompanyInfo(name=request.ticker, ticker=request.ticker),
            status=PipelineStatus.FAILED,
            warnings=[f"Financial data provider is not configured: {exc}"],
        )

    pipeline = _build_pipeline(settings)
    application_service = AnalysisApplicationService(FinancialDataService(provider), pipeline)
    result = await application_service.analyze_by_ticker(request)
    return _with_report_if_requested(result, request.include_report)

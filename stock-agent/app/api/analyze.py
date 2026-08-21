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
    )


@router.post("/analyze")
async def analyze(
    request: AnalysisRequest, settings: Settings = Depends(get_settings)
) -> CombinedAnalysisResult:
    pipeline = _build_pipeline(settings)
    return await pipeline.analyze(request)


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
    return await application_service.analyze_by_ticker(request)

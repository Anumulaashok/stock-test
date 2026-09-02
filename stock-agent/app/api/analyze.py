"""Thin transport layer for the end-to-end analysis pipeline.

This module must never contain orchestration or calculation logic — it
only builds the (already-existing) services, hands the request to
`AnalysisPipelineService`, and returns its result.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    build_cached_financial_data_service,
    build_cached_market_data_service,
    build_pipeline,
)
from app.application.service import AnalysisApplicationService
from app.core.config import Settings, get_settings
from app.data.factory import get_financial_data_provider
from app.db.base import get_db
from app.pipeline.models import (
    AnalysisRequest,
    CombinedAnalysisResult,
    PipelineCompanyInfo,
    PipelineStatus,
    TickerAnalysisRequest,
)
from app.reporting.service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analyze"])


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
    pipeline = build_pipeline(settings)
    result = await pipeline.analyze(request)
    return _with_report_if_requested(result, request.include_report)


@router.post("/analyze/ticker")
async def analyze_ticker(
    request: TickerAnalysisRequest,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
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

    pipeline = build_pipeline(settings)
    market_data_service = build_cached_market_data_service(settings, db)
    application_service = AnalysisApplicationService(
        build_cached_financial_data_service(settings, provider, db), pipeline, market_data_service
    )
    result = await application_service.analyze_by_ticker(request)
    return _with_report_if_requested(result, request.include_report)

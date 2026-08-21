"""Composes data acquisition and analysis for ticker-based requests.

`AnalysisApplicationService.analyze_by_ticker` fetches `CompanyFinancials`
via `FinancialDataService`, then hands them to the existing, unmodified
`AnalysisPipelineService` — exactly the same pipeline `POST /api/v1/analyze`
already uses. If data acquisition fails, the pipeline is never invoked;
the result is a `CombinedAnalysisResult` with `status="failed"` and a
sanitized warning (never a raw provider payload or credential).
"""

import logging

from app.data.models import CompanyIdentifier
from app.data.service import FinancialDataService
from app.pipeline.models import (
    AnalysisRequest,
    CombinedAnalysisResult,
    PipelineCompanyInfo,
    PipelineStatus,
    TickerAnalysisRequest,
)
from app.pipeline.service import AnalysisPipelineService

logger = logging.getLogger(__name__)


class AnalysisApplicationService:
    def __init__(
        self,
        financial_data_service: FinancialDataService,
        analysis_pipeline_service: AnalysisPipelineService,
    ) -> None:
        self._financial_data_service = financial_data_service
        self._pipeline = analysis_pipeline_service

    async def analyze_by_ticker(self, request: TickerAnalysisRequest) -> CombinedAnalysisResult:
        company = PipelineCompanyInfo(name=request.ticker, ticker=request.ticker)

        fetch_result = await self._financial_data_service.get_company_financials(
            CompanyIdentifier(ticker=request.ticker)
        )

        if fetch_result.status != "success":
            logger.warning(
                "Financial data fetch failed for %s: %s", request.ticker, fetch_result.error
            )
            return CombinedAnalysisResult(
                company=company,
                status=PipelineStatus.FAILED,
                warnings=[f"Failed to retrieve financial data: {fetch_result.error.message}"],
            )

        data = fetch_result.data
        analysis_request = AnalysisRequest(
            company_name=data.company_financials.company_name,
            ticker=request.ticker,
            company_financials=data.company_financials,
            **request.model_dump(exclude={"ticker"}),
        )

        result = await self._pipeline.analyze(analysis_request)
        return result.model_copy(update={"warnings": data.warnings + result.warnings})

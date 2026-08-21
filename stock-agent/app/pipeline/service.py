"""End-to-end analysis pipeline: orchestration only, no calculation.

`AnalysisPipelineService` coordinates the existing Step 2-5 services in
order and assembles their outputs into one `CombinedAnalysisResult`. It
knows nothing about Qwen, HTTP, or prompts — only `AnalystService` talks
to an `LLMProvider`. Every dependency is injected so each stage can be
replaced with a fake/mock in tests.

Failure policy:
- A deterministic stage (financial analysis, valuation, scoring) raising
  is treated as a pipeline failure: whatever deterministic results were
  already produced are kept, later stages are skipped, and `status` is
  `failed`.
- The AI analyst stage is optional: if it returns (or itself raises) an
  error, the deterministic results are still returned in full with
  `status` `partial` and `analyst.status == "error"`.
- Research enrichment (Step 8) is even more optional than the analyst:
  it only runs when the request opts in AND a research service is
  injected. A research failure NEVER changes `status` by itself — it
  only adds a warning and the analyst runs without research context
  (still contributing to `status` exactly as before). `research_service`
  lives on this same orchestrator (not `AnalysisApplicationService`)
  because research output feeds directly into the same analyst call
  that financial/valuation/scoring results already feed — splitting
  that composition across two services would mean the analyst's input
  is assembled in two different places instead of one.
"""

import logging
from datetime import datetime, timezone
from typing import Callable

from app.models.analyst import AnalystError, AnalystErrorCode, AnalystResult
from app.models.research import ResearchQuery
from app.pipeline.adapters import build_valuation_input
from app.pipeline.models import (
    AnalysisRequest,
    CombinedAnalysisResult,
    ExecutionMetadata,
    PipelineCompanyInfo,
    PipelineStatus,
)

logger = logging.getLogger(__name__)


class AnalysisPipelineService:
    """Runs `CompanyFinancials` through financial analysis, valuation,
    scoring, optional research enrichment, and the AI analyst, in that
    order."""

    def __init__(
        self,
        financial_service,
        valuation_service,
        scoring_service,
        analyst_service,
        research_service=None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._financial_service = financial_service
        self._valuation_service = valuation_service
        self._scoring_service = scoring_service
        self._analyst_service = analyst_service
        self._research_service = research_service
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def analyze(self, request: AnalysisRequest) -> CombinedAnalysisResult:
        started_at = self._clock()
        company = PipelineCompanyInfo(name=request.company_name, ticker=request.ticker)
        warnings: list[str] = []

        try:
            financial_analysis = self._financial_service.analyze(request.company_financials)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any stage failure degrades gracefully
            logger.error("Financial analysis stage failed: %s", exc)
            return self._failed_result(company, "financial_analysis", started_at, warnings=warnings)

        warnings.extend(financial_analysis.warnings)

        try:
            valuation_input = build_valuation_input(request, financial_analysis)
            valuation = self._valuation_service.analyze(valuation_input)
        except Exception as exc:  # noqa: BLE001
            logger.error("Valuation stage failed: %s", exc)
            return self._failed_result(
                company, "valuation", started_at,
                financial_analysis=financial_analysis, warnings=warnings,
            )

        warnings.extend(valuation.warnings)

        try:
            scoring = self._scoring_service.analyze(financial_analysis, valuation)
        except Exception as exc:  # noqa: BLE001
            logger.error("Scoring stage failed: %s", exc)
            return self._failed_result(
                company, "scoring", started_at,
                financial_analysis=financial_analysis, valuation=valuation, warnings=warnings,
            )

        warnings.extend(scoring.warnings)

        research = None
        if request.research.enabled:
            if self._research_service is None:
                warnings.append(
                    "Research enrichment was requested but no research service is configured."
                )
            else:
                try:
                    research = await self._research_service.search(
                        ResearchQuery(
                            company_name=request.company_name, ticker=request.ticker,
                            date_range_days=request.research.days,
                            max_results=request.research.max_results,
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - research is optional; never fail the pipeline for it
                    logger.error("Research stage raised unexpectedly: %s", exc)
                    research = None
                if research is not None:
                    if research.status != "success":
                        detail = research.error.message if research.error else "unknown error"
                        warnings.append(f"Research enrichment unavailable: {detail}")
                    else:
                        warnings.extend(research.warnings)

        try:
            analyst = await self._analyst_service.analyze(
                financial_analysis, valuation, scoring, request.company_financials, research
            )
        except Exception as exc:  # noqa: BLE001 - analyst is optional; never fail the pipeline for it
            logger.error("Analyst stage raised unexpectedly: %s", exc)
            analyst = AnalystResult(
                status="error",
                error=AnalystError(
                    code=AnalystErrorCode.LLM_UNAVAILABLE,
                    message="The analyst stage failed unexpectedly.",
                ),
            )

        if analyst.status == "success":
            status = PipelineStatus.CALCULATED
        else:
            status = PipelineStatus.PARTIAL
            detail = analyst.error.message if analyst.error else "unknown error"
            warnings.append(f"AI analyst stage did not complete successfully: {detail}")

        return CombinedAnalysisResult(
            company=company, status=status,
            financial_analysis=financial_analysis, valuation=valuation, scoring=scoring,
            research=research, analyst=analyst, warnings=warnings,
            metadata=self._metadata(started_at),
        )

    def _failed_result(
        self, company, failed_stage: str, started_at: datetime,
        financial_analysis=None, valuation=None, warnings: list[str] | None = None,
    ) -> CombinedAnalysisResult:
        return CombinedAnalysisResult(
            company=company, status=PipelineStatus.FAILED,
            financial_analysis=financial_analysis, valuation=valuation, scoring=None, analyst=None,
            warnings=(warnings or []) + [f"Pipeline failed during the {failed_stage} stage."],
            metadata=self._metadata(started_at),
        )

    def _metadata(self, started_at: datetime) -> ExecutionMetadata:
        completed_at = self._clock()
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        return ExecutionMetadata(
            started_at=started_at.isoformat(), completed_at=completed_at.isoformat(),
            duration_ms=duration_ms,
        )

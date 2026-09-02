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
- Forecasting is optional the same way research is: it only runs when a
  `forecasting_service` is injected, and a failure never changes
  `status` — only a warning is added and `forecast` stays `None`.
  Forecast output deliberately does NOT feed the analyst prompt or the
  deterministic score/signal — it is presentation-layer extrapolation,
  not evidence those stages should reason over.
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
        forecasting_service=None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._financial_service = financial_service
        self._valuation_service = valuation_service
        self._scoring_service = scoring_service
        self._analyst_service = analyst_service
        self._research_service = research_service
        self._forecasting_service = forecasting_service
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def analyze(self, request: AnalysisRequest, run_analyst: bool = True) -> CombinedAnalysisResult:
        """`run_analyst=False` skips the AI analyst narrative entirely
        (`analyst` stays `None`, `status` is `calculated` once the
        deterministic stages succeed) — used by the Q&A assistant, which
        needs the same deterministic context but not a second LLM call
        for a narrative nobody asked for."""
        started_at = self._clock()
        company = PipelineCompanyInfo(
            name=request.company_name,
            ticker=request.ticker,
            currency=request.company_financials.currency,
        )
        warnings: list[str] = []

        try:
            financial_analysis = self._financial_service.analyze(request.company_financials)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any stage failure degrades gracefully
            logger.error("Financial analysis stage failed: %s", exc)
            return self._failed_result(company, "financial_analysis", started_at, warnings=warnings)

        warnings.extend(financial_analysis.warnings)

        try:
            valuation_input, valuation_input_warnings = build_valuation_input(request, financial_analysis)
            warnings.extend(valuation_input_warnings)
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

        forecast = None
        if self._forecasting_service is not None:
            try:
                forecast_kwargs = dict(
                    company_financials=request.company_financials,
                    financial_analysis=financial_analysis,
                    valuation_input=valuation_input,
                    recent_prices=request.recent_prices,
                    ticker=request.ticker,
                )
                if request.projection_years is not None:
                    forecast_kwargs["projection_years"] = request.projection_years
                forecast = self._forecasting_service.forecast(**forecast_kwargs)
            except Exception as exc:  # noqa: BLE001 - forecasting is optional; never fail the pipeline for it
                logger.error("Forecasting stage raised unexpectedly: %s", exc)
                forecast = None
                warnings.append("Forecasting was requested but failed unexpectedly.")
            else:
                warnings.extend(forecast.warnings)

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

        analyst = None
        if not run_analyst:
            status = PipelineStatus.CALCULATED
        else:
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
            forecast=forecast, research=research, analyst=analyst, warnings=warnings,
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

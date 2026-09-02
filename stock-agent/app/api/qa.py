"""API surface for the AI Q&A assistant.

Accepts a ticker and a free-form question, re-derives the same
deterministic context the AI analyst uses (financial analysis,
valuation, scoring, optional research — never re-running the analyst's
narrative, which the assistant doesn't need), and returns a grounded
`QAResult`. Uses the existing `LLMProvider` factory; does not open a
second LLM client.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.context import build_analyst_context
from app.api.dependencies import (
    build_cached_financial_data_service,
    build_cached_market_data_service,
    build_pipeline,
)
from app.application.service import AnalysisApplicationService
from app.core.config import Settings, get_settings
from app.data.factory import get_financial_data_provider
from app.db.base import get_db
from app.llm.factory import get_llm_provider
from app.models.qa import QAError, QAErrorCode, QAResult, QATickerRequest
from app.pipeline.models import ResearchOptions, TickerAnalysisRequest
from app.qa.service import QAService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/qa", tags=["qa"])


@router.post("/ticker")
async def ask_ticker_question(
    request: QATickerRequest,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> QAResult:
    try:
        data_provider = get_financial_data_provider(settings)
    except ValueError as exc:
        logger.warning("Financial data provider misconfigured: %s", exc)
        return QAResult(
            status="error",
            error=QAError(
                code=QAErrorCode.DATA_UNAVAILABLE,
                message=f"Financial data provider is not configured: {exc}",
            ),
        )

    try:
        llm_provider = get_llm_provider(settings)
    except ValueError as exc:
        logger.warning("Q&A LLM provider misconfigured: %s", exc)
        return QAResult(
            status="error", error=QAError(code=QAErrorCode.LLM_UNAVAILABLE, message=str(exc))
        )

    pipeline = build_pipeline(settings)
    market_data_service = build_cached_market_data_service(settings, db)
    application_service = AnalysisApplicationService(
        build_cached_financial_data_service(settings, data_provider, db), pipeline, market_data_service
    )
    result = await application_service.analyze_by_ticker(
        TickerAnalysisRequest(ticker=request.ticker, research=ResearchOptions(enabled=True)),
        run_analyst=False,
    )

    if result.financial_analysis is None or result.scoring is None:
        return QAResult(
            status="error",
            error=QAError(
                code=QAErrorCode.DATA_UNAVAILABLE,
                message=f"Could not retrieve enough data for {request.ticker} to answer questions about it.",
            ),
        )

    context = build_analyst_context(
        financial_analysis=result.financial_analysis,
        valuation=result.valuation,
        scoring=result.scoring,
        research=result.research,
    )

    qa_service = QAService(llm_provider, max_response_tokens=settings.qa_max_response_tokens)
    return await qa_service.answer(context, request.question)

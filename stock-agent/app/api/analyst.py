"""Minimal API surface for the AI analyst.

Accepts already-computed deterministic domain models (Steps 2-4) — never
raw numbers for the LLM to calculate from — and returns a structured
`AnalystResult`. Uses the existing `LLMProvider` factory; does not open
a second LLM client.
"""

import logging

from fastapi import APIRouter, Depends

from app.analyst.service import AnalystService
from app.core.config import Settings, get_settings
from app.llm.factory import get_llm_provider
from app.models.analyst import AnalystError, AnalystErrorCode, AnalystRequest, AnalystResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analyst", tags=["analyst"])


@router.post("")
async def analyze(
    request: AnalystRequest, settings: Settings = Depends(get_settings)
) -> AnalystResult:
    try:
        provider = get_llm_provider(settings)
    except ValueError as exc:
        logger.warning("Analyst LLM provider misconfigured: %s", exc)
        return AnalystResult(
            status="error",
            error=AnalystError(code=AnalystErrorCode.LLM_UNAVAILABLE, message=str(exc)),
        )

    service = AnalystService(provider)
    return await service.analyze(
        financial_analysis=request.financial_analysis,
        valuation=request.valuation,
        scoring=request.scoring,
        company_financials=request.company_financials,
        research=request.research,
    )

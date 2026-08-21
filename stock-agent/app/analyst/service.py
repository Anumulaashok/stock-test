"""AI Analyst service.

Wires the deterministic Step 2-4 results through `AnalystContext` ->
prompt -> `LLMProvider` -> validated `AnalystResponse`. Depends only on
the `LLMProvider` interface (never a concrete provider), matching the
rest of the application's LLM-abstraction policy. Performs no financial
calculation of its own — every number in the output must trace back to
`AnalystContext`.
"""

import logging

from app.analyst.context import build_analyst_context, valid_evidence_names
from app.analyst.parsing import AnalystValidationError, build_analyst_response, extract_json_object
from app.analyst.prompts import build_system_instructions, build_user_prompt
from app.llm.base import LLMProvider, LLMProviderError
from app.models.analyst import AnalystError, AnalystErrorCode, AnalystResult
from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_statements import CompanyFinancials
from app.models.research import ResearchResult
from app.models.scoring import ScoringResult
from app.models.valuation import ValuationRange

logger = logging.getLogger(__name__)

# Keep responses compact given the CPU-only ~5-8 tok/s reference server —
# at the low end, even 700 tokens can take well over a minute.
_MAX_RESPONSE_TOKENS = 700


class AnalystService:
    """Generates a narrative `AnalystResponse` over deterministic results."""

    def __init__(self, llm_provider: LLMProvider, max_retries: int = 1) -> None:
        self._llm_provider = llm_provider
        self._max_retries = max_retries

    async def analyze(
        self,
        financial_analysis: FinancialAnalysisResult,
        valuation: ValuationRange | None,
        scoring: ScoringResult,
        company_financials: CompanyFinancials | None = None,
        research: ResearchResult | None = None,
    ) -> AnalystResult:
        context = build_analyst_context(financial_analysis, valuation, scoring, company_financials, research)
        valid_evidence = valid_evidence_names(context)
        system_prompt = build_system_instructions()
        base_prompt = build_user_prompt(context)

        prompt = base_prompt
        last_error: AnalystValidationError | None = None

        for attempt in range(self._max_retries + 1):
            try:
                raw = await self._llm_provider.generate(
                    prompt, system_prompt=system_prompt, max_tokens=_MAX_RESPONSE_TOKENS, enable_thinking=False,
                )
            except LLMProviderError as exc:
                code = (
                    AnalystErrorCode.TIMEOUT
                    if "timed out" in str(exc).lower()
                    else AnalystErrorCode.LLM_UNAVAILABLE
                )
                logger.error("Analyst LLM call failed: %s", exc)
                return AnalystResult(status="error", error=AnalystError(code=code, message=str(exc)))

            try:
                data = extract_json_object(raw)
                response = build_analyst_response(data, context.company.name, valid_evidence)
                return AnalystResult(status="success", response=response)
            except AnalystValidationError as exc:
                last_error = exc
                logger.warning(
                    "Analyst response failed validation (attempt %s/%s): %s",
                    attempt + 1, self._max_retries + 1, exc.message,
                )
                prompt = (
                    f"{base_prompt}\n\n"
                    f"Your previous response was invalid: {exc.message}. "
                    "Respond again with ONLY a single valid JSON object matching the schema above."
                )

        return AnalystResult(
            status="error", error=AnalystError(code=last_error.code, message=last_error.message)
        )

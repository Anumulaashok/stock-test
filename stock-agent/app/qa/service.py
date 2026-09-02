"""AI Q&A assistant service.

Wires an `AnalystContext` (the same structured, deterministic context
`AnalystService` uses) plus a free-form question through a prompt to
`LLMProvider` and back to a validated `QAResponse`. Depends only on the
`LLMProvider` interface, matching the rest of the application's
LLM-abstraction policy. Performs no financial calculation of its own —
every number referenced in the answer's evidence must trace back to the
supplied `AnalystContext`.
"""

import logging

from app.analyst.context import valid_evidence_names
from app.llm.base import LLMProvider, LLMProviderError
from app.models.analyst import AnalystContext
from app.models.qa import QAError, QAErrorCode, QAResult
from app.qa.parsing import QAValidationError, build_qa_response, extract_json_object
from app.qa.prompts import build_qa_system_instructions, build_qa_user_prompt

logger = logging.getLogger(__name__)

# Answers are one question, one grounded response — shorter than a full
# analyst report, so this default is lower than the analyst's. A
# reasoning model needs a much larger budget (see
# `Settings.qa_max_response_tokens`); callers pass that in rather than
# relying on this default.
_MAX_RESPONSE_TOKENS = 400


class QAService:
    """Answers one free-form question, grounded in an `AnalystContext`."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        max_retries: int = 1,
        max_response_tokens: int = _MAX_RESPONSE_TOKENS,
    ) -> None:
        self._llm_provider = llm_provider
        self._max_retries = max_retries
        self._max_response_tokens = max_response_tokens

    async def answer(self, context: AnalystContext, question: str) -> QAResult:
        valid_evidence = valid_evidence_names(context)
        system_prompt = build_qa_system_instructions()
        base_prompt = build_qa_user_prompt(context, question)

        prompt = base_prompt
        last_error: QAValidationError | None = None

        for attempt in range(self._max_retries + 1):
            try:
                raw = await self._llm_provider.generate(
                    prompt,
                    system_prompt=system_prompt,
                    max_tokens=self._max_response_tokens,
                    enable_thinking=False,
                )
            except LLMProviderError as exc:
                code = QAErrorCode.TIMEOUT if "timed out" in str(exc).lower() else QAErrorCode.LLM_UNAVAILABLE
                logger.error("Q&A LLM call failed: %s", exc)
                return QAResult(status="error", error=QAError(code=code, message=str(exc)))

            try:
                data = extract_json_object(raw)
                response = build_qa_response(data, valid_evidence)
                return QAResult(status="success", response=response)
            except QAValidationError as exc:
                last_error = exc
                logger.warning(
                    "Q&A response failed validation (attempt %s/%s): %s",
                    attempt + 1, self._max_retries + 1, exc.message,
                )
                prompt = (
                    f"{base_prompt}\n\n"
                    f"Your previous response was invalid: {exc.message}. "
                    "Respond again with ONLY a single valid JSON object matching the schema above."
                )

        return QAResult(status="error", error=QAError(code=last_error.code, message=last_error.message))

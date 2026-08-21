"""Research orchestration.

`ResearchService` validates the query, delegates to a `ResearchProvider`,
and applies the same provider-agnostic post-processing (dedup, freshness,
relevance, ranking/limiting) to every provider's results. Never
calculates a financial metric, never touches scoring/valuation, never
calls the LLM. Converts any `ResearchProviderError` into a structured
`ResearchResult` — callers never need exception handling for an expected
failure (provider down, rate limited, auth failure, ...).
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from app.models.research import ResearchError, ResearchErrorCode, ResearchQuery, ResearchResult
from app.research.base import ResearchProvider
from app.research.exceptions import ResearchProviderError
from app.research.processing import compute_freshness, compute_relevance, deduplicate, rank_and_limit, unique_sources

logger = logging.getLogger(__name__)

DEFAULT_DATE_RANGE_DAYS = 30
DEFAULT_MAX_RESULTS = 5
DEFAULT_STALE_AFTER_DAYS = 14


class ResearchService:
    def __init__(
        self,
        provider: ResearchProvider,
        default_date_range_days: int = DEFAULT_DATE_RANGE_DAYS,
        default_max_results: int = DEFAULT_MAX_RESULTS,
        stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._default_date_range_days = default_date_range_days
        self._default_max_results = default_max_results
        self._stale_after_days = stale_after_days
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def search(self, query: ResearchQuery) -> ResearchResult:
        retrieved_at = self._clock()

        if not query.company_name and not query.ticker:
            return ResearchResult(
                status="error",
                error=ResearchError(
                    code=ResearchErrorCode.INVALID_QUERY,
                    message="company_name or ticker is required",
                ),
                retrieved_at=retrieved_at.isoformat(),
            )

        try:
            raw_items, warnings = await self._provider.search(query)
        except ResearchProviderError as exc:
            logger.warning("Research provider error: %s [%s]", exc.message, exc.code)
            return ResearchResult(
                status="error",
                error=ResearchError(code=exc.code, message=exc.message),
                retrieved_at=retrieved_at.isoformat(),
            )

        warnings = list(warnings)
        deduped, dedupe_warnings = deduplicate(raw_items)
        warnings.extend(dedupe_warnings)

        scored = [
            item.model_copy(
                update={
                    "freshness": compute_freshness(item.published_at, retrieved_at, self._stale_after_days),
                    "relevance": compute_relevance(item, query),
                }
            )
            for item in deduped
        ]

        max_results = query.max_results or self._default_max_results
        ranked = rank_and_limit(scored, max_results)
        final_items = [
            item.model_copy(update={"id": f"research_{index + 1:03d}"})
            for index, item in enumerate(ranked)
        ]

        if not final_items:
            warnings.append("no relevant research results were found")

        return ResearchResult(
            status="success",
            items=final_items,
            sources=unique_sources(final_items),
            warnings=warnings,
            retrieved_at=retrieved_at.isoformat(),
        )
